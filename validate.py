"""Mesure du modèle sur des matchs qu'il n'a jamais vus.

Entraînement sur les matchs les plus anciens, test sur les plus récents. On
compare toujours à une référence naïve : sans référence, un chiffre de perte
logarithmique ne veut rien dire.

    python validate.py                  mesure complète
    python validate.py --sans-poste     ignore les postes (part joueur seule)
    python validate.py --avec-defense   rallume la faiblesse de défense par poste
    python validate.py --avec-cote      rallume le côté du terrain
    python validate.py --glissant       réentraînement mensuel (mode réaliste)

Les deux étages « faiblesse de la défense » sont désactivés par défaut : ils
ont été mesurés sans effet (voir le commentaire dans src/model.py).
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict

from src import historique, model, postes

JOUR = 86400.0


def _verite(m: dict) -> dict:
    """(camp, clé joueur) -> a marqué au moins un essai."""
    marque = set()
    for e in m["essais"]:
        marque.add((e["dom"], model.cle(e["joueur"])))
    return marque


def _cas(mdl: model.Modele, m: dict) -> list[tuple[float, int, dict]]:
    """Toutes les prédictions joueur d'un match, avec le résultat réel."""
    marque = _verite(m)
    sortie = []
    for dom in (True, False):
        # On ne juge que les joueurs entrés en jeu : un pari « marqueur
        # d'essai » sur un joueur qui ne joue pas est remboursé, pas perdu.
        joueurs = [p for p in m["compo"] if p["dom"] == dom and p.get("joue", True)]
        if len(joueurs) < 12:
            continue
        effectif = [{"nom": p["joueur"], "maillot": p.get("maillot"),
                     "banc": p.get("banc"), "titulaire": True} for p in joueurs]
        eq = m["dom_id"] if dom else m["ext_id"]
        adv = m["ext_id"] if dom else m["dom_id"]
        if eq not in mdl.equipes or adv not in mdl.equipes:
            continue
        lignes = mdl.predire_camp(eq, adv, m["tournoi"], dom, effectif)
        for l in lignes:
            reel = 1 if (dom, l["cle"]) in marque else 0
            sortie.append((l["p_essai"], reel, l))
    return sortie


def _mesures(cas, etiquette):
    if not cas:
        print(f"  {etiquette}: aucun cas")
        return None
    n = len(cas)
    ll = -sum(math.log(max(min(p, 1 - 1e-9), 1e-9)) if y else
              math.log(max(min(1 - p, 1 - 1e-9), 1e-9)) for p, y, _ in cas) / n
    brier = sum((p - y) ** 2 for p, y, _ in cas) / n
    taux = sum(y for _, y, _ in cas) / n
    biais = sum(p for p, _, _ in cas) / max(sum(y for _, y, _ in cas), 1)
    print(f"  {etiquette}: {n} cas | perte log {ll:.4f} | Brier {brier:.4f} "
          f"| taux réel {taux:.3f} | biais {biais:.3f}")
    return {"n": n, "ll": ll, "brier": brier, "taux": taux, "biais": biais}


def _reference(cas, taux_global):
    """Référence naïve : tout le monde à la moyenne."""
    return _mesures([(taux_global, y, l) for _, y, l in cas], "référence (moyenne)")


def _calibration(cas):
    bandes = [(0, .05), (.05, .1), (.1, .2), (.2, .3), (.3, .4),
              (.4, .5), (.5, .7), (.7, 1.01)]
    print("\n  Calibration :")
    print(f"    {'bande':>12} {'n':>6} {'annoncé':>9} {'réel':>8}")
    for a, b in bandes:
        s = [(p, y) for p, y, _ in cas if a <= p < b]
        if len(s) < 20:
            continue
        print(f"    {f'{a:.0%}-{b:.0%}':>12} {len(s):>6} "
              f"{sum(p for p, _ in s) / len(s):>9.1%} "
              f"{sum(y for _, y in s) / len(s):>8.1%}")


def _par_poste(cas):
    g = defaultdict(list)
    for p, y, l in cas:
        g[l["poste"] or "inconnu"].append((p, y))
    print("\n  Par poste :")
    print(f"    {'poste':>12} {'n':>6} {'annoncé':>9} {'réel':>8} {'biais':>7}")
    for k, s in sorted(g.items(), key=lambda x: -len(x[1])):
        if len(s) < 30:
            continue
        att = sum(p for p, _ in s) / len(s)
        reel = sum(y for _, y in s) / len(s)
        nom = postes.NOMS.get(k, k)
        print(f"    {nom[:12]:>12} {len(s):>6} {att:>9.1%} {reel:>8.1%} "
              f"{att / max(reel, 1e-9):>7.3f}")


def _par_competition(cas):
    pass


def fixe(matchs, part=0.75, **kw):
    coupe = int(len(matchs) * part)
    entr, test = matchs[:coupe], matchs[coupe:]
    print(f"Entraînement {len(entr)} matchs, test {len(test)} matchs "
          f"(coupure au {len(entr)}e)")
    mdl = model.Modele(entr, reference=entr[-1]["date"], **kw)
    cas = []
    for m in test:
        cas.extend(_cas(mdl, m))
    return cas


def glissant(matchs, part=0.6, pas_jours=30, **kw):
    """Réentraînement périodique : c'est ce que fait run.py en vrai."""
    coupe = int(len(matchs) * part)
    cas = []
    debut = matchs[coupe]["date"]
    fin = matchs[-1]["date"]
    t = debut
    while t <= fin:
        entr = [m for m in matchs if m["date"] < t]
        test = [m for m in matchs if t <= m["date"] < t + pas_jours * JOUR]
        if entr and test:
            mdl = model.Modele(entr, reference=t, **kw)
            for m in test:
                cas.extend(_cas(mdl, m))
        t += pas_jours * JOUR
    print(f"Mode glissant : réentraînement tous les {pas_jours} jours")
    return cas


def main():
    args = set(sys.argv[1:])
    kw = {
        "sans_poste": "--sans-poste" in args,
        "sans_defense": "--avec-defense" not in args,
        "sans_cote": "--avec-cote" not in args,
        "sans_minutes": "--sans-minutes" in args,
    }
    matchs = historique.charger()
    print(f"Base : {len(matchs)} matchs\n")
    variantes = []
    if kw["sans_poste"]:
        variantes.append("sans les postes")
    if not kw["sans_defense"]:
        variantes.append("avec la faiblesse de défense")
    if not kw["sans_cote"]:
        variantes.append("avec le côté du terrain")
    if kw["sans_minutes"]:
        variantes.append("sans le temps de jeu")
    if variantes:
        print("Variante :", ", ".join(variantes), "\n")

    cas = glissant(matchs, **kw) if "--glissant" in args else fixe(matchs, **kw)
    if not cas:
        print("Aucun cas testable.")
        return
    taux = sum(y for _, y, _ in cas) / len(cas)
    print()
    _mesures(cas, "modèle          ")
    _reference(cas, taux)
    _calibration(cas)
    _par_poste(cas)


if __name__ == "__main__":
    main()
