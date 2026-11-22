"""Identités, états et présence locale des CLI d'agents.

La présence d'un exécutable (--version qui répond) et l'obtention d'une
vraie réponse d'un fournisseur sont deux états distincts : la première est
détectée ici, hors-ligne ; le second ne se prouve qu'au premier envoi.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DOSSIER_DONNEES = Path(os.environ.get("ATELIER_IA_DONNEES") or
                       (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "RadioOcean" / "AtelierIA"))


class Etat(str, Enum):
    ABSENT = "absent"
    PRET = "pret"
    EN_COURS = "en_cours"
    CONNEXION = "connexion"
    QUOTA = "quota"
    ERREUR = "erreur"


LIBELLES_ETAT = {
    Etat.ABSENT: "CLI introuvable",
    Etat.PRET: "Prêt",
    Etat.EN_COURS: "En cours…",
    Etat.CONNEXION: "Connexion demandée",
    Etat.QUOTA: "Quota dépassé",
    Etat.ERREUR: "Erreur",
}

COULEURS_ETAT = {
    Etat.ABSENT: "#9ca3af",
    Etat.PRET: "#16a34a",
    Etat.EN_COURS: "#d97706",
    Etat.CONNEXION: "#dc2626",
    Etat.QUOTA: "#9333ea",
    Etat.ERREUR: "#dc2626",
}


@dataclass
class AgentInfo:
    cle: str
    nom: str
    couleur: str
    exe: str | None = None
    version: str | None = None
    etat: Etat = Etat.ABSENT
    detail: str = ""


AGENTS: dict[str, AgentInfo] = {
    "codex": AgentInfo("codex", "Codex", "#111827"),
    "claude": AgentInfo("claude", "Claude", "#ea580c"),
    "kimi": AgentInfo("kimi", "Kimi", "#2563eb"),
}

_CANDIDATS_EXE = {
    "codex": ["codex.exe", "codex"],
    "claude": ["claude.exe", "claude.cmd", "claude"],
    "kimi": ["kimi.exe", "kimi"],
}


def _chemins_connus(cle: str) -> list[Path]:
    dossier_home = Path.home()
    if cle == "codex":
        chemins: list[Path] = []
        programme = os.environ.get("ProgramFiles", r"C:\Program Files")
        paquet = Path(programme) / "WindowsApps"
        try:
            chemins.extend(sorted(paquet.glob("OpenAI.Codex_*/app/resources/codex.exe"),
                                  key=lambda p: p.stat().st_mtime, reverse=True))
        except OSError:
            pass
        if os.name == "nt" and not chemins:
            # L'Explorateur peut ignorer le PATH de Codex Desktop. Interroger le paquet
            # déclaré par Windows évite de dépendre des droits de liste de WindowsApps.
            ps = Path(os.environ.get("SystemRoot",r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
            try:
                appel = subprocess.run([str(ps),"-NoLogo","-NoProfile","-NonInteractive","-Command",
                                        "(Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1).InstallLocation"],
                                       capture_output=True, timeout=10, stdin=subprocess.DEVNULL,
                                       creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                installation = appel.stdout.decode("utf-8","replace").strip()
                if appel.returncode == 0 and installation:
                    chemins.append(Path(installation) / "app/resources/codex.exe")
            except (OSError,subprocess.TimeoutExpired):
                pass
        local = os.environ.get("LOCALAPPDATA")
        if local:
            chemins.append(Path(local) / "Microsoft" / "WindowsApps" / "codex.exe")
        return chemins
    if cle == "claude":
        appdata = os.environ.get("APPDATA")
        chemins = [dossier_home / ".local" / "bin" / "claude.exe"]
        if appdata:
            chemins.append(Path(appdata) / "npm" / "claude.cmd")
        nvm = os.environ.get("NVM_SYMLINK")
        if nvm:
            chemins.append(Path(nvm) / "claude.cmd")
        return chemins
    return [dossier_home / ".kimi-code" / "bin" / "kimi.exe"]


def _cible_native(candidat: Path, cle: str) -> Path | None:
    if os.name != "nt" or candidat.suffix.lower() == ".exe":
        return candidat if candidat.is_file() else None
    if cle == "claude":
        paquet = candidat.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if paquet.is_file():
            return paquet
    return None


def dossier_conversation(cle: str) -> Path:
    if cle not in AGENTS:
        raise ValueError("Agent inconnu")
    chemin = DOSSIER_DONNEES / "conversations" / cle
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def resoudre_executables() -> None:
    """Repère l'exécutable de chaque CLI (PATH puis emplacements connus)."""
    for cle, info in AGENTS.items():
        trouve: Path | None = None
        for nom in _CANDIDATS_EXE[cle]:
            p = shutil.which(nom)
            if p:
                trouve = _cible_native(Path(p),cle)
                if trouve:
                    break
        if trouve is None:
            for candidat in _chemins_connus(cle):
                trouve = _cible_native(candidat,cle)
                if trouve:
                    break
        info.exe = str(trouve) if trouve else None
        if trouve is None:
            info.etat = Etat.ABSENT
            info.detail = "exécutable introuvable"


