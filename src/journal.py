"""Suivi des conseils : ce qui a été annoncé, ce que ça a donné.

Sans ce fichier, l'outil ne peut rien prouver. C'est la seule pièce qui dise
si le modèle gagne de l'argent ou en perd.
"""

from __future__ import annotations

import json
import math
import os
import time

from . import historique, model, sofascore

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FICHIER = os.path.join(DOSSIER, "journal.json")


def _charger() -> dict:
    if os.path.exists(FICHIER):
        with open(FICHIER, encoding="utf-8") as f:
            return json.load(f)
    return {"fiches": {}}


def _enregistrer(j: dict) -> None:
    os.makedirs(DOSSIER, exist_ok=True)
    tmp = FICHIER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FICHIER)


def enregistrer(event_id: int, contexte: dict, lignes: list[dict]) -> None:
    """Note les conseils du jour pour ce match (sans écraser un verdict déjà rendu)."""
    j = _charger()
    for l in lignes:
        if l.get("verdict") != "conseille":
            continue
        ref = f"{event_id}:{l['cle']}"
        fiche = j["fiches"].get(ref)
        if fiche and fiche.get("resultat") is not None:
            continue
        j["fiches"][ref] = {
            "event": event_id,
            "sofa": contexte.get("sofa"),
            "competition": contexte.get("competition"),
            "match": contexte.get("match"),
            "date_match": contexte.get("date_match"),
            "joueur": l["nom"],
            "cle": l["cle"],
            "equipe": contexte.get("equipe"),
            "cote": l["cote"],
            "p_modele": round(l["p_essai"], 4),
            "p_marche": round(l.get("p_marche") or 0, 4),
            "gain": round(l.get("gain") or 0, 4),
            "pose_le": time.time(),
            "resultat": fiche.get("resultat") if fiche else None,
        }
    _enregistrer(j)


def regler(bavard: bool = False) -> int:
    """Tranche les conseils dont le match est terminé.

    Un conseil n'est jugé que si SofaScore déclare le match `finished` :
    juger sur des statistiques partielles gonfle le taux de réussite dans le
    sens flatteur (erreur commise et corrigée dans AcesTennis).
    """
    j = _charger()
    en_attente = [f for f in j["fiches"].values() if f.get("resultat") is None]
    if not en_attente:
        return 0

    par_event = {}
    for f in en_attente:
        if f.get("sofa"):
            par_event.setdefault(f["sofa"], []).append(f)

    regles = 0
    for eid, fiches in par_event.items():
        ev = sofascore.evenement(eid)
        if not ev or not sofascore.termine(ev):
            continue
        inc = sofascore.incidents(eid)
        if inc is None:
            continue
        marqueurs = {model.cle((i.get("player") or {}).get("name", ""))
                     for i in inc if i.get("incidentClass") == "try"}
        entres = set()
        for i in inc:
            if i.get("incidentType") == "substitution" and i.get("playerIn"):
                nom = i["playerIn"]
                entres.add(model.cle(nom.get("name") if isinstance(nom, dict) else nom))
        compo = sofascore.compositions(eid) or {}
        alignes = set()
        for cote in ("home", "away"):
            for p in (compo.get(cote) or {}).get("players", []):
                k = model.cle((p.get("player") or {}).get("name", ""))
                if not p.get("substitute") or k in entres:
                    alignes.add(k)
        for f in fiches:
            if f["cle"] in marqueurs:
                f["resultat"] = "gagne"
            elif alignes and f["cle"] not in alignes:
                f["resultat"] = "rembourse"   # n'a pas joué : pari annulé
            else:
                f["resultat"] = "perdu"
            f["regle_le"] = time.time()
            regles += 1
            if bavard:
                print(f"   {f['joueur']} ({f['match']}) : {f['resultat']}")
    if regles:
        _enregistrer(j)
    return regles


ARCHIVE = os.path.join(DOSSIER, "predictions.json")


def _charger_archive() -> dict:
    if os.path.exists(ARCHIVE):
        with open(ARCHIVE, encoding="utf-8") as f:
            return json.load(f)
    return {"lignes": {}}


def archiver(event_id: int, contexte: dict, lignes: list[dict]) -> None:
    """Enregistre TOUS les joueurs cotés, pas seulement les conseils.

    C'est la seule façon de trancher un jour la vraie question : le modèle
    est-il meilleur que le marché ? Aucune source gratuite ne conserve les
    cotes de marqueur d'essai, donc si on ne les note pas au fil de l'eau,
    elles sont perdues. Le journal des conseils, lui, ne porte qu'une poignée
    de lignes par jour — beaucoup trop peu pour conclure.
    """
    a = _charger_archive()
    for l in lignes:
        if not l.get("cote") or l.get("p_marche") is None:
            continue
        ref = f"{event_id}:{l['cle']}"
        if a["lignes"].get(ref, {}).get("resultat") is not None:
            continue
        a["lignes"][ref] = {
            "sofa": contexte.get("sofa"),
            "date_match": contexte.get("date_match"),
            "competition": contexte.get("competition"),
            "joueur": l["nom"],
            "cle": l["cle"],
            "equipe": contexte.get("equipe"),
            "poste": l.get("poste"),
            "cote": round(l["cote"], 2),
            "p_modele": round(l["p_essai"], 4),
            "p_marche": round(l["p_marche"], 4),
            "resultat": None,
        }
    os.makedirs(DOSSIER, exist_ok=True)
    tmp = ARCHIVE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False)
    os.replace(tmp, ARCHIVE)


