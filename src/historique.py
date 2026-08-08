"""Construction et mise à jour de la base de matchs.

Un match = qui a joué (compo + numéro de maillot) et qui a marqué (essais).
Deux requêtes SofaScore par match, mises en cache sur disque : la base ne se
reconstruit jamais deux fois.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import sofascore

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FICHIER = os.path.join(DOSSIER, "historique.json")

SAISONS_MINI = 4      # nombre de saisons remontées par compétition
FILS = 4


def _charger() -> dict:
    if os.path.exists(FICHIER):
        with open(FICHIER, encoding="utf-8") as f:
            return json.load(f)
    return {"matchs": {}, "maj": None}


def _enregistrer(base: dict) -> None:
    os.makedirs(DOSSIER, exist_ok=True)
    base["maj"] = time.time()
    tmp = FICHIER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False)
    os.replace(tmp, FICHIER)


def _nom(x):
    if isinstance(x, dict):
        return x.get("name")
    return x or None


def _remplacement(i: dict) -> dict | None:
    entrant, sortant = _nom(i.get("playerIn")), _nom(i.get("playerOut"))
    if not entrant and not sortant:
        return None
    return {"entrant": entrant, "sortant": sortant,
            "minute": i.get("time"), "dom": bool(i.get("isHome"))}


def _details(ev: dict) -> dict | None:
    """Récupère essais + compo d'un match terminé."""
    eid = ev["id"]
    inc = sofascore.incidents(eid)
    if inc is None:
        return None
    essais, entrees, remplacements = [], [], []
    for i in inc:
        if i.get("incidentType") == "substitution":
            r = _remplacement(i)
            if r:
                remplacements.append(r)
                if r["entrant"]:
                    entrees.append({"joueur": r["entrant"], "dom": r["dom"]})
        if i.get("incidentClass") != "try":
            continue
        j = i.get("player") or {}
        if not j.get("name"):
            continue
        essais.append({
            "joueur": j["name"],
            "jid": j.get("id"),
            "maillot": j.get("jerseyNumber"),
            "dom": bool(i.get("isHome")),
            "minute": i.get("time"),
        })

    compo = sofascore.compositions(eid)
    joueurs = []
    if compo:
        for cote, dom in (("home", True), ("away", False)):
            for p in (compo.get(cote) or {}).get("players", []):
                j = p.get("player") or {}
                if not j.get("name"):
                    continue
                joueurs.append({
                    "joueur": j["name"],
                    "jid": j.get("id"),
                    "maillot": p.get("shirtNumber") or j.get("jerseyNumber"),
                    "dom": dom,
                    "banc": bool(p.get("substitute")),
                })

    score = ev.get("homeScore") or {}
    score_ext = ev.get("awayScore") or {}
    return {
        "id": eid,
        "tournoi": (ev["tournament"].get("uniqueTournament") or {}).get("id"),
        "saison": (ev.get("season") or {}).get("id"),
        "date": ev.get("startTimestamp"),
        "dom_id": ev["homeTeam"]["id"],
        "dom_nom": ev["homeTeam"]["name"],
        "ext_id": ev["awayTeam"]["id"],
        "ext_nom": ev["awayTeam"]["name"],
        "points_dom": score.get("current"),
        "points_ext": score_ext.get("current"),
        "essais": essais,
        "entrees": entrees,
        "remplacements": remplacements,
        "compo": joueurs,
    }


def reparer_remplacements(bavard: bool = True) -> int:
    """Rattrape entrées et sorties sur les matchs téléchargés avant leur ajout.

    Ne retélécharge que les incidents (une requête), jamais les compos.
    """
    base = _charger()
    manquants = [m for m in base["matchs"].values() if "remplacements" not in m]
    if not manquants:
        return 0
    if bavard:
        print(f"   {len(manquants)} matchs sans les remplacements, rattrapage...")

    def travail(m):
        try:
            inc = sofascore.incidents(m["id"]) or []
        except Exception:
            return m["id"], None
        return m["id"], [r for r in (_remplacement(i) for i in inc
                                     if i.get("incidentType") == "substitution") if r]

    fait = 0
    with ThreadPoolExecutor(max_workers=FILS) as pool:
        for eid, rs in pool.map(travail, manquants):
            if rs is None:
                continue
            m = base["matchs"][str(eid)]
            m["remplacements"] = rs
            m["entrees"] = [{"joueur": r["entrant"], "dom": r["dom"]}
                            for r in rs if r["entrant"]]
            fait += 1
    _enregistrer(base)
    if bavard:
        print(f"   {fait} matchs complétés")
    return fait


