"""Rapport HTML : une page unique, lisible, sans dépendance."""

from __future__ import annotations

import datetime
import html
import os

from . import postes

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rapports")

CSS = """
:root{--fond:#f6f7f9;--carte:#fff;--texte:#15181d;--doux:#6b7280;--trait:#e5e7eb;
--vert:#0f7b4f;--vertf:#e7f6ee;--orange:#a35a00;--orangef:#fdf3e3;--gris:#eef0f3;--rouge:#b3261e;--rougef:#fdecea}
@media(prefers-color-scheme:dark){:root{--fond:#0f1216;--carte:#171b21;--texte:#e8eaed;--doux:#9aa3ae;
--trait:#262c34;--vert:#4ade80;--vertf:#12291d;--orange:#fbbf24;--orangef:#2a2110;--gris:#1e242b;--rouge:#f87171;--rougef:#2a1414}}
*{box-sizing:border-box}
body{margin:0;padding:20px;background:var(--fond);color:var(--texte);
font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
.page{max-width:1080px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
.sous{color:var(--doux);font-size:13px;margin-bottom:20px}
.carte{background:var(--carte);border:1px solid var(--trait);border-radius:12px;
padding:16px 18px;margin-bottom:14px}
.bandeau{border-left:4px solid var(--rouge);background:var(--rougef);color:var(--texte);
padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:14px}
.info{border-left:4px solid var(--orange);background:var(--orangef)}
.entete{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
.entete h2{font-size:17px;margin:0}
.tag{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--doux)}
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.04em;
color:var(--doux);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--trait)}
td{padding:7px 8px;border-bottom:1px solid var(--trait)}
tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pastille{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;font-weight:600}
.p-conseille{background:var(--vertf);color:var(--vert)}
.p-verifier{background:var(--orangef);color:var(--orange)}
.p-rien{background:var(--gris);color:var(--doux)}
.p-desaccord{background:var(--rougef);color:var(--rouge)}
.mini{font-size:12px;color:var(--doux)}
.barre{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px}
.stat{background:var(--carte);border:1px solid var(--trait);border-radius:10px;padding:10px 14px;flex:1;min-width:130px}
.stat b{display:block;font-size:20px;font-variant-numeric:tabular-nums}
.stat span{font-size:11px;color:var(--doux);text-transform:uppercase;letter-spacing:.04em}
.repli{margin-top:10px}
summary{cursor:pointer;color:var(--doux);font-size:13px}
.archives{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 18px}
.archives a{font-size:12px;padding:4px 10px;border-radius:99px;text-decoration:none;
background:var(--carte);border:1px solid var(--trait);color:var(--doux)}
.archives a:hover{border-color:var(--doux);color:var(--texte)}
.archives a.actif{background:var(--texte);color:var(--fond);border-color:var(--texte)}
.scroll{overflow-x:auto}
footer{color:var(--doux);font-size:12px;margin:24px 0 8px;line-height:1.6}
"""

PASTILLES = {
    "conseille": ("pari conseillé", "p-conseille"),
    "verifier": ("à vérifier", "p-verifier"),
    "rien": ("rien à prendre", "p-rien"),
    "desaccord": ("désaccord", "p-desaccord"),
    "aucune": ("pas de cote", "p-rien"),
}


def _e(x):
    return html.escape(str(x))


def _pc(x):
    return "—" if x is None else f"{x:.0%}"


