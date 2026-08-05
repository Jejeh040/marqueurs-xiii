"""Pages HTML du site : le rapport du jour et le tableau des cotes.

Même charte que le site « aces » de Jeremy (src/theme.py) : synthèse en haut,
une carte par match, distribution du nombre d'essais, tableaux en chasse fixe,
thème clair/sombre.
"""

from __future__ import annotations

import datetime
import html
import math
import os

from . import postes, theme

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "rapports")
JOURS_ARCHIVES = 14

VERDICTS = {
    "conseille": ("pari conseillé", "oui"),
    "verifier": ("à vérifier", "verifier"),
    "rien": ("rien à prendre", "non"),
    "desaccord": ("désaccord", "ecart"),
    "aucune": ("pas de cote", "non"),
}


def _e(x):
    return html.escape(str(x if x is not None else ""))


def _pc(x, vide="—"):
    return vide if x is None else f"{x:.0%}"


def _heure(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return t.astimezone().strftime("%a %d/%m à %Hh%M")
    except ValueError:
        return iso


def _page(titre: str, corps: str, scripts: str = "") -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{_e(titre)}</title>
<style>{theme.CSS}</style></head><body><div class="wrap">
{corps}
</div><script>{theme.BASCULE}{scripts}</script></body></html>"""


def _entete(titre: str, sous: str, page: str, archives=None, jour=None) -> str:
    liens = [
        ("index.html", "Rapport du jour", page == "rapport"),
        ("cotes.html", "Toutes les cotes", page == "cotes"),
    ]
    barre = "".join(
        f"<a class='lien{" actif" if actif else ""}' href='{href}'>{_e(lib)}</a>"
        for href, lib, actif in liens)
    arch = ""
    if archives:
        courant = jour or datetime.date.today().isoformat()
        liens_j = []
        for j, fichier in archives:
            try:
                lib = datetime.date.fromisoformat(j).strftime("%d/%m")
            except ValueError:
                lib = j
            actif = " actif" if j == courant else ""
            liens_j.append(f"<a class='{actif.strip()}' href='{_e(fichier)}'>{lib}</a>")
        arch = "<nav class='archives'>" + "".join(liens_j) + "</nav>"
    return f"""<header class="tete">
<p class="eyebrow">Rugby à XIII · NRL &amp; Super League</p>
<h1>{_e(titre)}</h1>
<p class="sous">{sous}</p>
<div class="barre-liens">{barre}
<button class="lien bascule" id="bascule" type="button">Thème sombre</button></div>
</header>{arch}"""


# --------------------------------------------------------------------------
# Distribution du nombre d'essais
# --------------------------------------------------------------------------

def _distribution(lam: float, ligne: float | None) -> str:
    """Loi de Poisson du total d'essais, avec la ligne du bookmaker en repère."""
    if not lam or lam <= 0:
        return ""
    # Recadré sur les 1 %-99 % : au-delà les barres sont invisibles et écrasent
    # l'échelle utile.
    toutes, terme, k = [], math.exp(-lam), 0
    while k < 60:
        toutes.append(terme)
        terme *= lam / (k + 1)
        k += 1
    cumul, bas, haut = 0.0, 0, len(toutes) - 1
    for i, p in enumerate(toutes):
        cumul += p
        if cumul < 0.01:
            bas = i + 1
        if cumul > 0.99:
            haut = i
            break
    probas = toutes[bas:haut + 1]
    sommet = max(probas) or 1.0
    mode = bas + probas.index(sommet)
    barres = []
    for i, p in enumerate(probas):
        k = bas + i
        classe = "barre"
        if ligne is not None and k > ligne:
            classe += " dedans"
        if k == mode:
            classe += " pivot"
        h = max(2, round(100 * p / sommet))
        titre = f"{k} essais : {p:.0%}"
        barres.append(f"<div class='{classe}' style='height:{h}%' title='{titre}'></div>")
    au_dessus = ""
    if ligne is not None:
        p = sum(x for i, x in enumerate(toutes) if i > ligne)
        au_dessus = f" · plus de {ligne:g} essais : {p:.0%}"
    return f"""<div class="distribution">
<p class="dist-titre">Total d'essais attendu — sommet à {mode}{au_dessus}</p>
<div class="barres">{''.join(barres)}</div>
<div class="echelle"><span>{bas}</span><span>{haut}</span></div></div>"""


# --------------------------------------------------------------------------
# Tableau des joueurs d'une équipe
# --------------------------------------------------------------------------

def _rang(l: dict) -> str:
    lib, classe = VERDICTS.get(l.get("verdict", "rien"), VERDICTS["rien"])
    poste = postes.NOMS.get(l.get("poste")) if l.get("poste") else None
    detail = []
    if poste:
        detail.append(poste)
    detail.append(f"{l['matchs_connus']} matchs connus")
    if l.get("dispo", 1) < 0.6:
        detail.append("titulaire incertain")
    gain = l.get("gain")
    if l.get("cote") and gain is not None:
        classe_gain = "gain" if gain > 0 else "perte"
        avantage = f"<span class='{classe_gain}'>{gain:+.0%}</span>"
    else:
        avantage = "—"
    pivot = " class='pivot'" if l.get("verdict") == "conseille" else ""
    return f"""<tr{pivot}><td>{_e(l['nom'])}<span class="det">{_e(' · '.join(detail))}</span></td>
<td>{_pc(l['p_essai'])}</td><td>{_pc(l.get('p_marche'))}</td>
<td>{('%.2f' % l['cote']) if l.get('cote') else '—'}</td>
<td>{avantage}</td>
<td><span class="marque {classe}">{lib}</span></td></tr>"""


VISIBLES = 8


def _tableau(camp: dict) -> str:
    """Les joueurs du plus probable au moins probable.

    Trier par « valeur » plaçait un troisième ligne remplaçant en tête et
    reléguait l'ailier à 60 % derrière un repli : la première question est
    « qui va marquer », pas « où est l'écart avec la cote ».
    """
    lignes = sorted(camp["lignes"], key=lambda l: -l["p_essai"])
    tete = lignes[:VISIBLES]
    reste = [l for l in lignes if l not in tete]
    detail = (f"marché {camp['essais_marche']:.1f} essais"
              if camp.get("essais_marche")
              else f"modèle {camp['essais_modele']:.1f} essais")
    if camp.get("marge"):
        detail += f" · marge du book {camp['marge'] - 1:.0%}"
    corps = f"""<div class="marche">{_e(camp['nom'])}
<span class="det">{'domicile' if camp['dom'] else 'extérieur'} · {detail}</span></div>
<div class="defilement"><table>
<thead><tr><th>joueur</th><th>modèle</th><th>marché</th><th>cote</th>
<th>avantage</th><th>verdict</th></tr></thead>
<tbody>{''.join(_rang(l) for l in tete)}</tbody></table></div>"""
    if reste:
        corps += (f"<details><summary>voir les {len(reste)} autres joueurs</summary>"
                  f"<div class='defilement'><table><tbody>"
                  f"{''.join(_rang(l) for l in reste)}</tbody></table></div></details>")
    return corps


def _carte(a: dict) -> str:
    dom = a["camps"][0] if a["camps"] else None
    ext = a["camps"][1] if len(a["camps"]) > 1 else None
    affiche = (f"{_e(dom['nom'])}<span class='contre'>—</span>{_e(ext['nom'])}"
               if dom and ext else _e(a["rencontre"]))
    chiffres = []
    if a.get("total_marche"):
        chiffres.append(("essais attendus", f"{a['total_marche']:.1f}", True))
        chiffres.append(("estimation du modèle", f"{a['total_modele']:.1f}", False))
    else:
        chiffres.append(("essais attendus (modèle)", f"{a['total_modele']:.1f}", True))
    for c in a["camps"]:
        chiffres.append((c["nom"], f"{c['essais_retenus']:.1f}", False))
    cases = "".join(
        f"<div class='ch{' majeur' if maj else ''}'><dt>{_e(t)}</dt><dd>{v}</dd></div>"
        for t, v, maj in chiffres)

    ligne = None
    if a.get("total_marche"):
        ligne = round(a["total_marche"]) - 0.5
    dist = _distribution(a.get("total_marche") or a.get("total_modele"), ligne)

    compo = ("compositions officielles" if a.get("compo_officielle")
             else "effectifs annoncés par le bookmaker")
    return f"""<article class="match">
<div class="match-tete">
<div class="contexte"><span class="circuit">{_e(a['competition'])}</span>
{_e(_heure(a.get('debut')))} · {compo}</div>
<h2 class="affiche">{affiche}</h2></div>
<dl class="chiffres">{cases}</dl>
{dist}
{''.join(_tableau(c) for c in a['camps'])}
</article>"""


# --------------------------------------------------------------------------
# Page principale
# --------------------------------------------------------------------------

FAVORIS = 14


def _favoris_du_jour(analyses) -> str:
    """Qui a le plus de chances de marquer aujourd'hui, tous matchs confondus."""
    tout = [(a, c, l) for a in analyses for c in a["camps"] for l in c["lignes"]
            if l.get("dispo", 1) >= 0.5]
    if not tout:
        return ""
    tout.sort(key=lambda x: -x[2]["p_essai"])
    rangs = []
    for a, c, l in tout[:FAVORIS]:
        cote = f"{l['cote']:.2f}" if l.get("cote") else "—"
        badge = ""
        if l.get("verdict") == "conseille":
            badge = " <span class='marque oui'>value</span>"
        rangs.append(f"""<div class="sur">
<div class="sur-proba">{l['p_essai']:.0%}</div>
<div class="sur-quoi"><b>{_e(l['nom'])}</b>{badge}
<small>{_e(postes.NOMS.get(l.get('poste'), '') or 'poste inconnu')} · {_e(c['nom'])}</small></div>
<div class="sur-match">{_e(a['rencontre'])}<small>{_e(a['competition'])} ·
{_e(_heure(a.get('debut')))}</small></div>
<div class="sur-cote">cote<b>{cote}</b></div></div>""")
    return f"""<section class="bilan surs"><div class="bilan-tete">
<h2>Les plus gros favoris à l'essai</h2>
<p>Classement par chance de marquer, tous les matchs du jour confondus. C'est la
réponse à « qui va marquer ». Attention : les favoris évidents sont aussi ceux que
le bookmaker cote le mieux — fort ne veut pas dire rentable.</p></div>
{''.join(rangs)}</section>"""


def _conseils_du_jour(analyses) -> str:
    conseils = []
    for a in analyses:
        for c in a["camps"]:
            for l in c["lignes"]:
                if l.get("verdict") == "conseille":
                    conseils.append((a, c, l))
    if not conseils:
        return """<section class="bilan"><div class="bilan-tete">
<h2>Aucun écart exploitable avec la cote</h2>
<p>Le modèle est d'accord avec le bookmaker partout aujourd'hui. C'est le cas le
plus fréquent, et de loin le plus sain sur un marché aussi chargé en marge.</p>
</div></section>"""
    conseils.sort(key=lambda x: -(x[2].get("gain") or 0))
    rangs = "".join(f"""<div class="sur">
<div class="sur-proba">{l['p_essai']:.0%}</div>
<div class="sur-quoi"><b>{_e(l['nom'])}</b>
<small>{_e(postes.NOMS.get(l.get('poste'), '') or 'poste inconnu')} ·
le marché le voit à {_pc(l.get('p_marche'))}</small></div>
<div class="sur-match">{_e(c['nom'])}<small>{_e(a['rencontre'])} ·
{_e(a['competition'])}</small></div>
<div class="sur-cote">cote<b>{l['cote']:.2f}</b>{l['gain']:+.0%}</div>
</div>""" for a, c, l in conseils)
    s = "s" if len(conseils) > 1 else ""
    return f"""<section class="bilan"><div class="bilan-tete">
<h2>{len(conseils)} écart{s} avec la cote</h2>
<p>Là où le modèle donne plus de chances que le bookmaker. Ce ne sont presque
jamais les favoris : sur eux le marché est juste. Marqueur d'essai à tout moment,
remboursé si le joueur n'entre pas en jeu. Mise plate, 1 % de bankroll.</p>
</div>{rangs}</section>"""


def _journal(bilan: dict) -> str:
    if not bilan["tranches"] and not bilan["en_attente"]:
        return ""
    reussite = "—" if bilan["reussite"] is None else f"{bilan['reussite']:.0%}"
    attendue = "" if bilan["attendue"] is None else f"<small> attendu {bilan['attendue']:.0%}</small>"
    roi = bilan["roi"]
    classe = "" if roi is None else (" class='gain'" if roi > 0 else " class='perte'")
    roi_txt = "—" if roi is None else f"{roi:+.1%}"
    derniers = "".join(f"""<div class="pari">
<span class="issue {f['resultat']}">{'gagné' if f['resultat'] == 'gagne' else 'perdu'}</span>
<span class="quoi-pari"><b>{_e(f['joueur'])}</b> — {_e(f['match'])}</span>
<span class="reel">cote {f['cote']:.2f} · annoncé {f['p_modele']:.0%}</span>
</div>""" for f in bilan["derniers"]) or \
        "<p class='vide-journal'>Aucun conseil tranché pour l'instant.</p>"
    return f"""<section class="bilan"><div class="bilan-tete">
<h2>Journal des conseils</h2>
<p>Chaque conseil est enregistré puis tranché sur le résultat réel. C'est la seule
preuve que l'outil gagne ou perd de l'argent : aucun test contre des cotes passées
n'est possible faute de source gratuite.</p></div>
<dl class="synthese" style="border:none;border-radius:0">
<div class="syn"><dt>tranchés</dt><dd>{bilan['tranches']}</dd></div>
<div class="syn"><dt>gagnés</dt><dd>{bilan['gagnes']}</dd></div>
<div class="syn"><dt>réussite</dt><dd>{reussite}{attendue}</dd></div>
<div class="syn"><dt>rendement</dt><dd{classe}>{roi_txt}</dd></div>
<div class="syn"><dt>en attente</dt><dd>{bilan['en_attente']}<small> · {bilan['rembourses']} remboursés</small></dd></div>
</dl>{_verdict_journal(bilan)}{derniers}</section>"""


SEUIL_PREUVE = 100


def _verdict_journal(bilan: dict) -> str:
    """Dit en clair ce que le bilan prouve — et surtout ce qu'il ne prouve pas."""
    n = bilan["tranches"]
    if not n:
        return ""
    attendus = (bilan["attendue"] or 0) * n
    classe = "gain" if (bilan["roi"] or 0) > 0 else "perte"
    phrase = (f"<b>{bilan['gagnes']}</b> conseil{'s' if bilan['gagnes'] > 1 else ''} "
              f"gagné{'s' if bilan['gagnes'] > 1 else ''} sur {n}, "
              f"pour <b>{attendus:.1f}</b> attendus. "
              f"Bilan : <b>{bilan['gain']:+.2f}</b> unité"
              f"{'s' if abs(bilan['gain']) >= 2 else ''} de mise.")
    if n < SEUIL_PREUVE:
        phrase += (f" Sur {n} paris, ça ne prouve rien dans un sens ni dans l'autre — "
                   f"il en faut environ {SEUIL_PREUVE}.")
    return f"<p class='rendement {classe}'>{phrase}</p>"


def construire(analyses: list[dict], bilan: dict, alerte: str | None = None,
               avertissements: list[str] | None = None,
               archives: list | None = None, jour: str | None = None) -> str:
    maintenant = datetime.datetime.now().strftime("%d/%m/%Y à %Hh%M")
    conseils = sum(1 for a in analyses for c in a["camps"] for l in c["lignes"]
                   if l.get("verdict") == "conseille")

    reussite = "—" if bilan["reussite"] is None else f"{bilan['reussite']:.0%}"
    roi = bilan["roi"]
    classe_roi = "" if roi is None else (" class='gain'" if roi > 0 else " class='perte'")
    synthese = f"""<dl class="synthese">
<div class="syn"><dt>matchs analysés</dt><dd>{len(analyses)}</dd></div>
<div class="syn"><dt>paris conseillés</dt><dd>{conseils}</dd></div>
<div class="syn"><dt>conseils tranchés</dt><dd>{bilan['tranches']}</dd></div>
<div class="syn"><dt>réussite</dt><dd>{reussite}</dd></div>
<div class="syn"><dt>rendement</dt><dd{classe_roi}>{'—' if roi is None else f'{roi:+.1%}'}</dd></div>
</dl>"""

    avis = []
    if alerte:
        avis.append(f"<div class='avis grave'><p class='titre'>Signal d'alarme</p>"
                    f"<p>{_e(alerte)}</p></div>")
    for a in (avertissements or []):
        avis.append(f"<div class='avis attention'><p>{_e(a)}</p></div>")

    # un onglet par compétition
    groupes = {}
    for a in analyses:
        groupes.setdefault(a["competition"], []).append(a)
    if groupes:
        noms = list(groupes)
        onglets = "".join(
            f"<button class='onglet{' actif' if i == 0 else ''}' type='button' "
            f"data-cible='g{i}'>{_e(n)}<span>{len(groupes[n])}</span></button>"
            for i, n in enumerate(noms))
        blocs = "".join(
            f"<div class='groupe-matchs' id='g{i}'{'' if i == 0 else ' hidden'}>"
            + "".join(_carte(a) for a in groupes[n]) + "</div>"
            for i, n in enumerate(noms))
        corps_matchs = f"<nav class='onglets'>{onglets}</nav>{blocs}"
    else:
        corps_matchs = ("<div class='vide'>Aucun match coté pour le moment. "
                        "Les cotes apparaissent en général la veille.</div>")

    sous = (f"Généré le {maintenant} · cotes Unibet, offre publique Kambi")
    corps = f"""{_entete("Marqueurs d'essai", sous, "rapport", archives, jour)}
{synthese}
{''.join(avis)}
{_favoris_du_jour(analyses)}
{_conseils_du_jour(analyses)}
{corps_matchs}
{_journal(bilan)}
<footer>
Les probabilités « modèle » valent <b>si le joueur entre en jeu</b> : c'est ainsi que se
règlent ces paris, remboursés sinon.<br>
La colonne « marché » est la cote débarrassée de la marge, ramenée au total d'essais que le
bookmaker attend lui-même du match.<br>
Modèle mesuré hors échantillon sur 33 304 prédictions, réentraînement mensuel : perte
logarithmique 0,446 contre 0,496 pour une simple moyenne, biais 0,991. Calibré, pas devin —
et jamais confronté à des cotes passées.<br>
Un avantage affiché n'est pas un gain acquis. Mises plates et petites, jeu responsable.<br>
<a href="https://github.com/Jejeh040/marqueurs-xiii">Code source</a>
</footer>"""
    return _page(f"Marqueurs XIII — {maintenant}", corps, theme.ONGLETS)


# --------------------------------------------------------------------------
# Page « toutes les cotes »
# --------------------------------------------------------------------------

def construire_cotes(releve: dict) -> str:
    from . import kambi

    maintenant = datetime.datetime.now().strftime("%d/%m/%Y à %Hh%M")
    matchs = sorted(releve.get("matchs", {}).values(), key=lambda m: m.get("debut") or "")

    cartes = []
    for m in matchs:
        total = kambi.esperance_poisson(m.get("total_match") or [])
        equipes = {}
        for nom, lignes in (m.get("total_equipe") or {}).items():
            lam = kambi.esperance_poisson(lignes)
            if lam:
                equipes[nom] = lam
        chiffres = []
        if total:
            chiffres.append(("total d'essais", f"{total:.1f}", True))
        for nom, lam in equipes.items():
            chiffres.append((nom, f"{lam:.1f}", False))
        if not chiffres:
            chiffres.append(("joueurs cotés", str(len(m["joueurs"])), True))
        cases = "".join(
            f"<div class='ch{' majeur' if maj else ''}'><dt>{_e(t)}</dt><dd>{v}</dd></div>"
            for t, v, maj in chiffres)

        blocs = ""
        for dom in (True, False):
            js = [j for j in m["joueurs"] if j["dom"] == dom and j.get("cote")]
            if not js:
                continue
            js.sort(key=lambda j: j["cote"])
            rangs = "".join(f"""<tr><td>{_e(j['nom'])}</td>
<td>{j['cote']:.2f}</td><td>{1 / j['cote']:.0%}</td>
<td>{('%.2f' % j['cote_premier']) if j.get('cote_premier') else '—'}</td>
<td>{('%.2f' % j['cote_dernier']) if j.get('cote_dernier') else '—'}</td></tr>"""
                             for j in js)
            blocs += f"""<div class="marche">{_e(m['dom'] if dom else m['ext'])}
<span class="det">{len(js)} joueurs cotés</span></div>
<div class="defilement"><table>
<thead><tr><th>joueur</th><th>à tout moment</th><th>proba implicite</th>
<th>premier essai</th><th>dernier essai</th></tr></thead>
<tbody>{rangs}</tbody></table></div>"""

        cartes.append(f"""<article class="match">
<div class="match-tete">
<div class="contexte"><span class="circuit">{_e(m.get('groupe'))}</span>
{_e(_heure(m.get('debut')))}</div>
<h2 class="affiche">{_e(m.get('dom'))}<span class="contre">—</span>{_e(m.get('ext'))}</h2>
</div><dl class="chiffres">{cases}</dl>{blocs}</article>""")

    avis = ""
    if releve.get("erreur"):
        avis = f"<div class='avis attention'><p>{_e(releve['erreur'])}</p></div>"

    sous = (f"Relevé du {maintenant} · offre publique Kambi (Unibet) · "
            "toutes les compétitions cotées, modèle ou pas")
    corps = f"""{_entete("Toutes les cotes du moment", sous, "cotes")}
<div class="avis info"><p class="titre">Les cotes brutes, sans modèle</p>
<p>Cette page affiche simplement ce que le bookmaker propose, marge comprise, y compris sur
les compétitions que le modèle ne couvre pas (NRL Women, faute de compositions publiées).
La probabilité implicite est le simple inverse de la cote : elle contient la marge, elle
surestime donc toujours un peu les chances réelles.</p></div>
{avis}
{''.join(cartes) if cartes else "<div class='vide'>Aucune cote pour le moment.</div>"}
<footer>Les cotes changent en permanence ; ce relevé date de {maintenant}.<br>
<a href="index.html">Retour au rapport du jour</a> ·
<a href="https://github.com/Jejeh040/marqueurs-xiii">Code source</a></footer>"""
    return _page(f"Cotes marqueur d'essai — {maintenant}", corps)


# --------------------------------------------------------------------------
# Écriture
# --------------------------------------------------------------------------

def archives_disponibles(jour_courant: str | None = None) -> list[tuple[str, str]]:
    if not os.path.isdir(DOSSIER):
        jours = []
    else:
        jours = sorted((f[:-5] for f in os.listdir(DOSSIER)
                        if f.endswith(".html") and f[:4].isdigit()), reverse=True)
    if jour_courant and jour_courant not in jours:
        jours.insert(0, jour_courant)
    return [(j, j + ".html") for j in jours[:JOURS_ARCHIVES]]


def ecrire(contenu: str, jour: str | None = None) -> str:
    os.makedirs(DOSSIER, exist_ok=True)
    jour = jour or datetime.date.today().isoformat()
    chemin = os.path.join(DOSSIER, jour + ".html")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    with open(os.path.join(DOSSIER, "dernier.html"), "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin


def ecrire_cotes(contenu: str) -> str:
    os.makedirs(DOSSIER, exist_ok=True)
    chemin = os.path.join(DOSSIER, "cotes.html")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin
