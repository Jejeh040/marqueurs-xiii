"""Modèle de marqueur d'essai.

Trois étages, chacun mesurable séparément dans `validate.py` :

1. combien d'essais l'équipe va marquer (attaque / défense, Poisson) ;
2. quelle part de ces essais revient à chaque joueur (historique du joueur,
   régularisé vers la moyenne de son poste) ;
3. de quel poste et de quel côté la défense adverse encaisse le plus.

La probabilité de marquer au moins un essai est ensuite 1 - exp(-lambda).
"""

from __future__ import annotations

import math
import unicodedata
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

from . import postes
from .historique import DUREE

JOUR = 86400.0

# Réglages. Chaque valeur a été choisie pour être mesurable dans validate.py.
# Réglages retenus par balayage sur 26 648 prédictions hors échantillon
# (scratchpad/tune.py, réentraînement tous les 60 jours). La surface est plate :
# le balayage n'a gagné que 0,4477 -> 0,4469 de perte logarithmique. Le vrai gain
# est venu du volume de données, pas de ces quatre nombres.
DEMI_VIE = 300.0          # jours : mémoire des performances d'équipe
DEMI_VIE_JOUEUR = 750.0   # jours : mémoire des essais d'un joueur
K_JOUEUR = 2.5            # essais attendus de régularisation du multiplicateur
# 1,0 = pas de compression. Elle valait 0,85 tant que la base tenait en 1 430
# matchs : elle compensait le bruit. À 2 585 matchs elle ne sert plus (0,4474
# à 0,85 contre 0,4469 à 1,0). Ne pas la réactiver sans remesurer.
# Compression des écarts entre joueurs. Utile tant que la base tenait sur 4
# saisons (0,85 : perte log 0,4572 -> 0,4526) ; devenue nuisible à 8 saisons.
# Mesuré sur 33 336 cas : perte log identique (0,4458) mais les biais par poste
# se resserrent nettement, ailier 0,940 -> 0,988 et pilier 1,090 -> 0,968.
# Le niveau général, lui, est fixé par le total d'essais du marché en production.
COMPRESSION = 1.0
K_DEFENSE = 45.0          # essais encaissés de régularisation vers 1,0
K_COTE = 60.0             # idem pour le côté du terrain (échantillon plus fin)
REGUL_EQUIPE = 0.02       # pénalité L2 sur attaque/défense
MATCHS_DISPO = 8          # matchs récents servant à estimer la probabilité de jouer
SUR_LE_TERRAIN = 17.0     # joueurs d'une équipe qui foulent la pelouse en moyenne


