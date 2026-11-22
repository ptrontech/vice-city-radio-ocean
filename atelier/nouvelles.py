"""Lecture locale des nouvelles du projet et des annonces JSONL de l'atelier."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unicodedata

FICHIER_NOUVELLES = "nouvelles.jsonl"
JOURNAUX = {
    FICHIER_NOUVELLES: "",
    "codex-evenements.jsonl": "codex",
    "facades-evenements.jsonl": "claude",
    "kimi-atelier-activite.jsonl": "kimi",
}


def _simple(value):
    return "".join(c for c in unicodedata.normalize("NFD", str(value).lower()) if not unicodedata.combining(c))


def dossier_du_projet():
    import os
    explicite = os.environ.get("ATELIER_JOURNAUX")
    if explicite:
        return Path(explicite)
    for parent in Path(__file__).resolve().parents:
        candidat = parent / "RevueClaude"
        if candidat.is_dir():
            return candidat
    return None


class VeilleNouvelles:
    def __init__(self, dossier: str | None = None):
        self.activer(dossier)

    def activer(self, dossier):
        self.dossier = Path(dossier) if dossier else None
        self._cursors = {}
        self._vues = {}

    @property
    def actif(self):
        return self.dossier is not None

    @property
    def fichier(self):
        return self.dossier / FICHIER_NOUVELLES if self.dossier else None

    def lire_nouveau(self):
        if not self.dossier:
            return []
        nouvelles = []
        for nom, agent in JOURNAUX.items():
            chemin = self.dossier / nom
            try:
                with chemin.open("rb") as src:
                    identite = chemin.stat().st_ino
                    precedent, offset, marque = self._cursors.get(nom,(identite,0,b""))
                    taille = src.seek(0,2)
                    if identite != precedent or taille < offset:
                        offset, marque = 0, b""
                    if marque:
                        src.seek(offset-len(marque))
                        if src.read(len(marque)) != marque:
                            offset = 0
                    src.seek(offset)
                    while True:
                        brut = src.readline(131073)
                        if not brut:
                            break
                        # Ne consommer une ligne qu'une fois le saut de ligne écrit.
                        if not brut.endswith(b"\n"):
                            if len(brut) <= 131072:
                                break
                            while brut and not brut.endswith(b"\n"):
                                brut = src.readline(131073)
                            if not brut:
                                break
                            offset = src.tell()
                            continue
                        offset = src.tell()
                        event = self._analyser(brut.decode("utf-8-sig",errors="replace"),agent)
                        if event:
                            cle = (event["source"],event["horodatage"],event["titre"],event["texte"])
                            if cle not in self._vues:
                                self._vues[cle] = None
                                nouvelles.append(event)
                                if len(self._vues) > 2048:
                                    self._vues.pop(next(iter(self._vues)))
                    src.seek(max(0,offset-64))
                    marque = src.read(min(64,offset))
                    self._cursors[nom] = identite,offset,marque
            except OSError:
                continue
        return sorted(nouvelles,key=lambda n:n["horodatage"])

    @staticmethod
    def _analyser(ligne, agent=""):
        try:
            obj = json.loads(ligne)
        except ValueError:
            return None
        if not isinstance(obj,dict):
            return None
        source = str(obj.get("source") or obj.get("author") or "").strip().lower()
        titre = str(obj.get("titre") or obj.get("kind") or "").strip()
        texte = obj.get("texte",obj.get("text"))
        if not isinstance(texte,str) or not texte.strip():
            return None
        if agent:
            # Les journaux d'autres outils contiennent également leurs entrées et leurs
            # sorties brutes. Seules les nouvelles attribuées à l'auteur sont destinées au joueur.
            if source != agent or _simple(titre) in {"outil","resultat","activite","consigne","diagnostic"}:
                return None
            if re.search(r"think|reason|pensee|raisonnement|tool",_simple(titre)):
                return None
            if _simple(titre) == "fin" and texte.strip() == "0":
                titre, texte = "Fin de session", f"{agent.capitalize()} a terminé sa session du chantier."
            texte = " ".join(texte.replace("**","").replace("`","").split())
            if len(texte) > 600:
                texte = texte[:597].rsplit(" ",1)[0] + "…"
        return {
            "source":source, "titre":titre, "texte":texte.strip(),
            "horodatage":str(obj.get("horodatage") or obj.get("time") or obj.get("date") or ""),
        }
