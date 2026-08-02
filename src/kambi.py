"""Cotes « marqueur d'essai » via l'offre publique Kambi (moteur d'Unibet).

Aucune clé, aucun compte, aucun quota connu. Le code marché `ubbe` (Unibet
Belgique) répond ; `ubfr` renvoie 400.

Le marché 1001519712 « Try Scorer » porte, pour chaque joueur des deux
effectifs, trois cotes distinguées par `criterion.type` :
    4 = premier essai · 5 = dernier essai · 6 = marque un essai (à tout moment)
`homeTeamMember` sépare les deux équipes, et l'effectif annoncé par le
bookmaker (20 joueurs par équipe) sert de compo quand SofaScore ne l'a pas
encore publiée.
"""

from __future__ import annotations

import json
import os
import time

from curl_cffi import requests

BASE = "https://eu-offering-api.kambicdn.com/offering/v2018/ubbe"
PARAMS = "?lang=fr_BE&market=BE"
SPORT = "rugby_league"

CRIT_MARQUEUR = 1001519712
TYPE_PREMIER, TYPE_DERNIER, TYPE_TOUT_MOMENT = 4, 5, 6

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE = os.path.join(DOSSIER, "cotes.json")
FRAICHEUR = 20 * 60  # secondes

_session = None


def _s():
    global _session
    if _session is None:
        _session = requests.Session(impersonate="chrome")
    return _session


def _get(url: str):
    r = _s().get(url, timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f"Kambi {r.status_code} sur {url.split('/')[-1]}")
    return r.json()


def _lire_cache() -> dict:
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def _ecrire_cache(d: dict) -> None:
    os.makedirs(DOSSIER, exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, CACHE)


def rencontres() -> list[dict]:
    """Matchs de rugby à XIII cotés, avec leur groupe (NRL, Super Ligue, NRL (F))."""
    d = _get(f"{BASE}/listView/{SPORT}.json{PARAMS}")
    sortie = []
    for g in d.get("events", []):
        e = g.get("event", {})
        if e.get("state") not in (None, "NOT_STARTED"):
            continue
        sortie.append({
            "id": e["id"],
            "nom": e.get("name"),
            "groupe": e.get("group"),
            "debut": e.get("start"),
            "dom": e.get("homeName"),
            "ext": e.get("awayName"),
        })
    return sortie


def _lignes_ou(o: dict) -> list[dict]:
    """Une ligne plus/moins : (ligne, cote plus, cote moins)."""
    par_ligne = {}
    for oc in o.get("outcomes", []):
        if oc.get("status") != "OPEN" or oc.get("line") is None or oc.get("odds") is None:
            continue
        d = par_ligne.setdefault(oc["line"] / 1000.0, {"ligne": oc["line"] / 1000.0})
        d["plus" if oc.get("type") == "OT_OVER" else "moins"] = oc["odds"] / 1000.0
    return [v for v in par_ligne.values() if "plus" in v and "moins" in v]


def _extraire(bo: dict) -> dict:
    """Marqueurs + totaux d'essais (match et par équipe) d'une rencontre."""
    joueurs = {}
    total_match, total_equipe = [], {}
    for o in bo.get("betOffers", []):
        crit = o.get("criterion", {})
        en = crit.get("englishLabel") or ""
        if crit.get("id") == CRIT_MARQUEUR:
            for oc in o.get("outcomes", []):
                if oc.get("status") != "OPEN" or not oc.get("participant"):
                    continue
                f = joueurs.setdefault(oc["participant"], {
                    "nom": oc["participant"],
                    "dom": bool(oc.get("homeTeamMember")),
                    "pid": oc.get("participantId"),
                })
                t = (oc.get("criterion") or {}).get("type")
                cote = oc.get("odds")
                if cote is None:
                    continue
                if t == TYPE_TOUT_MOMENT:
                    f["cote"] = cote / 1000.0
                elif t == TYPE_PREMIER:
                    f["cote_premier"] = cote / 1000.0
                elif t == TYPE_DERNIER:
                    f["cote_dernier"] = cote / 1000.0
        elif en == "Total Tries - Including Overtime":
            total_match.extend(_lignes_ou(o))
        elif en.startswith("Total Tries by ") and en.endswith(" - Including Overtime"):
            equipe = en[len("Total Tries by "):-len(" - Including Overtime")]
            total_equipe.setdefault(equipe, []).extend(_lignes_ou(o))
    return {
        "joueurs": list(joueurs.values()),
        "total_match": total_match,
        "total_equipe": total_equipe,
    }


def esperance_poisson(lignes: list[dict]) -> float | None:
    """Nombre d'essais que le marché attend, déduit des lignes plus/moins.

    Les deux cotes d'une même ligne sont d'abord dévigorisées (leur somme
    ramenée à 1), puis on cherche le lambda de Poisson qui reproduit au mieux
    toutes les lignes disponibles.
    """
    obs = []
    for l in lignes:
        ip, im = 1.0 / l["plus"], 1.0 / l["moins"]
        s = ip + im
        if s <= 0:
            continue
        obs.append((l["ligne"], ip / s))
    if not obs:
        return None

    from math import exp, floor

    def p_plus(lam, ligne):
        # P(X > ligne) pour une ligne demi-entière
        k = int(floor(ligne))
        c, terme = 0.0, exp(-lam)
        for i in range(k + 1):
            c += terme
            terme *= lam / (i + 1)
        return 1.0 - c

    bas, haut = 0.5, 25.0
    for _ in range(60):
        mid = (bas + haut) / 2
        ecart = sum(p_plus(mid, ligne) - cible for ligne, cible in obs)
        if ecart > 0:
            haut = mid
        else:
            bas = mid
    return round((bas + haut) / 2, 2)


def cotes(event_id: int) -> dict:
    return _extraire(_get(f"{BASE}/betoffer/event/{event_id}.json{PARAMS}"))


def releve(forcer: bool = False) -> dict:
    """Relevé complet, mis en cache 20 minutes.

    En cas d'échec on renvoie le dernier relevé connu ET on remonte l'erreur :
    une absence de cote ne doit jamais se confondre avec un refus du serveur.
    """
    cache = _lire_cache()
    if not forcer and cache.get("t") and time.time() - cache["t"] < FRAICHEUR:
        return cache

    sortie = {"t": time.time(), "matchs": {}, "erreur": None}
    try:
        liste = rencontres()
    except Exception as exc:
        if cache:
            cache["erreur"] = f"Kambi injoignable ({exc}) — cotes datées."
            return cache
        return {"t": time.time(), "matchs": {}, "erreur": f"Kambi injoignable ({exc})"}

    echecs = 0
    for r in liste:
        try:
            d = cotes(r["id"])
        except Exception:
            echecs += 1
            continue
        if not d["joueurs"]:
            continue
        d.update(r)
        sortie["matchs"][str(r["id"])] = d
    if echecs:
        sortie["erreur"] = (f"{echecs} match(s) sur {len(liste)} n'ont pas répondu — "
                            "l'absence de cote n'y veut rien dire.")
    _ecrire_cache(sortie)
    return sortie


def marge(joueurs: list[dict]) -> float | None:
    """Marge du bookmaker sur le marché « marque un essai » d'un match.

    Chaque joueur est un pari indépendant : la marge se lit sur la somme des
    probabilités implicites rapportée au nombre d'essais attendus, pas sur 100 %.
    """
    cotes_ = [j["cote"] for j in joueurs if j.get("cote")]
    if not cotes_:
        return None
    return sum(1.0 / c for c in cotes_)
