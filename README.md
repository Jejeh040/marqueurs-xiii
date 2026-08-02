# Marqueurs XIII — paris sur les marqueurs d'essai au rugby à XIII

### 👉 Le rapport du jour : **https://jejeh040.github.io/marqueurs-xiii/**


Outil gratuit, sans clé ni compte. Il estime, pour chaque joueur des matchs du
jour, sa chance de marquer un essai, compare cette estimation à la cote réelle
d'Unibet et signale les écarts qui valent peut-être un pari.

**Lancer :** double-cliquer sur `Lancer.bat`. Le rapport s'ouvre tout seul.

**Site public :** https://jejeh040.github.io/marqueurs-xiii/ — deux pages, dans la
même charte que le site *aces* : `index.html` le rapport du jour (synthèse, paris
conseillés, onglets par compétition, une carte par match avec la distribution du
nombre d'essais, journal des conseils) et `cotes.html` toutes les cotes marqueur
d'essai du moment, y compris les compétitions hors modèle. Thème clair/sombre
mémorisé. Les treize rapports précédents restent accessibles par le bandeau de
dates en haut. Publié
automatiquement à chaque lancement (`--sans-site` pour s'en passer). Le site vit
sur la branche `gh-pages`, tenue à un seul commit réécrit à chaque fois : sans
ça, deux rapports par jour feraient grossir le dépôt de dizaines de mégaoctets
par an. GitHub met deux à cinq minutes à reconstruire la page — un 404 juste
après publication est normal, ne pas relancer en boucle.

**Automatique :** tâche Windows « Marqueurs13 - rapport », **8 h et 20 h chaque
jour**. Celle de 20 h est la plus utile : elle attrape les matchs NRL du
lendemain matin (5 h - 11 h heure de Paris), qu'il faut donc jouer la veille au
soir. Celle de 8 h couvre la Super League de l'après-midi. Rattrapage si le PC
était éteint, aucune relance en boucle. Journal dans `logs/quotidien.log`, le
rapport du jour reste dans `rapports/`.
Pour la désactiver : `Disable-ScheduledTask -TaskName "Marqueurs13 - rapport"`.

Compétitions couvertes : **NRL** (Australie) et **Super League** (Europe,
Catalans Dragons compris).

---

## Comment lire le rapport

| colonne | ce que c'est |
|---|---|
| **modèle** | chance que le joueur marque, selon l'outil, **s'il entre en jeu** |
| **marché** | la même chose selon Unibet, **marge du bookmaker retirée** |
| **cote** | la cote réelle, marge comprise, celle que vous jouez |
| **avantage** | `cote × probabilité du modèle − 1`. Positif = pari théoriquement rentable |

Quatre verdicts :

- **pari conseillé** — l'écart est net, la cote raisonnable, le joueur bien connu ;
- **à vérifier** — il y a un écart mais un signal d'alarme (cote trop haute,
  effectif mal connu, désaccord trop violent avec le marché) ;
- **rien à prendre** — pas d'avantage suffisant. C'est le cas le plus fréquent, et
  c'est normal ;
- **désaccord** — l'outil et le marché ne s'accordent pas sur le nombre d'essais du
  match lui-même. Dans ce cas, aucun conseil n'est donné : c'est presque toujours
  l'outil qui a tort.

---

## Ce que l'outil sait faire, et ce qu'il ne sait pas

**Mesuré, hors échantillon**, sur 33 304 prédictions joueur avec réentraînement
tous les 30 jours (`python validate.py --glissant`) :

| | modèle | simple moyenne |
|---|---|---|
| perte logarithmique | **0,446** | 0,496 |
| score de Brier | **0,141** | 0,158 |
| biais de niveau | 0,991 | 1,000 |

Calibration par tranche (annoncé contre réalisé) : 7,5 % → 8,0 % · 14,5 % →
14,2 % · 24,6 % → 25,4 % · 34,5 % → 35,2 % · 44,7 % → 45,3 %. Le biais par poste
tient entre 0,93 et 1,06 sur les neuf postes.

**Le défaut connu** : au-dessus de 50 %, le modèle est optimiste (56 % annoncés
pour 51 % réalisés). Un garde-fou refuse donc tout conseil au-dessus de 50 %.

Historique des mesures, pour situer ce qui a vraiment payé :

| étape | perte log |
|---|---|
| 1 430 matchs, première version | 0,463 |
| dévigorisation pondérée par le temps de jeu attendu | 0,451 |
| 2 585 matchs (8 saisons au lieu de 4) | 0,446 |
| minutes réellement jouées | 0,4463 → **0,4456** |
| balayage des 4 réglages | 0,4477 → 0,4469 (bruit) |

C'est le **volume de données** qui a fait le travail, pas le réglage fin.

**Ce qui n'a jamais été mesuré : est-ce que ça bat les cotes.** Il n'existe pas
de source gratuite de cotes historiques de marqueur d'essai, donc pas de
backtest possible. Le seul juge est le journal des conseils, alimenté à chaque
lancement (colonnes « réussite » et « rendement » en haut du rapport). Tant
qu'il y a moins d'une centaine de conseils tranchés, il ne prouve rien.

**La marge du bookmaker sur ce marché est énorme : 16 à 55 % selon le match**
(affichée dans le code, calculée à chaque lancement). C'est trois à cinq fois la
marge d'un simple 1X2. Un marché aussi chargé est très difficile à battre :
partir du principe que c'est perdant jusqu'à preuve du contraire.

---

## Comment marche le modèle

Trois étages, chacun mesurable séparément.

1. **Combien d'essais l'équipe va marquer.** Régression de Poisson
   attaque/défense avec avantage du terrain, pondérée par la fraîcheur des
   matchs (demi-vie 400 jours). **Quand le bookmaker cote le total d'essais de
   l'équipe, c'est SA valeur qui est retenue, pas celle du modèle** : le marché
   estime bien mieux le niveau, et l'outil ne garde alors que ce qu'il sait
   faire, répartir ces essais entre les joueurs. (Même logique que le marché
   « qui met le plus d'aces » dans AcesTennis : le biais de niveau s'annule.)

2. **Quelle part revient à chaque joueur.** Taux d'essais **par minute** du poste
   (lu sur les numéros de maillot) × **temps de jeu attendu** × un coefficient
   propre au joueur (« marque-t-il plus ou moins que sa place ? »), régularisé
   vers 1. Le temps de jeu est reconstruit match par match à partir des
   remplacements : un pilier joue 49 minutes, un ailier 78, un remplaçant 41.
   Sans cette séparation, « marque peu » et « joue peu » se confondaient.

3. **Faiblesse de la défense adverse par poste et par côté du terrain.**
   **Désactivée** : mesurée sans effet (0,4526 avec, 0,4518 sans). Le conseil
   classique « viser le côté faible de l'adversaire » ne se voit pas dans les
   données à ce volume. Le code est resté ; `validate.py --avec-defense` permet
   de le remesurer quand la base aura grossi.

Les probabilités sont **conditionnées au fait que le joueur entre en jeu**,
parce que c'est ainsi que se règlent ces paris : remboursés si le joueur ne joue
pas.

### Trois pièges rencontrés pendant la construction, à ne pas défaire

1. **Le numéro de maillot d'un essai ne vient pas de la feuille de match** mais
   de la fiche annuelle du joueur (Jake Connor y est le 18 alors qu'il joue avec
   le 7). Sans correction, un tiers des essais étaient attribués à des
   remplaçants.
2. **La Super League numérote à l'année, pas par poste**, contrairement à la
   NRL. Le poste ne se lit sur le maillot que dans 23 % des feuilles de Super
   League contre 96 % en NRL ; ailleurs, l'outil utilise le poste habituel du
   joueur, appris sur les feuilles qui, elles, sont positionnelles.
3. **Depuis 2026, SofaScore liste les réservistes non utilisés.** L'outil ne
   compte que les joueurs réellement entrés (déduits des remplacements), sans
   quoi la part de tous les autres était diluée.

---

## Les garde-fous (`src/valeur.py`)

Aucun n'est décoratif : chacun a supprimé des conseils manifestement faux le
jour de sa mise en place (21 conseils au départ, 6 après).

- cote entre 1,30 et 7,00 ;
- probabilité du modèle ≤ 50 % (au-delà il est mesuré optimiste) ;
- avantage estimé entre +8 % et +40 % ;
- le modèle ne peut pas donner **plus de 1,5 fois** la chance vue par le marché ;
- désaccord de plus de 1,6 essai avec le total du marché → aucun conseil ;
- joueur vu moins de 6 fois → « à vérifier » ;
- plus de 30 % de l'effectif inconnu → « à vérifier » ;
- si ≥ 75 % des conseils vont dans le même sens (tous à grosse cote, ou tous sur
  des favoris), bandeau rouge : ce n'est pas dix occasions, c'est un seul
  désaccord répété.

---

## Sources de données (toutes gratuites, sans compte)

- **SofaScore** (`src/sofascore.py`) — essais, compositions, remplacements,
  calendrier. Refuse les clients HTTP ordinaires : passe par `curl_cffi` avec
  une empreinte de navigateur.
- **Unibet / Kambi** (`src/kambi.py`) — offre publique
  `eu-offering-api.kambicdn.com`, code marché `ubbe`. Marché « Try Scorer »
  (premier / dernier / à tout moment) plus les totaux d'essais du match et par
  équipe. Le code `ubfr` renvoie 400 ; `ubbe` fonctionne.

**Limite connue :** la Super League n'a pas de cote de total d'essais chez
Kambi. Sur ces matchs, l'outil doit estimer seul le nombre d'essais et ses
probabilités sont moins sûres — un bandeau le rappelle.

**NRL Women est cotée mais exclue** : SofaScore n'y publie aucune composition
d'équipe (0 sur 191 matchs). Sans savoir qui joue, il n'y a pas de taux par
joueuse possible.

---

## Fichiers

```
Lancer.bat          double-clic : met à jour, analyse, ouvre le rapport
LancerAuto.bat      version silencieuse pour une tâche planifiée
run.py              enchaînement complet
validate.py         mesure du modèle (voir les options en tête du fichier)
src/sofascore.py    accès à l'API SofaScore
src/historique.py   construction de la base (data/historique.json)
src/postes.py       postes du XIII à partir des numéros
src/model.py        le modèle
src/kambi.py        relevé des cotes
src/valeur.py       croisement modèle/marché et garde-fous
src/journal.py      suivi des conseils et de leur résultat
src/theme.py        charte du site (CSS, thème clair/sombre, onglets)
src/report.py       les deux pages HTML
src/pages.py        publication du site sur GitHub Pages
data/               base, cotes en cache, journal
rapports/           un fichier par jour + dernier.html
```

La première construction de la base prend environ 8 minutes (2 993 matchs, 8
saisons, deux requêtes par match). Ensuite, chaque lancement dure une quinzaine
de secondes. Le dossier `data/` n'est pas versionné : il se reconstruit tout
seul au premier lancement.

## Installation depuis GitHub

```bash
git clone https://github.com/Jejeh040/marqueurs-xiii.git
cd marqueurs-xiii
pip install -r requirements.txt
python run.py
```

Python 3.12 recommandé. Sous Windows, `Lancer.bat` fait tout.

---

## Miser sans se faire mal

Mises plates, 1 % de la bankroll par conseil, jamais de combiné. Un avantage
affiché n'est pas de l'argent gagné : c'est un pari sur le fait que le modèle a
raison contre un bookmaker qui prend déjà 20 à 40 % de marge sur ce marché.
Commencer par suivre les conseils **sans miser** pendant deux ou trois semaines
et regarder la ligne « rendement ».