def _heure(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return t.astimezone().strftime("%a %d/%m %H:%M")
    except ValueError:
        return iso


def _ligne(l: dict) -> str:
    lib, classe = PASTILLES.get(l.get("verdict", "rien"), PASTILLES["rien"])
    poste = postes.NOMS.get(l.get("poste"), "—") if l.get("poste") else "—"
    gain = l.get("gain")
    gain_txt = f"{gain:+.0%}" if gain is not None and l.get("cote") else "—"
    alerte = ""
    if l.get("dispo", 1) < 0.6:
        alerte = " <span class='mini'>· titulaire incertain</span>"
    return f"""<tr>
<td>{_e(l['nom'])}{alerte}<div class='mini'>{_e(poste)} · {l['matchs_connus']} matchs connus</div></td>
<td class='num'>{_pc(l['p_essai'])}</td>
<td class='num'>{_pc(l.get('p_marche'))}</td>
<td class='num'>{('%.2f' % l['cote']) if l.get('cote') else '—'}</td>
<td class='num'>{gain_txt}</td>
<td><span class='pastille {classe}'>{lib}</span><div class='mini'>{_e(l.get('motif',''))}</div></td>
</tr>"""


def _camp(camp: dict, complet: bool) -> str:
    lignes = camp["lignes"]
    vedettes = [l for l in lignes if l.get("verdict") in ("conseille", "verifier")]
    autres = [l for l in lignes if l not in vedettes]
    marche = camp.get("essais_marche")
    detail = (f"marché {marche:.1f} essais" if marche
              else f"modèle {camp['essais_modele']:.1f} essais (pas de cote de total)")
    corps = f"""<div class='entete'><h2>{_e(camp['nom'])}</h2>
<span class='tag'>{'domicile' if camp['dom'] else 'extérieur'} · {detail}</span></div>
<div class='scroll'><table>
<tr><th>joueur</th><th class='num'>modèle</th><th class='num'>marché</th>
<th class='num'>cote</th><th class='num'>avantage</th><th>verdict</th></tr>
{''.join(_ligne(l) for l in (vedettes or lignes[:6]))}
</table></div>"""
    if vedettes and autres:
        corps += (f"<details class='repli'><summary>voir les {len(autres)} autres joueurs"
                  f"</summary><div class='scroll'><table>"
                  f"{''.join(_ligne(l) for l in autres)}</table></div></details>")
    return corps


def _archives(liste, courant) -> str:
    """Bandeau de liens vers les rapports des jours précédents."""
    if not liste:
        return ""
    liens = []
    for jour, fichier in liste:
        try:
            libelle = datetime.date.fromisoformat(jour).strftime("%d/%m")
        except ValueError:
            libelle = jour
        actif = " class='actif'" if jour == courant else ""
        liens.append(f"<a href='{_e(fichier)}'{actif}>{libelle}</a>")
    return "<nav class='archives'>" + "".join(liens) + "</nav>"


def construire(analyses: list[dict], bilan: dict, alerte: str | None = None,
               avertissements: list[str] | None = None,
               archives: list | None = None, jour: str | None = None) -> str:
    conseils = [l for a in analyses for c in a["camps"] for l in c["lignes"]
                if l.get("verdict") == "conseille"]
    maintenant = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")

    tetes = []
    if alerte:
        tetes.append(f"<div class='bandeau'>{_e(alerte)}</div>")
    for a in (avertissements or []):
        tetes.append(f"<div class='bandeau info'>{_e(a)}</div>")

    reussite = ("—" if bilan["reussite"] is None
                else f"{bilan['reussite']:.0%}")
    roi = "—" if bilan["roi"] is None else f"{bilan['roi']:+.1%}"
    barre = f"""<div class='barre'>
<div class='stat'><b>{len(analyses)}</b><span>matchs analysés</span></div>
<div class='stat'><b>{len(conseils)}</b><span>paris conseillés</span></div>
<div class='stat'><b>{bilan['tranches']}</b><span>conseils tranchés</span></div>
<div class='stat'><b>{reussite}</b><span>réussite</span></div>
<div class='stat'><b>{roi}</b><span>rendement</span></div>
</div>"""

    corps = []
    for a in analyses:
        titre = f"{a['rencontre']} <span class='tag'>{_e(a['competition'])} · {_heure(a['debut'])}</span>"
        tot = ""
        if a.get("total_marche"):
            tot = (f"total du match : marché {a['total_marche']:.1f} essais, "
                   f"modèle {a['total_modele']:.1f}")
        elif a.get("total_modele"):
            tot = f"total du match : modèle {a['total_modele']:.1f} essais"
        corps.append(f"<div class='carte'><div class='entete'><h2>{titre}</h2>"
                     f"<span class='tag'>{_e(tot)}</span></div>"
                     + "".join(f"<div style='margin-top:14px'>{_camp(c, True)}</div>"
                               for c in a["camps"]) + "</div>")

    derniers = ""
    if bilan["derniers"]:
        rangs = "".join(
            f"<tr><td>{'✅' if f['resultat'] == 'gagne' else '❌'} {_e(f['joueur'])}"
            f"<div class='mini'>{_e(f['match'])}</div></td>"
            f"<td class='num'>{f['cote']:.2f}</td>"
            f"<td class='num'>{f['p_modele']:.0%}</td></tr>"
            for f in bilan["derniers"])
        derniers = (f"<div class='carte'><h2 style='font-size:17px;margin:0'>Derniers conseils tranchés</h2>"
                    f"<div class='scroll'><table><tr><th>conseil</th><th class='num'>cote</th>"
                    f"<th class='num'>annoncé</th></tr>{rangs}</table></div></div>")

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marqueurs XIII — {maintenant}</title><style>{CSS}</style></head><body><div class="page">
<h1>Marqueurs d'essai — rugby à XIII</h1>
<div class="sous">Généré le {maintenant} · cotes Unibet (offre publique Kambi) · NRL et Super League</div>
{_archives(archives or [], jour or datetime.date.today().isoformat())}
{''.join(tetes)}
{barre}
{''.join(corps) if corps else "<div class='carte'>Aucun match coté pour le moment.</div>"}
{derniers}
<footer>
Les probabilités « modèle » sont conditionnées au fait que le joueur entre en jeu : c'est ainsi
que se règlent les paris marqueur d'essai (remboursés si le joueur ne joue pas).<br>
La colonne « marché » est la cote débarrassée de la marge du bookmaker, ramenée au total
d'essais que ce même bookmaker attend du match.<br>
Mesure du modèle hors échantillon (33 304 prédictions, réentraînement mensuel) : perte
logarithmique 0,446 contre 0,496 pour une simple moyenne, biais de niveau 0,991.
Il est calibré, pas devin — et il n'a JAMAIS été confronté à des cotes passées.<br>
Un avantage affiché n'est pas de l'argent gagné. Mises plates et petites, jeu responsable.
</footer>
</div></body></html>"""


JOURS_ARCHIVES = 14


def archives_disponibles(jour_courant: str | None = None) -> list[tuple[str, str]]:
    """Les derniers rapports déjà écrits, du plus récent au plus ancien."""
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
