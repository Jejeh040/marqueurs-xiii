"""Postes du rugby à XIII, déduits du numéro de maillot.

Au XIII le numéro EST le poste (contrairement au football) : c'est la donnée la
plus fiable de SofaScore, dont le champ `position` est souvent vide ou faux.
"""

from __future__ import annotations

NOMS = {
    "ARR": "Arrière",
    "AIL": "Ailier",
    "CEN": "Centre",
    "OUV": "Demi",
    "TAL": "Talonneur",
    "PIL": "Pilier",
    "2EL": "2e ligne",
    "TRO": "Troisième ligne",
    "REM": "Remplaçant",
}

# numéro -> (poste, côté)  ; côté G/D/C (centre du terrain)
_TABLE = {
    1: ("ARR", "C"),
    2: ("AIL", "D"),
    3: ("CEN", "D"),
    4: ("CEN", "G"),
    5: ("AIL", "G"),
    6: ("OUV", "C"),
    7: ("OUV", "C"),
    8: ("PIL", "C"),
    9: ("TAL", "C"),
    10: ("PIL", "C"),
    11: ("2EL", "G"),
    12: ("2EL", "D"),
    13: ("TRO", "C"),
}

POSTES = ["ARR", "AIL", "CEN", "OUV", "TAL", "PIL", "2EL", "TRO", "REM"]
COTES = ["G", "D", "C"]


def depuis_maillot(numero) -> tuple[str, str]:
    """(poste, côté) pour un numéro de maillot. 14+ = banc."""
    try:
        n = int(numero)
    except (TypeError, ValueError):
        return ("REM", "C")
    if n in _TABLE:
        return _TABLE[n]
    return ("REM", "C")


def numerotation_positionnelle(joueurs: list[dict]) -> bool:
    """La compo d'une équipe utilise-t-elle les numéros comme postes ?

    La NRL numérote 1-17 par poste chaque semaine ; la Super League attribue un
    numéro fixe à l'année (comme le football), où le 22 peut être un ailier.
    Sans ce test, la moitié des essais de Super League seraient attribués à des
    « remplaçants ».
    """
    numeros = []
    for p in joueurs:
        try:
            numeros.append(int(p["maillot"]))
        except (TypeError, ValueError):
            continue
    if len(numeros) < 12:
        return False
    bas = [n for n in numeros if 1 <= n <= 13]
    if len(set(bas)) != len(bas):
        return False
    # Un remplaçant de dernière minute peut porter le 22 sans que le reste de
    # la feuille cesse d'être positionnel : on tolère deux numéros manquants.
    return len(set(bas)) >= 11


def libelle(poste: str, cote: str) -> str:
    base = NOMS.get(poste, poste)
    if cote == "G":
        return base + " gauche"
    if cote == "D":
        return base + " droit"
    return base
