"""Le modèle est-il meilleur que le bookmaker ?

La seule question qui compte, et la seule à laquelle `validate.py` ne peut pas
répondre : il mesure le modèle contre le passé, pas contre un prix. Aucune
source gratuite ne conserve les cotes de marqueur d'essai, alors `run.py`
archive chaque jour la probabilité du modèle ET celle du marché pour tous les
joueurs cotés. Ce script les confronte dès qu'il y en a assez.

    python comparer.py
"""

from __future__ import annotations

import math

from src import journal

SEUIL = 2000  # prédictions tranchées avant de prendre le résultat au sérieux


def _bandes(lignes):
    tranches = [(0, .10), (.10, .20), (.20, .30), (.30, .45), (.45, 1.01)]
    print(f"\n  {'marché dit':>12} {'n':>6} {'modèle':>8} {'marché':>8} {'réel':>8}")
    for a, b in tranches:
        s = [l for l in lignes if a <= l["p_marche"] < b]
        if len(s) < 30:
            continue
        print(f"  {f'{a:.0%}-{b:.0%}':>12} {len(s):>6} "
              f"{sum(l['p_modele'] for l in s) / len(s):>8.1%} "
              f"{sum(l['p_marche'] for l in s) / len(s):>8.1%} "
              f"{sum(1 for l in s if l['resultat'] == 'essai') / len(s):>8.1%}")


def main():
    d = journal.duel_modele_marche()
    if not d:
        print("Aucune prédiction archivée n'est encore tranchée.")
        print("Lance run.py chaque jour : l'archive se remplit toute seule.")
        return

    print(f"{d['n']} prédictions tranchées "
          f"({d['attente']} en attente, {d['absents']} joueurs n'ont pas joué)")
    print(f"taux d'essai réel : {d['taux']:.1%}\n")
    print(f"  perte logarithmique du modèle : {d['perte_modele']:.4f}")
    print(f"  perte logarithmique du marché : {d['perte_marche']:.4f}")
    ecart = d["perte_marche"] - d["perte_modele"]
    if ecart > 0:
        print(f"  -> le modèle fait mieux de {ecart:.4f}")
    else:
        print(f"  -> le marché fait mieux de {-ecart:.4f}")

    # Écart-type de la différence : sans lui, un signe ne veut rien dire.
    a = journal._charger_archive()
    lignes = [l for l in a["lignes"].values() if l.get("resultat") in ("essai", "rien")]
    diffs = []
    for l in lignes:
        pm = min(max(l["p_modele"], 1e-6), 1 - 1e-6)
        pk = min(max(l["p_marche"], 1e-6), 1 - 1e-6)
        gagne = l["resultat"] == "essai"
        diffs.append((-math.log(pk) if gagne else -math.log(1 - pk))
                     - (-math.log(pm) if gagne else -math.log(1 - pm)))
    n = len(diffs)
    moy = sum(diffs) / n
    var = sum((x - moy) ** 2 for x in diffs) / max(n - 1, 1)
    erreur = math.sqrt(var / n)
    print(f"  incertitude sur cet écart : ±{1.96 * erreur:.4f} (95 %)")
    if abs(moy) < 1.96 * erreur:
        print("  -> écart NON significatif : on ne peut pas les départager.")
    elif moy > 0:
        print("  -> le modèle bat le marché de façon significative.")
    else:
        print("  -> le marché bat le modèle de façon significative.")

    if n < SEUIL:
        print(f"\n  ATTENTION : {n} prédictions seulement, il en faut ~{SEUIL} "
              "pour que ce verdict tienne.")
    _bandes(lignes)


if __name__ == "__main__":
    main()
