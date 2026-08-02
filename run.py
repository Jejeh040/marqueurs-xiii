"""Point d'entrée : met à jour la base, relève les cotes, écrit le rapport.

    python run.py            met à jour, analyse, publie le site, ouvre le rapport
    python run.py --muet     idem sans ouvrir le navigateur (tâche planifiée)
    python run.py --sans-site   ne publie pas sur GitHub Pages
    python run.py --hors-ligne  n'interroge pas SofaScore, réutilise la base
"""

from __future__ import annotations

import datetime
import os
import sys
import time
import webbrowser

from src import historique, journal, kambi, model, pages, report, sofascore, valeur

RACINE = os.path.dirname(os.path.abspath(__file__))


class _Tee:
    """Écrit à la fois sur la sortie standard et dans le journal du jour.

    La tâche planifiée lance python directement (pas un .bat) : sans cette
    recopie, il ne resterait aucune trace des lancements automatiques.
    """

    def __init__(self, flux, fichier):
        self.flux, self.fichier = flux, fichier

    def write(self, texte):
        self.flux.write(texte)
        self.fichier.write(texte)

    def flush(self):
        self.flux.flush()
        self.fichier.flush()


def _journaliser():
    dossier = os.path.join(RACINE, "logs")
    os.makedirs(dossier, exist_ok=True)
    f = open(os.path.join(dossier, "quotidien.log"), "a", encoding="utf-8")
    f.write("\n===== " + time.strftime("%Y-%m-%d %H:%M:%S") + " =====\n")
    sys.stdout = _Tee(sys.stdout, f)
    sys.stderr = _Tee(sys.stderr, f)


def preparer(hors_ligne: bool = False):
    if not hors_ligne:
        print("1. Mise à jour de la base de matchs")
        historique.completer()
        historique.reparer_remplacements()
    matchs = historique.charger()
    print(f"   base : {len(matchs)} matchs exploitables")
    print("2. Entraînement du modèle")
    mdl = model.Modele(matchs)
    print(f"   {len(mdl.equipes)} équipes, {len(mdl.joueurs)} joueurs connus"
          + ("" if mdl.convergence else "  (⚠ ajustement non convergé)"))
    return matchs, mdl


def analyser(matchs, mdl, hors_ligne=False):
    print("3. Relevé des cotes")
    releve = kambi.releve()
    if releve.get("erreur"):
        print("   ⚠", releve["erreur"])
    print(f"   {len(releve['matchs'])} matchs cotés")

    annuaire = valeur.annuaire_equipes(matchs)
    kambi_vers_tournoi = {c["kambi"]: t for t, c in sofascore.COMPETITIONS.items()}
    calendrier = {} if hors_ligne else _calendrier()

    analyses, inconnus, hors_perimetre = [], [], []
    for r in sorted(releve["matchs"].values(), key=lambda x: x.get("debut") or ""):
        tournoi = kambi_vers_tournoi.get(r["groupe"])
        if tournoi is None:
            hors_perimetre.append(r["groupe"])
            continue
        dom = annuaire.get((tournoi, valeur._cle_equipe(r["dom"])))
        ext = annuaire.get((tournoi, valeur._cle_equipe(r["ext"])))
        if not dom or not ext:
            inconnus.append(r["nom"])
            continue
        prevu = calendrier.get((valeur._cle_equipe(r["dom"]),
                                valeur._cle_equipe(r["ext"])))
        compo = None
        if prevu:
            try:
                compo = sofascore.compositions(prevu["id"])
            except Exception:
                compo = None
        a = valeur.analyser_match(mdl, r, dom, ext, tournoi, compo)
        if prevu:
            a["sofa"] = prevu["id"]
            a["date_match"] = prevu["date"]
        a["rencontre"] = r["nom"]
        a["competition"] = sofascore.COMPETITIONS[tournoi]["nom"]
        a["debut"] = r["debut"]
        a["event_kambi"] = r["id"]
        analyses.append(a)
    return analyses, inconnus, releve, sorted(set(hors_perimetre))


def _calendrier():
    """Matchs SofaScore à venir, indexés par (équipe reçue, équipe visiteuse)."""
    try:
        prochains = historique.a_venir()
    except Exception as exc:
        print("   ⚠ calendrier SofaScore injoignable :", exc)
        return {}
    return {(valeur._cle_equipe(p["dom_nom"]), valeur._cle_equipe(p["ext_nom"])): p
            for p in prochains}


def main():
    args = set(sys.argv[1:])
    if "--muet" in args:
        _journaliser()
    debut = time.time()
    hors_ligne = "--hors-ligne" in args
    matchs, mdl = preparer(hors_ligne)
    analyses, inconnus, releve, hors_perimetre = analyser(matchs, mdl, hors_ligne)

    print("4. Suivi des conseils passés")
    if not hors_ligne:
        try:
            n = journal.regler()
            print(f"   {n} conseil(s) tranché(s)")
        except Exception as exc:
            print("   ⚠ règlement impossible :", exc)
        for a in analyses:
            if not a.get("sofa"):
                continue
            for camp in a["camps"]:
                journal.enregistrer(a["event_kambi"], {
                    "sofa": a.get("sofa"),
                    "competition": a["competition"],
                    "match": a["rencontre"],
                    "date_match": a.get("date_match"),
                    "equipe": camp["nom"],
                }, camp["lignes"])

    avertissements = []
    if releve.get("erreur"):
        avertissements.append(releve["erreur"])
    if inconnus:
        avertissements.append(
            "Non analysés faute d'historique : " + ", ".join(inconnus[:6])
            + (" …" if len(inconnus) > 6 else ""))
    if hors_perimetre:
        avertissements.append(
            "Compétitions cotées mais hors périmètre (" + ", ".join(hors_perimetre)
            + ") : SofaScore n'y publie aucune composition d'équipe, "
            "le modèle ne peut pas savoir qui joue.")
    sans_total = [a["rencontre"] for a in analyses if not a.get("total_marche")]
    if sans_total:
        avertissements.append(
            f"{len(sans_total)} match(s) sans cote de total d'essais (Super League) : "
            "le modèle y estime seul le nombre d'essais, ses probabilités y sont "
            "moins sûres.")

    alerte = valeur.penchant(analyses)
    print("5. Rapport")
    jour = datetime.date.today().isoformat()
    chemin = report.ecrire(report.construire(
        analyses, journal.bilan(), alerte, avertissements,
        report.archives_disponibles(jour), jour), jour)
    conseils = sum(1 for a in analyses for c in a["camps"] for l in c["lignes"]
                   if l.get("verdict") == "conseille")
    print(f"   {conseils} pari(s) conseillé(s) — {chemin}")

    if "--sans-site" not in args:
        print("6. Publication du site")
        pages.publier()

    print(f"   terminé en {time.time() - debut:.0f} s")
    if "--muet" not in args:
        webbrowser.open("file:///" + chemin.replace("\\", "/"))


if __name__ == "__main__":
    main()