def sonder_version(info: AgentInfo, delai: int = 20) -> None:
    """Vérifie que le CLI se lance (--version). Aucun contact réseau."""
    if not info.exe:
        info.etat = Etat.ABSENT
        info.detail = "exécutable introuvable"
        return
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        resultat = subprocess.run(
            [info.exe, "--version"],
            capture_output=True,
            timeout=delai,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        info.etat = Etat.ABSENT
        info.detail = "exécutable introuvable"
        return
    except subprocess.TimeoutExpired:
        info.etat = Etat.ERREUR
        info.detail = "--version : délai dépassé"
        return
    except OSError as exc:
        info.etat = Etat.ERREUR
        info.detail = f"--version : {type(exc).__name__}"
        return
    brut = (resultat.stdout or resultat.stderr or b"").decode("utf-8", "replace").strip()
    premiere = brut.splitlines()[0].strip() if brut else ""
    if resultat.returncode == 0 and premiere:
        info.version = premiere[:90]
        info.etat = Etat.PRET
        info.detail = f"CLI présent — {info.version}"
    else:
        info.version = None
        info.etat = Etat.ERREUR
        info.detail = premiere[:140] or f"code de sortie {resultat.returncode}"


def nouveau_contexte() -> dict:
    return {
        "session": None,
        "texte_tour": 0,
        "candidat_final": "",
        "bruts": [],
    }


_MOTIFS_CONNEXION = re.compile(
    r"not logged in|log in|login|sign in|authentication|unauthorized|forbidden|"
    r"invalid api key|expired|connexion|authentifi|non autorisé|reconnect",
    re.IGNORECASE,
)
_MOTIFS_QUOTA = re.compile(
    r"rate.?limit|too many requests|429|quota|usage limit|limit reached|"
    r"insufficient|credit|payment|dépassé|limite",
    re.IGNORECASE,
)
_MOTIFS_SECRET = re.compile(
    r"sk-[A-Za-z0-9_\-]{8,}|api[_-]?key\s*[:=]\s*\S+|bearer\s+[A-Za-z0-9_\-\.]{8,}",
    re.IGNORECASE,
)


def classer_erreur(texte: object) -> tuple[Etat, str]:
    """Classe un message d'erreur : connexion demandée, quota ou erreur."""
    nettoye = _MOTIFS_SECRET.sub("⟨secret masqué⟩", str(texte or ""))
    ligne = " ".join(nettoye.split())[:220]
    if not ligne:
        return Etat.ERREUR, "erreur inconnue"
    if _MOTIFS_CONNEXION.search(ligne):
        return (
            Etat.CONNEXION,
            "connexion demandée : authentifiez ce CLI dans un terminal, puis réessayez",
        )
    if _MOTIFS_QUOTA.search(ligne):
        return Etat.QUOTA, "quota ou limite de débit dépassé — réessayez plus tard"
    return Etat.ERREUR, ligne
