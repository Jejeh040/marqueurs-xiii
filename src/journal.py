"""Suivi des conseils : ce qui a été annoncé, ce que ça a donné.

Sans ce fichier, l'outil ne peut rien prouver. C'est la seule pièce qui dise
si le modèle gagne de l'argent ou en perd.
"""

from __future__ import annotations

import json
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
