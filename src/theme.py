"""Feuille de style commune aux pages du site.

Reprend la charte du site « aces » : neutres à légère dominante verte, thème
clair et sombre, chiffres en chasse fixe tabulaire. Les deux sites de Jeremy se
ressemblent volontairement.
"""

CSS = """
:root{
  --ground:#F5F8F6; --surface:#FFFFFF; --raised:#EEF3F0;
  --ink:#101E1A; --ink-soft:#5D706A; --ink-faint:#8A9B95;
  --line:#DFE7E2; --line-strong:#C6D3CD;
  --accent:#0B6E63; --accent-wash:rgba(11,110,99,.08);
  --over:#1A6B3C; --under:#8E4319; --warn:#7A5800; --danger:#8E2A2A;
  --warn-wash:rgba(122,88,0,.10); --danger-wash:rgba(142,42,42,.10);
  --radius:14px;
  --font-display:"Segoe UI Variable Display","Segoe UI",system-ui,-apple-system,sans-serif;
  --font-body:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,sans-serif;
  --font-data:"Cascadia Mono",ui-monospace,"SF Mono",Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root{
    --ground:#0C1211; --surface:#141C1A; --raised:#1B2523;
    --ink:#E9F0EC; --ink-soft:#9AACA5; --ink-faint:#6F817B;
    --line:#222E2B; --line-strong:#33423E;
    --accent:#4FD1C0; --accent-wash:rgba(79,209,192,.10);
    --over:#5BC98C; --under:#EE9A5D; --warn:#E4B93F; --danger:#EE8B8B;
    --warn-wash:rgba(228,185,63,.10); --danger-wash:rgba(238,139,139,.10);
  }
}
:root[data-theme="dark"]{
  --ground:#0C1211; --surface:#141C1A; --raised:#1B2523;
  --ink:#E9F0EC; --ink-soft:#9AACA5; --ink-faint:#6F817B;
  --line:#222E2B; --line-strong:#33423E;
  --accent:#4FD1C0; --accent-wash:rgba(79,209,192,.10);
  --over:#5BC98C; --under:#EE9A5D; --warn:#E4B93F; --danger:#EE8B8B;
  --warn-wash:rgba(228,185,63,.10); --danger-wash:rgba(238,139,139,.10);
}
:root[data-theme="light"]{
  --ground:#F5F8F6; --surface:#FFFFFF; --raised:#EEF3F0;
  --ink:#101E1A; --ink-soft:#5D706A; --ink-faint:#8A9B95;
  --line:#DFE7E2; --line-strong:#C6D3CD;
  --accent:#0B6E63; --accent-wash:rgba(11,110,99,.08);
  --over:#1A6B3C; --under:#8E4319; --warn:#7A5800; --danger:#8E2A2A;
  --warn-wash:rgba(122,88,0,.10); --danger-wash:rgba(142,42,42,.10);
}

*{box-sizing:border-box}
body{margin:0;padding:0;background:var(--ground);color:var(--ink);
  font:400 16px/1.55 var(--font-body);-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:32px 18px 72px;
  display:flex;flex-direction:column;gap:22px}

/* ---------- en-tete ---------- */
.tete{display:flex;flex-direction:column;gap:6px}
.eyebrow{margin:0;font:600 12px/1 var(--font-body);letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent)}
h1{margin:0;font:700 clamp(28px,5vw,40px)/1.1 var(--font-display);
  letter-spacing:-.02em;text-wrap:balance}
.sous{margin:0;color:var(--ink-soft);font-size:14px}
.barre-liens{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:2px}
.lien{font:600 12.5px/1 var(--font-body);text-decoration:none;color:var(--ink-soft);
  border:1px solid var(--line-strong);border-radius:999px;padding:7px 13px;
  background:var(--surface)}
.lien:hover{color:var(--ink);border-color:var(--ink-faint)}
.lien.actif{background:var(--accent);border-color:var(--accent);color:var(--ground)}
.bascule{appearance:none;cursor:pointer;margin-left:auto}

/* ---------- archives ---------- */
.archives{display:flex;gap:6px;flex-wrap:wrap}
.archives a{font:600 11.5px/1 var(--font-data);text-decoration:none;padding:6px 10px;
  border-radius:999px;background:var(--surface);border:1px solid var(--line);
  color:var(--ink-faint);font-variant-numeric:tabular-nums}
.archives a:hover{border-color:var(--ink-faint);color:var(--ink)}
.archives a.actif{background:var(--ink);color:var(--ground);border-color:var(--ink)}

/* ---------- barre de synthese ---------- */
.synthese{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:var(--radius);overflow:hidden;margin:0;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.syn{background:var(--surface);padding:14px 16px;display:flex;flex-direction:column;gap:3px}
.syn dt{margin:0;font:600 11px/1 var(--font-body);letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-faint)}
.syn dd{margin:0;font:600 20px/1.2 var(--font-data);font-variant-numeric:tabular-nums}
.syn dd small{font:400 13px/1 var(--font-body);color:var(--ink-soft)}
.syn dd.gain{color:var(--over)} .syn dd.perte{color:var(--under)}

/* ---------- messages ---------- */
.avis{border:1px solid var(--line);border-left-width:3px;border-radius:var(--radius);
  background:var(--surface);padding:14px 16px;font-size:14px;
  display:flex;flex-direction:column;gap:6px}
.avis p{margin:0}
.avis .titre{font-weight:650;color:var(--ink)}
.avis.info{border-left-color:var(--accent)}
.avis.attention{border-left-color:var(--warn);background:var(--warn-wash)}
.avis.grave{border-left-color:var(--danger);background:var(--danger-wash)}

/* ---------- onglets ---------- */
.onglets{display:flex;gap:8px;border-bottom:2px solid var(--line)}
.onglet{appearance:none;background:none;border:none;cursor:pointer;
  font:650 15px/1 var(--font-display);color:var(--ink-faint);padding:12px 18px;
  border-bottom:2px solid transparent;margin-bottom:-2px;
  display:inline-flex;align-items:center;gap:8px}
.onglet span{font:600 11px/1 var(--font-data);padding:3px 7px;border-radius:999px;
  background:var(--raised);color:var(--ink-soft)}
.onglet:hover{color:var(--ink-soft)}
.onglet.actif{color:var(--accent);border-bottom-color:var(--accent)}
.onglet.actif span{background:var(--accent);color:var(--ground)}
.groupe-matchs{display:flex;flex-direction:column;gap:22px}
.groupe-matchs[hidden]{display:none}

/* ---------- carte de match ---------- */
.match{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);overflow:hidden}
.match-tete{padding:18px 20px 16px;display:flex;flex-direction:column;gap:10px;
  border-bottom:1px solid var(--line)}
.contexte{display:flex;flex-wrap:wrap;align-items:center;gap:9px;
  font:500 12px/1 var(--font-body);color:var(--ink-soft)}
.circuit{font:700 11px/1 var(--font-body);letter-spacing:.1em;color:var(--accent);
  padding:3px 7px;border:1px solid color-mix(in srgb,var(--accent) 40%,transparent);
  border-radius:4px}
.affiche{margin:0;font:650 clamp(19px,3.2vw,24px)/1.25 var(--font-display);
  letter-spacing:-.01em;text-wrap:balance}
.affiche .contre{color:var(--ink-faint);font-weight:400;padding:0 6px}

/* ---------- chiffres cles ---------- */
.chiffres{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));
  gap:1px;background:var(--line);margin:0}
.ch{background:var(--surface);padding:14px 16px;display:flex;flex-direction:column;gap:2px}
.ch dt{margin:0;font:600 10.5px/1.3 var(--font-body);letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-faint)}
.ch dd{margin:0;font:600 22px/1.15 var(--font-data);font-variant-numeric:tabular-nums}
.ch.majeur dd{color:var(--accent);font-size:27px}

/* ---------- distribution ---------- */
.distribution{padding:16px 20px 12px;border-top:1px solid var(--line)}
.dist-titre{margin:0 0 10px;font:600 10.5px/1 var(--font-body);letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-faint)}
.barres{display:flex;align-items:flex-end;gap:2px;height:64px}
.barre{flex:1 1 0;background:var(--line-strong);border-radius:2px 2px 0 0;min-height:2px}
.barre.dedans{background:var(--accent);opacity:.5}
.barre.pivot{background:var(--accent);opacity:1}
.echelle{display:flex;justify-content:space-between;margin-top:6px;
  font:500 11px/1 var(--font-data);color:var(--ink-faint);font-variant-numeric:tabular-nums}

/* ---------- tableaux ---------- */
.marche{display:flex;align-items:center;gap:9px;padding:16px 20px 0;
  font:650 13px/1 var(--font-display)}
.marche::before{content:"";width:4px;height:15px;border-radius:2px;flex:none;
  background:var(--accent)}
.marche .det{font:500 11.5px/1 var(--font-body);color:var(--ink-soft);margin-left:auto}
.defilement{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px;font-size:14px}
th,td{padding:9px 14px;text-align:right;border-bottom:1px solid var(--line);
  font-variant-numeric:tabular-nums}
th{font:600 11px/1.3 var(--font-body);letter-spacing:.05em;text-transform:uppercase;
  color:var(--ink-faint);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
td{font-family:var(--font-data)}
td:first-child{font-weight:650;font-family:var(--font-body)}
tbody tr:last-child td{border-bottom:none}
tr.pivot td{background:var(--accent-wash)}
.det{display:block;font:400 11.5px/1.4 var(--font-body);color:var(--ink-faint)}
.gain{color:var(--over);font-weight:650} .perte{color:var(--ink-faint)}
.marque{display:inline-block;font:600 10px/1 var(--font-body);letter-spacing:.08em;
  text-transform:uppercase;padding:4px 8px;border-radius:4px;white-space:nowrap}
.marque.oui{background:var(--over);color:var(--ground)}
.marque.verifier{background:var(--warn-wash);color:var(--warn);
  border:1px solid color-mix(in srgb,var(--warn) 45%,transparent)}
.marque.non{background:var(--raised);color:var(--ink-faint);border:1px solid var(--line-strong)}
.marque.ecart{background:var(--danger-wash);color:var(--danger);
  border:1px solid color-mix(in srgb,var(--danger) 45%,transparent)}
summary{cursor:pointer;padding:12px 20px;font-size:13px;color:var(--ink-soft)}
summary:hover{color:var(--ink)}
.mode-emploi{margin:0;padding:12px 20px 18px;font-size:13px;color:var(--ink-soft);
  border-top:1px solid var(--line);line-height:1.6}
.mode-emploi b{color:var(--ink)}

/* ---------- blocs ---------- */
.bilan{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);overflow:hidden}
.bilan-tete{padding:16px 20px;border-bottom:1px solid var(--line)}
.bilan-tete h2{margin:0 0 4px;font:650 18px/1.25 var(--font-display)}
.bilan-tete p{margin:0;font-size:13px;color:var(--ink-soft)}
.surs{border-color:color-mix(in srgb,var(--over) 45%,transparent)}
.surs .bilan-tete{border-bottom-color:color-mix(in srgb,var(--over) 30%,transparent);
  background:color-mix(in srgb,var(--over) 7%,transparent)}
.surs h2{color:var(--over)}
.sur{display:flex;align-items:center;gap:14px;padding:11px 20px;
  border-bottom:1px solid var(--line);flex-wrap:wrap}
.sur:last-child{border-bottom:none}
.sur-proba{flex:none;width:52px;font:700 19px/1 var(--font-data);color:var(--over);
  font-variant-numeric:tabular-nums}
.sur-quoi{flex:1 1 190px;min-width:0;display:flex;flex-direction:column;gap:2px}
.sur-quoi b{font:650 15px/1.2 var(--font-display)}
.sur-quoi small,.sur-match small{font-size:11.5px;color:var(--ink-faint)}
.sur-match{flex:1 1 200px;min-width:0;display:flex;flex-direction:column;gap:2px;
  font-size:13px;color:var(--ink-soft)}
.sur-cote{flex:none;display:flex;flex-direction:column;align-items:flex-end;gap:2px;
  font:600 10.5px/1 var(--font-body);color:var(--ink-faint);text-transform:uppercase;
  letter-spacing:.06em}
.sur-cote b{font:650 16px/1 var(--font-data);color:var(--ink);text-transform:none}
.pari{display:flex;align-items:baseline;gap:11px;padding:9px 20px;font-size:13px;
  flex-wrap:wrap;border-bottom:1px solid var(--line)}
.pari:last-child{border-bottom:none}
.issue{flex:none;width:66px;font:700 10px/1 var(--font-body);letter-spacing:.07em;
  text-transform:uppercase}
.issue.gagne{color:var(--over)} .issue.perdu{color:var(--under)}
.issue.rembourse{color:var(--ink-faint)}
.quoi-pari{flex:1 1 260px;min-width:0;color:var(--ink-soft)}
.quoi-pari b{color:var(--ink)}
.reel{flex:none;color:var(--ink-soft);font-family:var(--font-data);font-size:12.5px;
  font-variant-numeric:tabular-nums}
.vide{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:38px 20px;text-align:center;color:var(--ink-soft)}
.vide-journal{padding:26px 20px;text-align:center;color:var(--ink-soft);font-size:13.5px}
footer{color:var(--ink-faint);font-size:12.5px;text-align:center;line-height:1.7;
  border-top:1px solid var(--line);padding-top:20px}
footer a{color:var(--ink-soft)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

BASCULE = """
  var racine = document.documentElement;
  var bouton = document.getElementById('bascule');
  var garde = null;
  try { garde = localStorage.getItem('theme'); } catch (e) {}
  if (garde) { racine.setAttribute('data-theme', garde); }
  function libelle() {
    var sombre = racine.getAttribute('data-theme') === 'dark'
      || (!racine.getAttribute('data-theme')
          && window.matchMedia('(prefers-color-scheme: dark)').matches);
    bouton.textContent = sombre ? 'Thème clair' : 'Thème sombre';
    return sombre;
  }
  libelle();
  bouton.addEventListener('click', function () {
    var sombre = racine.getAttribute('data-theme') === 'dark'
      || (!racine.getAttribute('data-theme')
          && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var neuf = sombre ? 'light' : 'dark';
    racine.setAttribute('data-theme', neuf);
    try { localStorage.setItem('theme', neuf); } catch (e) {}
    libelle();
  });
"""

ONGLETS = """
  document.querySelectorAll('.onglet').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.onglet').forEach(function (x) {
        x.classList.remove('actif');
      });
      b.classList.add('actif');
      document.querySelectorAll('.groupe-matchs').forEach(function (g) {
        g.hidden = (g.id !== b.dataset.cible);
      });
    });
  });
"""