def completer(tournois=None, saisons_mini: int = SAISONS_MINI, bavard: bool = True) -> dict:
    """Complète la base. Incrémental : ne retélécharge que les matchs absents."""
    base = _charger()
    connus = base["matchs"]
    tournois = tournois or list(sofascore.COMPETITIONS)

    a_faire = []
    for tid in tournois:
        nom = sofascore.COMPETITIONS[tid]["nom"]
        for s in sofascore.saisons(tid)[:saisons_mini]:
            evs = sofascore.evenements(tid, s["id"], "last")
            neufs = [e for e in evs
                     if str(e["id"]) not in connus
                     and (e.get("status") or {}).get("type") == "finished"]
            if bavard:
                print(f"   {nom} {s['name']}: {len(evs)} matchs, {len(neufs)} à télécharger")
            a_faire.extend(neufs)

    if not a_faire:
        if bavard:
            print("   base déjà à jour")
        return base

    debut = time.time()
    fait = [0]

    def travail(ev):
        try:
            d = _details(ev)
        except Exception as exc:
            print(f"   ! {ev['id']} : {exc}", file=sys.stderr)
            return None
        fait[0] += 1
        if bavard and fait[0] % 50 == 0:
            print(f"   {fait[0]}/{len(a_faire)}...")
        return d

    with ThreadPoolExecutor(max_workers=FILS) as pool:
        for d in pool.map(travail, a_faire):
            if d:
                connus[str(d["id"])] = d

    _enregistrer(base)
    if bavard:
        print(f"   {len(a_faire)} matchs ajoutés en {time.time() - debut:.0f} s "
              f"(base : {len(connus)} matchs)")
    return base


def _numeroter(match: dict) -> None:
    """Fixe le numéro de maillot des marqueurs d'après la compo du match.

    Le numéro porté par l'incident vient de la FICHE du joueur (son numéro de
    club à l'année), pas de la feuille de match : Jake Connor y est le 18 alors
    qu'il joue avec le 7. Celui de la compo est le bon. Sans cette correction,
    un tiers des essais étaient attribués à des « remplaçants » et la
    répartition par poste était fausse dans les deux sens.
    """
    par_id, par_nom = {}, {}
    for p in match["compo"]:
        if p.get("maillot") in (None, ""):
            continue
        if p.get("jid"):
            par_id[p["jid"]] = p["maillot"]
        par_nom[p["joueur"]] = p["maillot"]
    for e in match["essais"]:
        officiel = par_id.get(e.get("jid")) or par_nom.get(e["joueur"])
        if officiel not in (None, ""):
            e["maillot"] = officiel

    # A réellement foulé la pelouse : titulaire, ou entré en cours de match.
    entres = {(e["joueur"], e["dom"]) for e in match.get("entrees", [])}
    inconnu = "entrees" not in match
    for p in match["compo"]:
        p["joue"] = (inconnu or not p.get("banc")
                     or (p["joueur"], p["dom"]) in entres)
    _minuter(match)


DUREE = 80.0


def _minuter(match: dict) -> None:
    """Minutes passées sur le terrain par joueur.

    Un pilier joue une cinquantaine de minutes là où un ailier en fait
    quatre-vingts : sans cette mesure, on lui prête le taux d'essais d'un
    joueur présent tout le match. Le XIII autorise les allers-retours
    (remplacements « interchange »), donc on additionne des créneaux.
    """
    if "remplacements" not in match:
        for p in match["compo"]:
            p["minutes"] = DUREE if p.get("joue") else 0.0
        return

    ouverts, total = {}, {}
    for p in match["compo"]:
        k = (p["joueur"], p["dom"])
        total[k] = 0.0
        if not p.get("banc"):
            ouverts[k] = 0.0

    for r in sorted(match["remplacements"], key=lambda r: r.get("minute") or 0):
        t = min(max(float(r.get("minute") or 0), 0.0), DUREE)
        if r.get("sortant"):
            k = (r["sortant"], r["dom"])
            if k in ouverts:
                total[k] = total.get(k, 0.0) + (t - ouverts.pop(k))
        if r.get("entrant"):
            k = (r["entrant"], r["dom"])
            if k not in ouverts:
                ouverts[k] = t
                total.setdefault(k, 0.0)

    for k, debut in ouverts.items():
        total[k] = total.get(k, 0.0) + (DUREE - debut)

    for p in match["compo"]:
        m = total.get((p["joueur"], p["dom"]), 0.0)
        p["minutes"] = round(min(max(m, 0.0), DUREE), 1)
        p["joue"] = p["minutes"] > 0


def charger() -> list[dict]:
    """Les matchs exploitables, triés par date."""
    base = _charger()
    m = [x for x in base["matchs"].values()
         if x.get("date") and x.get("compo") and x.get("points_dom") is not None]
    m.sort(key=lambda x: x["date"])
    for x in m:
        _numeroter(x)
    return m


def a_venir(tournois=None) -> list[dict]:
    """Matchs programmés, toutes compétitions suivies."""
    tournois = tournois or list(sofascore.COMPETITIONS)
    sortie = []
    for tid in tournois:
        s = sofascore.saisons(tid)
        if not s:
            continue
        for ev in sofascore.evenements(tid, s[0]["id"], "next"):
            sortie.append({
                "id": ev["id"],
                "tournoi": tid,
                "competition": sofascore.COMPETITIONS[tid]["nom"],
                "date": ev.get("startTimestamp"),
                "dom_id": ev["homeTeam"]["id"],
                "dom_nom": ev["homeTeam"]["name"],
                "ext_id": ev["awayTeam"]["id"],
                "ext_nom": ev["awayTeam"]["name"],
            })
    sortie.sort(key=lambda x: x["date"] or 0)
    return sortie
