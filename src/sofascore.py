"""Accès à l'API publique SofaScore pour le rugby à XIII.

Gratuit, sans clé. SofaScore renvoie 403 aux clients HTTP classiques : il faut
`curl_cffi` avec une empreinte de navigateur (même technique que AcesTennis).
"""

from __future__ import annotations

import threading
import time

from curl_cffi import requests

BASE = "https://api.sofascore.com/api/v1"

# Compétitions suivies. L'identifiant est celui de SofaScore (uniqueTournament).
# Le libellé Kambi permet de rapprocher les cotes (voir src/kambi.py).
COMPETITIONS = {
    294: {"nom": "NRL", "kambi": "NRL", "pays": "Australie"},
    302: {"nom": "Super League", "kambi": "Super Ligue", "pays": "Angleterre"},
}

# NRL Women (uniqueTournament 19120) est cotée par Unibet mais RESTE HORS DU
# MODÈLE : SofaScore publie les essais mais aucune composition d'équipe (0 sur
# 191 matchs, vérifié). Sans savoir qui a joué, il n'y a pas de dénominateur et
# donc pas de taux par joueur. À rallumer le jour où les compos apparaissent.
SANS_COMPOSITIONS = {19120: {"nom": "NRL Women", "kambi": "NRL (F)"}}

_local = threading.local()
_verrou = threading.Lock()
_dernier_appel = [0.0]
PAUSE = 0.05  # secondes entre deux requêtes, tous fils confondus


def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session(impersonate="chrome")
        _local.s = s
    return s


def _get(chemin: str, essais: int = 3):
    """GET sur l'API. Renvoie None sur 404 (ressource absente), lève sinon.

    Un None doit toujours pouvoir se distinguer d'un échec de lecture : les
    erreurs autres que 404 remontent en exception plutôt qu'en absence de
    données silencieuse.
    """
    derniere = None
    for tentative in range(essais):
        with _verrou:
            attente = PAUSE - (time.time() - _dernier_appel[0])
            if attente > 0:
                time.sleep(attente)
            _dernier_appel[0] = time.time()
        try:
            r = _session().get(BASE + chemin, timeout=25)
        except Exception as exc:  # réseau
            derniere = exc
            time.sleep(0.8 * (tentative + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 200:
            return r.json()
        derniere = RuntimeError(f"SofaScore {r.status_code} sur {chemin}")
        # 403/429 = on nous freine : pause franche avant de réessayer
        time.sleep(1.5 * (tentative + 1))
    raise RuntimeError(f"SofaScore injoignable sur {chemin} ({derniere})")


# --------------------------------------------------------------------------
# Calendrier
# --------------------------------------------------------------------------

def saisons(tournoi: int) -> list[dict]:
    d = _get(f"/unique-tournament/{tournoi}/seasons") or {}
    return d.get("seasons", [])


def evenements(tournoi: int, saison: int, sens: str = "last") -> list[dict]:
    """Tous les matchs d'une saison (`last` = joués, `next` = à venir)."""
    sortie, page = [], 0
    while True:
        d = _get(f"/unique-tournament/{tournoi}/season/{saison}/events/{sens}/{page}")
        if not d:
            break
        sortie.extend(d.get("events", []))
        if not d.get("hasNextPage"):
            break
        page += 1
        if page > 40:  # garde-fou
            break
    return sortie


def incidents(event_id: int) -> list[dict] | None:
    d = _get(f"/event/{event_id}/incidents")
    return None if d is None else d.get("incidents", [])


def compositions(event_id: int) -> dict | None:
    """Compos officielles. 404 tant que le bookmaker les publie avant SofaScore."""
    return _get(f"/event/{event_id}/lineups")


def evenement(event_id: int) -> dict | None:
    d = _get(f"/event/{event_id}")
    return None if d is None else d.get("event")


def termine(ev: dict) -> bool:
    """Un match n'est réglé que s'il est explicitement terminé.

    Leçon d'AcesTennis : juger un pronostic sur des statistiques partielles
    gonfle le taux de réussite dans le sens flatteur.
    """
    return (ev.get("status") or {}).get("type") == "finished"
