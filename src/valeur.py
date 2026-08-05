"""Croisement modèle / marché et détection des paris à valeur.

Deux idées portent tout le module.

1. **Dévigorisation par le total d'essais.** La somme des essais attendus de
   tous les joueurs vaut, par construction, le nombre d'essais attendus du
   match — que le marché cote par ailleurs. Le facteur qui ramène l'une sur
   l'autre EST la marge du bookmaker, et il donne des probabilités de marché
   propres, sans avoir à supposer quoi que ce soit.

2. **On ne parie jamais contre le marché sur le niveau, seulement sur la
   répartition.** Le total d'essais d'une équipe est très bien estimé par le
   marché ; la part de chaque joueur l'est beaucoup moins. Quand le marché
   donne le total, le modèle s'y aligne et ne garde que ce qu'il sait faire :
   départager les joueurs. (Même raisonnement que le marché « le plus d'aces »
   d'AcesTennis, où le biais de niveau s'annule.)
"""

from __future__ import annotations

import math
import unicodedata

from . import kambi, model

# Garde-fous. Chacun répond à une erreur constatée, pas à une intuition.
COTE_MAXI = 7.0         # au-delà, l'erreur du modèle dépasse l'avantage supposé
COTE_MINI = 1.30        # en dessous, la marge du book mange tout le gain
GAIN_MINI = 0.12        # il faut p x cote >= 1,12 pour couvrir l'erreur d'estimation
GAIN_MAXI = 0.40        # au-delà, c'est une erreur de modèle, pas une occasion
ECART_RELATIF_MAX = 1.5  # contredire le marché de plus de 50 % en relatif = erreur
PROBA_MAXI = 0.50        # au-dessus, le modèle est mesuré optimiste (56 % pour 51 %)
MATCHS_MINI = 6         # joueur vu moins souvent -> « à vérifier », jamais conseillé
ECART_TOTAL_MAX = 1.6   # désaccord en essais avec le marché -> aucun conseil
MARGE_MINI = 1.02       # une marge sous 1 signale une lecture incohérente
INCONNUS_MAX = 0.30     # part d'effectif inconnu au-delà de laquelle on doute
PENCHANT = 0.75         # part d'avis dans le même sens déclenchant le bandeau


def _cle(nom: str) -> str:
    s = unicodedata.normalize("NFKD", nom or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() else " " for c in s.lower())
    return " ".join(s.split())


def _cle_equipe(nom: str) -> str:
    """Nom d'équipe comparable entre SofaScore et Kambi (« (W) » vs « (F) »)."""
    k = _cle(nom)
    for suffixe in (" w", " f", " women", " femmes"):
        if k.endswith(suffixe):
            k = k[: -len(suffixe)]
    return k.strip()


def annuaire_equipes(matchs: list[dict]) -> dict[tuple[int, str], int]:
    """Index (compétition, nom normalisé) -> identifiant SofaScore.

    Indexer sur le seul nom confondrait les Sydney Roosters hommes et femmes,
    et ferait analyser un match féminin avec les notes de l'équipe masculine.
    """
    ann = {}
    for m in matchs:
        ann[(m["tournoi"], _cle_equipe(m["dom_nom"]))] = m["dom_id"]
        ann[(m["tournoi"], _cle_equipe(m["ext_nom"]))] = m["ext_id"]
    return ann


def devigoriser(cotes: list[float], dispos: list[float],
                total_attendu: float) -> tuple[list[float], float]:
    """Probabilités de marché sans marge + facteur de marge.

    Une cote « marqueur d'essai » vaut pour un joueur qui entre en jeu (sinon le
    pari est remboursé). L'espérance d'essais du joueur vue par le marché est
    donc `dispo x -ln(1-p)`, et la somme de ces espérances sur les deux
    effectifs doit valoir le total d'essais que le marché attend de l'équipe.
    Sans la pondération par `dispo`, les 3 remplaçants non retenus gonflent la
    somme et la marge apparaît deux fois trop grosse.
    """
    lam = [-math.log(max(1.0 - 1.0 / c, 1e-6)) for c in cotes]
    somme = sum(l * d for l, d in zip(lam, dispos))
    if somme <= 0 or not total_attendu:
        return ([1.0 / c for c in cotes], 1.0)
    k = total_attendu / somme
    return ([1.0 - math.exp(-k * l) for l in lam], 1.0 / k)