def _issues_du_match(eid: int):
    """(marqueurs, joueurs alignés) d'un match terminé, ou None s'il ne l'est pas."""
    ev = sofascore.evenement(eid)
    if not ev or not sofascore.termine(ev):
        return None
    inc = sofascore.incidents(eid)
    if inc is None:
        return None
    marqueurs = {model.cle((i.get("player") or {}).get("name", ""))
                 for i in inc if i.get("incidentClass") == "try"}
    entres = set()
    for i in inc:
        if i.get("incidentType") == "substitution" and i.get("playerIn"):
            nom = i["playerIn"]
            entres.add(model.cle(nom.get("name") if isinstance(nom, dict) else nom))
    compo = sofascore.compositions(eid) or {}
    alignes = set()
    for cote in ("home", "away"):
        for p in (compo.get(cote) or {}).get("players", []):
            k = model.cle((p.get("player") or {}).get("name", ""))
            if not p.get("substitute") or k in entres:
                alignes.add(k)
    return marqueurs, alignes


def regler_archive() -> int:
    """Renseigne le résultat des prédictions archivées dont le match est fini."""
    a = _charger_archive()
    attente = [l for l in a["lignes"].values() if l.get("resultat") is None and l.get("sofa")]
    if not attente:
        return 0
    par_event = {}
    for l in attente:
        par_event.setdefault(l["sofa"], []).append(l)
    regles = 0
    for eid, lignes in par_event.items():
        issues = _issues_du_match(eid)
        if issues is None:
            continue
        marqueurs, alignes = issues
        for l in lignes:
            if alignes and l["cle"] not in alignes:
                l["resultat"] = "absent"
            else:
                l["resultat"] = "essai" if l["cle"] in marqueurs else "rien"
            regles += 1
    if regles:
        tmp = ARCHIVE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(a, f, ensure_ascii=False)
        os.replace(tmp, ARCHIVE)
    return regles


def duel_modele_marche() -> dict | None:
    """Modèle contre marché, sur toutes les prédictions déjà tranchées."""
    a = _charger_archive()
    jouees = [l for l in a["lignes"].values() if l.get("resultat") in ("essai", "rien")]
    if not jouees:
        return None

    def perte(champ):
        s = 0.0
        for l in jouees:
            p = min(max(l[champ], 1e-6), 1 - 1e-6)
            s -= math.log(p) if l["resultat"] == "essai" else math.log(1 - p)
        return s / len(jouees)

    return {
        "n": len(jouees),
        "absents": sum(1 for l in a["lignes"].values() if l.get("resultat") == "absent"),
        "attente": sum(1 for l in a["lignes"].values() if l.get("resultat") is None),
        "perte_modele": perte("p_modele"),
        "perte_marche": perte("p_marche"),
        "taux": sum(1 for l in jouees if l["resultat"] == "essai") / len(jouees),
    }


def derniere_journee() -> dict | None:
    """Les conseils de la dernière journée déjà jouée, avec leur résultat.

    Jeremy veut voir le résultat de la veille à chaque ouverture du rapport,
    pas seulement un cumul depuis le début.
    """
    j = _charger()
    tranches = [f for f in j["fiches"].values()
                if f.get("resultat") in ("gagne", "perdu", "rembourse")
                and f.get("date_match")]
    if not tranches:
        return None
    par_jour = {}
    for f in tranches:
        jour = time.strftime("%Y-%m-%d", time.localtime(f["date_match"]))
        par_jour.setdefault(jour, []).append(f)
    jour = max(par_jour)
    fiches = sorted(par_jour[jour], key=lambda f: -f["cote"])
    joues = [f for f in fiches if f["resultat"] != "rembourse"]
    gagnes = [f for f in joues if f["resultat"] == "gagne"]
    return {
        "jour": jour,
        "fiches": fiches,
        "joues": len(joues),
        "gagnes": len(gagnes),
        "attendus": sum(f["p_modele"] for f in joues),
        "gain": sum(f["cote"] for f in gagnes) - len(joues),
    }


def bilan() -> dict:
    j = _charger()
    fiches = list(j["fiches"].values())
    tranches = [f for f in fiches if f.get("resultat") in ("gagne", "perdu")]
    gagnes = [f for f in tranches if f["resultat"] == "gagne"]
    mise = len(tranches)
    retour = sum(f["cote"] for f in gagnes)
    return {
        "en_attente": sum(1 for f in fiches if f.get("resultat") is None),
        "rembourses": sum(1 for f in fiches if f.get("resultat") == "rembourse"),
        "tranches": mise,
        "gagnes": len(gagnes),
        "reussite": (len(gagnes) / mise) if mise else None,
        "attendue": (sum(f["p_modele"] for f in tranches) / mise) if mise else None,
        "gain": retour - mise,
        "roi": ((retour - mise) / mise) if mise else None,
        "derniers": sorted(tranches, key=lambda f: -(f.get("regle_le") or 0))[:25],
    }
