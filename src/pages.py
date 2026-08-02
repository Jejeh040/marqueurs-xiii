"""Publication du rapport sur GitHub Pages.

Le site vit sur une branche `gh-pages` séparée, tenue à **un seul commit** :
le rapport est réécrit deux fois par jour, garder l'historique ferait grossir le
dépôt de plusieurs dizaines de mégaoctets par an pour rien. Chaque publication
modifie ce commit unique et le renvoie de force — ce sont des pages générées,
rien d'autre n'y vit, il n'y a donc rien à écraser.
"""

from __future__ import annotations

import os
import shutil
import subprocess

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAPPORTS = os.path.join(RACINE, "rapports")
TRAVAIL = os.path.join(RACINE, ".pages")
BRANCHE = "gh-pages"
JOURS = 14


def _git(*args, cwd=RACINE, verifier=True):
    r = subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if verifier and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def depot_pret() -> str | None:
    """Message d'erreur si la publication est impossible, None si tout va bien."""
    if not os.path.isdir(os.path.join(RACINE, ".git")):
        return "le dossier n'est pas un dépôt git"
    if not _git("remote", verifier=False):
        return "aucun dépôt distant configuré (git remote add origin ...)"
    return None


def _preparer_branche():
    """Crée la branche gh-pages et son répertoire de travail si besoin."""
    if os.path.isdir(TRAVAIL):
        return
    distantes = _git("ls-remote", "--heads", "origin", BRANCHE, verifier=False)
    if distantes:
        _git("fetch", "origin", f"{BRANCHE}:{BRANCHE}", verifier=False)
    if _git("rev-parse", "--verify", BRANCHE, verifier=False):
        _git("worktree", "add", TRAVAIL, BRANCHE)
    else:
        _git("worktree", "add", "--detach", TRAVAIL)
        _git("checkout", "--orphan", BRANCHE, cwd=TRAVAIL)
        _git("rm", "-rf", "--quiet", ".", cwd=TRAVAIL, verifier=False)


def _remplir():
    """Recopie les derniers rapports dans le répertoire du site."""
    fichiers = sorted((f for f in os.listdir(RAPPORTS)
                       if f.endswith(".html") and f[:4].isdigit()), reverse=True)[:JOURS]
    for ancien in os.listdir(TRAVAIL):
        if ancien != ".git" and ancien.endswith(".html"):
            os.remove(os.path.join(TRAVAIL, ancien))
    for f in fichiers:
        shutil.copy(os.path.join(RAPPORTS, f), os.path.join(TRAVAIL, f))
    if fichiers:
        shutil.copy(os.path.join(RAPPORTS, fichiers[0]),
                    os.path.join(TRAVAIL, "index.html"))
    cotes = os.path.join(RAPPORTS, "cotes.html")
    if os.path.exists(cotes):
        shutil.copy(cotes, os.path.join(TRAVAIL, "cotes.html"))
    # Empêche Jekyll de réinterpréter les pages : ce sont des HTML finis.
    open(os.path.join(TRAVAIL, ".nojekyll"), "w").close()
    return fichiers


def publier(bavard: bool = True) -> str | None:
    """Envoie le site. Renvoie l'URL publique, ou None en cas d'échec."""
    souci = depot_pret()
    if souci:
        if bavard:
            print("   publication impossible :", souci)
        return None
    try:
        _preparer_branche()
        fichiers = _remplir()
        if not fichiers:
            if bavard:
                print("   aucun rapport à publier")
            return None
        _git("add", "-A", cwd=TRAVAIL)
        if not _git("status", "--porcelain", cwd=TRAVAIL):
            if bavard:
                print("   site déjà à jour")
            return url()
        message = "Rapport du " + fichiers[0][:-5]
        deja = _git("rev-parse", "--verify", "HEAD", cwd=TRAVAIL, verifier=False)
        if deja:
            _git("commit", "--amend", "-m", message, "--quiet", cwd=TRAVAIL)
        else:
            _git("commit", "-m", message, "--quiet", cwd=TRAVAIL)
        _git("push", "--force", "origin", BRANCHE, cwd=TRAVAIL)
    except Exception as exc:
        if bavard:
            print("   publication échouée :", exc)
        return None
    if bavard:
        print(f"   {len(fichiers)} page(s) publiée(s) — {url()}")
        print("   GitHub Pages met quelques minutes à reconstruire.")
    return url()


def url() -> str | None:
    distant = _git("remote", "get-url", "origin", verifier=False)
    if not distant:
        return None
    reste = distant.split("github.com", 1)[-1].lstrip(":/")
    if reste.endswith(".git"):
        reste = reste[:-4]
    if "/" not in reste:
        return None
    compte, depot = reste.split("/", 1)
    return f"https://{compte.lower()}.github.io/{depot}/"