def _verdict(ligne: dict, ecart_total: float | None, camp: dict) -> tuple[str, str]:
    cote = ligne.get("cote")
    if not cote:
        return ("aucune", "pas de cote")
    if ecart_total is not None and abs(ecart_total) > ECART_TOTAL_MAX:
        return ("desaccord",
                f"le modèle et le marché ne sont pas d'accord sur le nombre "
                f"d'essais du match ({ecart_total:+.1f})")
    marge = camp.get("marge")
    if marge is not None and marge < MARGE_MINI:
        return ("desaccord",
                f"les cotes de ce match impliquent moins d'essais que le total "
                f"coté par ailleurs (facteur {marge:.2f}) — lecture incohérente")
    if camp.get("part_inconnus", 0.0) > INCONNUS_MAX:
        return ("verifier",
                f"{camp['part_inconnus']:.0%} de l'effectif est inconnu du modèle")
    gain = ligne["p_essai"] * cote - 1.0
    ligne["gain"] = gain
    if gain < GAIN_MINI:
        return ("rien", "pas d'avantage suffisant")
    if cote > COTE_MAXI:
        return ("verifier", f"cote trop haute ({cote:.2f}) pour ce modèle")
    if cote < COTE_MINI:
        return ("rien", "cote trop courte")
    if gain > GAIN_MAXI:
        return ("verifier", f"avantage annoncé irréaliste (+{gain:.0%}) — "
                            "presque toujours une erreur de modèle")
    if ligne["p_essai"] > PROBA_MAXI:
        return ("verifier",
                "au-dessus de 50 % le modèle est mesuré optimiste "
                "(56 % annoncés pour 51 % réalisés) — avantage sans doute illusoire")
    pm = ligne.get("p_marche")
    if pm and ligne["p_essai"] / pm > ECART_RELATIF_MAX:
        return ("verifier",
                f"le modèle donne {ligne['p_essai'] / pm:.1f} fois la chance vue "
                "par le marché : c'est le modèle qui a tort la plupart du temps")
    if ligne["matchs_connus"] < MATCHS_MINI:
        return ("verifier", f"joueur vu seulement {ligne['matchs_connus']} fois")
    return ("conseille", f"+{gain:.0%} d'avantage estimé")


def _effectif(rencontre: dict, dom: bool, compo: dict | None):
    """Qui aligner : la compo officielle si elle est sortie, sinon les 20 noms
    cotés par le bookmaker.

    La compo officielle apporte deux choses que le bookmaker ne donne pas :
    les numéros de maillot (donc les postes en NRL) et la certitude de jouer.
    """
    cotes_par_nom = {_cle(j["nom"]): j for j in rencontre["joueurs"] if j["dom"] == dom}
    if compo:
        joueurs = (compo.get("home") if dom else compo.get("away")) or {}
        liste = joueurs.get("players") or []
        if len(liste) >= 12:
            return ([{"nom": (p.get("player") or {}).get("name"),
                      "maillot": p.get("shirtNumber"),
                      "banc": bool(p.get("substitute")),
                      "titulaire": not p.get("substitute")}
                     for p in liste
                     if (p.get("player") or {}).get("name")], cotes_par_nom, True)
    return ([{"nom": j["nom"]} for j in rencontre["joueurs"] if j["dom"] == dom],
            cotes_par_nom, False)