def cle(nom: str) -> str:
    """Nom normalisé, pour rapprocher SofaScore et le bookmaker."""
    s = unicodedata.normalize("NFKD", nom or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _poids(age_jours: float, demi_vie: float) -> float:
    return 0.5 ** (max(age_jours, 0.0) / demi_vie)


class Modele:
    # Faiblesse de la défense adverse par poste et par côté : MESURÉE SANS
    # EFFET (perte log 0,4526 avec, 0,4518 sans, sur 9 880 cas hors
    # échantillon). Le conseil classique « viser le côté faible » ne se voit
    # pas dans les données à ce volume. Le code reste, désactivé, et
    # `validate.py --avec-defense` permet de le remesurer quand la base aura
    # grossi. Ne pas le rallumer sans nouvelle mesure.
    def __init__(self, matchs: list[dict], reference: float | None = None,
                 sans_poste: bool = False, sans_defense: bool = True,
                 sans_cote: bool = True, sans_minutes: bool = False):
        self.sans_minutes = sans_minutes
        self.sans_poste = sans_poste
        self.sans_defense = sans_defense
        self.sans_cote = sans_cote
        self.matchs = matchs
        self.reference = reference or max((m["date"] for m in matchs), default=0)
        self._preparer()
        self._ajuster_equipes()
        self._ajuster_joueurs()
        self._ajuster_defenses()

    # ------------------------------------------------------------------
    # Mise en forme
    # ------------------------------------------------------------------
    def _preparer(self):
        """Découpe chaque match en deux « camps » (équipe vs adversaire)."""
        self.camps = []
        self.postes_connus = {}   # (match_id, cote) -> bool
        for m in self.matchs:
            age = (self.reference - m["date"]) / JOUR
            if age < 0:
                continue
            for dom in (True, False):
                listes = [p for p in m["compo"] if p["dom"] == dom]
                # On n'apprend que sur les joueurs entrés sur le terrain : depuis
                # 2026 SofaScore liste aussi les réservistes non utilisés, qui
                # diluaient la part de tous les autres.
                joueurs = [p for p in listes if p.get("joue", True)]
                if len(joueurs) < 12:
                    continue
                positionnel = postes.numerotation_positionnelle(listes)
                self.postes_connus[(m["id"], dom)] = positionnel
                essais = [e for e in m["essais"] if e["dom"] == dom]
                self.camps.append({
                    "match": m["id"],
                    "tournoi": m["tournoi"],
                    "date": m["date"],
                    "age": age,
                    "poids": _poids(age, DEMI_VIE),
                    "poids_j": _poids(age, DEMI_VIE_JOUEUR),
                    "equipe": m["dom_id"] if dom else m["ext_id"],
                    "nom": m["dom_nom"] if dom else m["ext_nom"],
                    "adversaire": m["ext_id"] if dom else m["dom_id"],
                    "dom": dom,
                    "joueurs": joueurs,
                    "listes": listes,
                    "essais": essais,
                    "n_essais": len(essais),
                    "positionnel": positionnel,
                })

    def _minutes(self, p: dict) -> float:
        return DUREE if self.sans_minutes else float(p.get("minutes", DUREE))

    def poste_de(self, joueur: dict, positionnel: bool) -> tuple[str | None, str | None]:
        if self.sans_poste or not positionnel:
            return (None, None)
        return postes.depuis_maillot(joueur.get("maillot"))

    # ------------------------------------------------------------------
    # Étage 1 : essais attendus par équipe
    # ------------------------------------------------------------------
    def _ajuster_equipes(self):
        equipes = sorted({c["equipe"] for c in self.camps})
        self.equipes = {e: i for i, e in enumerate(equipes)}
        tournois = sorted({c["tournoi"] for c in self.camps})
        self.tournois = {t: i for i, t in enumerate(tournois)}
        n, nt = len(equipes), len(tournois)

        idx_a = np.array([self.equipes[c["equipe"]] for c in self.camps])
        idx_d = np.array([self.equipes[c["adversaire"]] for c in self.camps])
        idx_t = np.array([self.tournois[c["tournoi"]] for c in self.camps])
        dom = np.array([1.0 if c["dom"] else 0.0 for c in self.camps])
        y = np.array([c["n_essais"] for c in self.camps], dtype=float)
        w = np.array([c["poids"] for c in self.camps])

        def eclater(x):
            return x[:n], x[n:2 * n], x[2 * n:2 * n + nt], x[2 * n + nt:]

        def objectif(x):
            att, dfn, base, adv = eclater(x)
            eta = base[idx_t] + att[idx_a] - dfn[idx_d] + adv[idx_t] * dom
            eta = np.clip(eta, -6, 4)
            lam = np.exp(eta)
            nll = np.sum(w * (lam - y * eta))
            nll += REGUL_EQUIPE * np.sum(w.sum() * (att ** 2 + dfn ** 2)) / max(len(y), 1)
            return nll

        x0 = np.concatenate([np.zeros(2 * n), np.full(nt, math.log(4.0)), np.zeros(nt)])
        res = minimize(objectif, x0, method="L-BFGS-B",
                       options={"maxiter": 800, "maxfun": 40000})
        self.att, self.dfn, self.base, self.adv = eclater(res.x)
        self.convergence = bool(res.success)

    def essais_attendus(self, equipe, adversaire, tournoi, dom: bool) -> float:
        it = self.tournois.get(tournoi)
        if it is None:
            it = 0
        base = self.base[it]
        adv = self.adv[it] if dom else 0.0
        a = self.att[self.equipes[equipe]] if equipe in self.equipes else 0.0
        d = self.dfn[self.equipes[adversaire]] if adversaire in self.equipes else 0.0
        return float(np.exp(np.clip(base + a - d + adv, -6, 4)))

    # ------------------------------------------------------------------
    # Étage 2 : part de chaque joueur dans les essais de son équipe
    # ------------------------------------------------------------------
    def _ajuster_joueurs(self):
        # parts moyennes par poste (sur les compos numérotées par poste)
        num, num_c = defaultdict(float), defaultdict(float)
        minutes, joueurs_vus = defaultdict(float), defaultdict(float)
        places, compos = defaultdict(float), 0.0
        for c in self.camps:
            if not c["positionnel"]:
                continue
            compos += c["poids"]
            for p in c["joueurs"]:
                po, co = postes.depuis_maillot(p.get("maillot"))
                places[po] += c["poids"]
                minutes[po] += c["poids"] * self._minutes(p)
                joueurs_vus[po] += c["poids"]
            for e in c["essais"]:
                po, co = postes.depuis_maillot(e.get("maillot"))
                num[po] += c["poids"]
                num_c[co] += c["poids"]

        # Part du bucket dans les essais de l'équipe (sert aux ratios de défense).
        total = sum(num.values()) or 1.0
        self.part_bucket = {p: num.get(p, 0.0) / total for p in postes.POSTES}
        total_c = sum(num_c.values()) or 1.0
        self.part_bucket_cote = {p: num_c.get(p, 0.0) / total_c for p in postes.COTES}

        self.places = {p: (places.get(p, 0.0) / compos if compos else 0.0)
                       for p in postes.POSTES}

        # Essais par minute passée sur le terrain, poste par poste. Un pilier
        # joue ~50 minutes et un ailier 80 : compter en matchs mélangeait
        # « marque peu » et « joue peu », deux choses différentes.
        self.taux_bucket = {p: (num.get(p, 0.0) / minutes[p]) if minutes.get(p) else None
                            for p in postes.POSTES}
        self.minutes_bucket = {p: (minutes[p] / joueurs_vus[p]) if joueurs_vus.get(p)
                               else DUREE for p in postes.POSTES}
        mtot = sum(minutes.values())
        self.taux_moyen = (total / mtot) if mtot else 1.0 / (17 * DUREE)
        self.minutes_moyennes = (mtot / sum(joueurs_vus.values())) if joueurs_vus else DUREE

        # historique par joueur, exprimé en MULTIPLICATEUR de ce qu'on attend
        # de son poste. Un nombre d'essais brut serait faussé par la taille de
        # la feuille de match : SofaScore est passé de 17 à 19 noms listés en
        # 2026, ce qui divisait mécaniquement par 1,4 le taux par remplaçant.
        # Premier passage : poste habituel de chaque joueur, lu uniquement sur
        # les feuilles positionnelles. Il sert ensuite à situer ce joueur les
        # jours où la feuille ne dit rien (toute la Super League).
        vus = defaultdict(lambda: defaultdict(float))
        vus_cote = defaultdict(lambda: defaultdict(float))
        for c in self.camps:
            if not c["positionnel"] or self.sans_poste:
                continue
            for p in c["joueurs"]:
                po, co = postes.depuis_maillot(p.get("maillot"))
                vus[cle(p["joueur"])][po] += c["poids_j"]
                vus_cote[cle(p["joueur"])][co] += c["poids_j"]
        self._poste_habituel = {k: max(d.items(), key=lambda x: x[1])[0]
                                for k, d in vus.items()}
        self._cote_habituelle = {k: max(d.items(), key=lambda x: x[1])[0]
                                 for k, d in vus_cote.items()}

        self.joueurs = {}
        self.equipe_de = {}
        for c in self.camps:
            marqueurs = defaultdict(float)
            for e in c["essais"]:
                marqueurs[cle(e["joueur"])] += 1.0
            buckets = self.buckets_du_camp(c["joueurs"], c["positionnel"])
            reelles = [self._minutes(p) for p in c["joueurs"]]
            parts = self.parts_du_camp(c["joueurs"], c["positionnel"], buckets, reelles)
            for p, part, mn in zip(c["joueurs"], parts, reelles):
                k = cle(p["joueur"])
                po, co = self.poste_de(p, c["positionnel"])
                f = self.joueurs.setdefault(k, {
                    "nom": p["joueur"], "essais": 0.0, "attendus": 0.0,
                    "minutes": 0.0, "poids_min": 0.0,
                    "postes": defaultdict(float), "cotes": defaultdict(float),
                    "matchs": 0, "dernier": 0,
                })
                f["essais"] += c["poids_j"] * marqueurs.get(k, 0.0)
                f["attendus"] += c["poids_j"] * c["n_essais"] * part
                f["minutes"] += c["poids_j"] * mn
                f["poids_min"] += c["poids_j"]
                f["matchs"] += 1
                f["dernier"] = max(f["dernier"], c["date"])
                if po:
                    f["postes"][po] += c["poids_j"]
                    f["cotes"][co] += c["poids_j"]
                self.equipe_de[k] = c["equipe"]

        # disponibilité : présence sur les derniers matchs de l'équipe
        par_equipe = defaultdict(list)
        for c in self.camps:
            par_equipe[c["equipe"]].append(c)
        self.dispo = {}
        for eq, cs in par_equipe.items():
            cs.sort(key=lambda c: c["date"], reverse=True)
            recents = cs[:MATCHS_DISPO]
            compte = defaultdict(int)
            for c in recents:
                for p in c["joueurs"]:   # joueurs entrés en jeu
                    compte[cle(p["joueur"])] += 1
            for k, v in compte.items():
                self.dispo[k] = v / len(recents)

    def poste_probable(self, k: str) -> tuple[str | None, str | None]:
        f = self.joueurs.get(k)
        if not f or not f["postes"]:
            return (None, None)
        po = max(f["postes"].items(), key=lambda x: x[1])[0]
        co = max(f["cotes"].items(), key=lambda x: x[1])[0] if f["cotes"] else None
        return (po, co)

    def minutes_attendues(self, k: str, poste: str | None, j: dict) -> float:
        """Minutes que ce joueur passera sur le terrain S'IL entre en jeu."""
        if self.sans_minutes:
            return DUREE
        if j.get("minutes") is not None:
            return float(j["minutes"])
        f = self.joueurs.get(k)
        if f and f["poids_min"] > 0:
            return f["minutes"] / f["poids_min"]
        if j.get("titulaire") and poste:
            return self.minutes_bucket.get(poste, DUREE) if poste != "REM" else DUREE
        if poste:
            return self.minutes_bucket.get(poste, DUREE)
        return self.minutes_moyennes

    def buckets_du_camp(self, joueurs: list[dict], positionnel: bool) -> list[str | None]:
        """Poste de chaque joueur : le maillot si la feuille est positionnelle,
        sinon le poste habituel du joueur s'il est connu par ailleurs."""
        if self.sans_poste:
            return [None] * len(joueurs)
        sortie = []
        for j in joueurs:
            nom = j.get("joueur") or j.get("nom")
            if positionnel and j.get("maillot") not in (None, ""):
                sortie.append(postes.depuis_maillot(j["maillot"])[0])
            else:
                sortie.append(self._poste_habituel.get(cle(nom)))
        return sortie

    def parts_du_camp(self, joueurs: list[dict], positionnel: bool,
                      buckets: list | None = None,
                      minutes: list | None = None) -> list[float]:
        """Part de chaque joueur dans les essais de l'équipe, avant son historique.

        Produit d'un taux par minute (celui de son poste) et du temps de jeu
        attendu. Les deux quantités sont additives, donc la normalisation
        suffit : plus besoin de répartir un « reste » entre les inconnus.
        """
        n = len(joueurs) or 1
        if buckets is None:
            buckets = self.buckets_du_camp(joueurs, positionnel)
        if minutes is None:
            minutes = [self.minutes_attendues(cle(j.get("joueur") or j.get("nom")),
                                              b, j)
                       for j, b in zip(joueurs, buckets)]
        brut = []
        for b, m in zip(buckets, minutes):
            taux = (self.taux_bucket.get(b) if b else None) or self.taux_moyen
            brut.append(max(taux, 1e-9) * max(m, 1.0))
        s = sum(brut)
        return [x / s for x in brut] if s > 0 else [1.0 / n] * n

    def multiplicateur(self, k: str) -> float:
        """Combien de fois plus (ou moins) que sa place ce joueur marque.

        Régularisé vers 1,0 : un joueur inconnu vaut exactement sa place.
        """
        f = self.joueurs.get(k)
        if not f:
            return 1.0
        return (f["essais"] + K_JOUEUR) / (f["attendus"] + K_JOUEUR)

    # ------------------------------------------------------------------
    # Étage 3 : à quels postes une défense encaisse
    # ------------------------------------------------------------------
    def _ajuster_defenses(self):
        enc = defaultdict(lambda: defaultdict(float))
        enc_c = defaultdict(lambda: defaultdict(float))
        tot = defaultdict(float)
        for c in self.camps:
            if not c["positionnel"]:
                continue
            d = c["adversaire"]
            for e in c["essais"]:
                po, co = postes.depuis_maillot(e.get("maillot"))
                enc[d][po] += c["poids"]
                enc_c[d][co] += c["poids"]
                tot[d] += c["poids"]
        self.ratio_poste, self.ratio_cote = {}, {}
        for d, total in tot.items():
            for p in postes.POSTES:
                base = self.part_bucket.get(p, 0.0)
                if base <= 0:
                    continue
                part = (enc[d].get(p, 0.0) + K_DEFENSE * base) / (total + K_DEFENSE)
                self.ratio_poste[(d, p)] = part / base
            for p in postes.COTES:
                base = self.part_bucket_cote.get(p, 0.0)
                if base <= 0:
                    continue
                part = (enc_c[d].get(p, 0.0) + K_COTE * base) / (total + K_COTE)
                self.ratio_cote[(d, p)] = part / base

    def faiblesse(self, defense, poste, cote) -> float:
        r = 1.0
        if not self.sans_defense and poste:
            r *= self.ratio_poste.get((defense, poste), 1.0)
        if not self.sans_cote and cote:
            r *= self.ratio_cote.get((defense, cote), 1.0)
        return r

    # ------------------------------------------------------------------
    # Prédiction
    # ------------------------------------------------------------------
    def predire_camp(self, equipe, adversaire, tournoi, dom, effectif,
                     positionnel=None) -> list[dict]:
        """effectif : liste de {nom, maillot?, banc?}. Renvoie une ligne par joueur."""
        if positionnel is None:
            positionnel = postes.numerotation_positionnelle(
                [{"maillot": j.get("maillot"), "banc": j.get("banc")} for j in effectif])
        attendus = self.essais_attendus(equipe, adversaire, tournoi, dom)
        buckets = self.buckets_du_camp(effectif, positionnel)
        minutes = [self.minutes_attendues(cle(j["nom"]), b, j)
                   for j, b in zip(effectif, buckets)]
        places = self.parts_du_camp(effectif, positionnel, buckets, minutes)

        lignes = []
        for j, place, po, mn in zip(effectif, places, buckets, minutes):
            k = cle(j["nom"])
            if positionnel and j.get("maillot") not in (None, ""):
                co = postes.depuis_maillot(j["maillot"])[1]
            else:
                co = self._cote_habituelle.get(k)
            mult = self.multiplicateur(k)
            fai = self.faiblesse(adversaire, po, co)
            dispo = 1.0 if j.get("titulaire") else self.dispo.get(k, 0.5)
            f = self.joueurs.get(k)
            lignes.append({
                "nom": j["nom"],
                "cle": k,
                "maillot": j.get("maillot"),
                "poste": po,
                "cote": co,
                "place": place,
                "minutes": round(mn),
                "multiplicateur": mult,
                "faiblesse": fai,
                "dispo": dispo,
                "poids_brut": place * mult * fai,
                "matchs_connus": f["matchs"] if f else 0,
                "essais_connus": round(f["essais"], 1) if f else 0.0,
            })

        # Une équipe fait entrer ~17 joueurs. Le bookmaker en cote 20 : sans
        # recalage, la somme des chances de jouer valait 11 sur 20 (beaucoup de
        # joueurs inconnus du modèle) et toutes les probabilités partaient de
        # travers. On met donc la somme des disponibilités au bon niveau.
        cible_terrain = min(SUR_LE_TERRAIN, float(len(lignes)))
        brut = sum(l["dispo"] for l in lignes)
        if brut > 0 and abs(brut - cible_terrain) > 0.5:
            bas, haut = 0.05, 20.0
            for _ in range(50):
                mid = (bas + haut) / 2
                s = sum(min(1.0, mid * l["dispo"]) for l in lignes)
                if s > cible_terrain:
                    haut = mid
                else:
                    bas = mid
            f = (bas + haut) / 2
            for l in lignes:
                l["dispo"] = min(1.0, f * l["dispo"])

        # Compression : le modèle sépare un peu trop les joueurs (mesuré, les
        # probabilités hautes sortaient au-dessus du réel et les basses en
        # dessous). On resserre les écarts, puis on remet la somme au niveau du
        # total attendu de l'équipe — ce total, lui, n'est pas touché.
        for l in lignes:
            l["poids"] = max(l["poids_brut"], 1e-9) ** COMPRESSION * l["dispo"]
        somme = sum(l["poids"] for l in lignes) or 1.0
        for l in lignes:
            l["part"] = l["poids"] / somme
            l["lambda"] = attendus * l["part"]
            # Les paris « marqueur d'essai » sont remboursés si le joueur
            # n'entre pas en jeu : la probabilité utile est donc conditionnée
            # au fait qu'il joue, et non pondérée par sa chance d'être aligné.
            l["lambda_si_joue"] = l["lambda"] / max(l["dispo"], 0.05)
            lam = l["lambda_si_joue"]
            l["p_essai"] = 1.0 - math.exp(-lam)
            l["p_double"] = 1.0 - math.exp(-lam) * (1.0 + lam)
            l["essais_equipe"] = attendus
        lignes.sort(key=lambda l: -l["p_essai"])
        return lignes