def analyser_match(mdl, rencontre: dict, dom_id: int, ext_id: int,
                   tournoi: int, compo: dict | None = None) -> dict:
    """Un match Kambi + les identités SofaScore -> toutes les lignes joueurs."""
    total_marche = kambi.esperance_poisson(rencontre.get("total_match") or [])
    totaux_eq = {}
    for nom, lignes in (rencontre.get("total_equipe") or {}).items():
        lam = kambi.esperance_poisson(lignes)
        if lam:
            totaux_eq[_cle_equipe(nom)] = lam

    resultat = {"camps": [], "total_marche": total_marche, "total_modele": 0.0,
                "compo_officielle": bool(compo)}
    for dom in (True, False):
        equipe = dom_id if dom else ext_id
        adverse = ext_id if dom else dom_id
        effectif, par_nom, officielle = _effectif(rencontre, dom, compo)
        if not effectif:
            continue
        lignes = mdl.predire_camp(equipe, adverse, tournoi, dom, effectif,
                                  positionnel=None if officielle else False)
        attendus_modele = lignes[0]["essais_equipe"] if lignes else 0.0

        # Recalage sur le total d'équipe du marché quand il existe.
        nom_eq = _cle_equipe(rencontre["dom"] if dom else rencontre["ext"])
        attendus_marche = totaux_eq.get(nom_eq)
        cible = attendus_marche or attendus_modele
        if attendus_modele > 0:
            facteur = cible / attendus_modele
            for l in lignes:
                l["lambda"] *= facteur
                l["p_essai"] = 1.0 - math.exp(-l["lambda"])
                l["p_double"] = 1.0 - math.exp(-l["lambda"]) * (1.0 + l["lambda"])
        resultat["total_modele"] += attendus_modele

        for l in lignes:
            j = par_nom.get(_cle(l["nom"]), {})
            l["cote"] = j.get("cote")
            l["cote_premier"] = j.get("cote_premier")

        # Marché sans marge, à l'échelle du camp.
        cotees = [l for l in lignes if l.get("cote")]
        if cotees and cible:
            probas, marge = devigoriser([l["cote"] for l in cotees],
                                        [l["dispo"] for l in cotees], cible)
            for l, p in zip(cotees, probas):
                l["p_marche"] = p
        else:
            marge = None
            for l in lignes:
                l["p_marche"] = (1.0 / l["cote"]) if l.get("cote") else None

        inconnus = sum(1 for l in lignes if l["matchs_connus"] < 3)
        resultat["camps"].append({
            "dom": dom,
            "nom": rencontre["dom"] if dom else rencontre["ext"],
            "essais_modele": attendus_modele,
            "essais_marche": attendus_marche,
            "essais_retenus": cible,
            "marge": marge,
            "part_inconnus": inconnus / max(len(lignes), 1),
            "officielle": officielle,
            "lignes": lignes,
        })

    ecart = None
    if total_marche and resultat["total_modele"]:
        ecart = resultat["total_modele"] - total_marche
    resultat["ecart_total"] = ecart

    for camp in resultat["camps"]:
        for l in camp["lignes"]:
            l["verdict"], l["motif"] = _verdict(l, ecart, camp)
    return resultat


def penchant(analyses: list[dict]) -> str | None:
    """Alerte quand tous les conseils vont dans le même sens.

    Vingt conseils qui pointent tous vers les joueurs à grosse cote, ce n'est
    pas vingt occasions : c'est un seul désaccord systématique, répété.
    """
    conseils = [l for a in analyses for c in a["camps"] for l in c["lignes"]
                if l.get("verdict") == "conseille"]
    if len(conseils) < 6:
        return None
    hautes = sum(1 for l in conseils if l["cote"] >= 3.5)
    if hautes / len(conseils) >= PENCHANT:
        return (f"{hautes} conseils sur {len(conseils)} portent sur des cotes ≥ 3,50. "
                "Le modèle a probablement un penchant systématique pour les joueurs "
                "peu attendus, pas {} occasions distinctes.".format(len(conseils)))
    if (len(conseils) - hautes) / len(conseils) >= PENCHANT:
        return (f"{len(conseils) - hautes} conseils sur {len(conseils)} portent sur "
                "des favoris. Le modèle est probablement décalé vers le haut sur les "
                "joueurs les plus attendus.")
    return None
