"""Lancement et lecture d'un processus CLI, sans fenêtre console."""
from __future__ import annotations

from collections import deque
import subprocess
import threading
from pathlib import Path


class TacheAnnulee(Exception):
    pass


class TacheProcessus:
    """Enveloppe subprocess : sortie ligne à ligne, stderr capturé, annulation."""

    def __init__(self, argv: list[str], cwd: Path):
        self.argv = list(argv)
        self.cwd = Path(cwd)
        self._annullee = threading.Event()
        self._verrou_stderr = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self._stderr = deque(maxlen=24)
        self._fil_stderr: threading.Thread | None = None

    def demarrer(self) -> None:
        argv = list(self.argv)
        if argv and argv[0].lower().endswith((".cmd", ".bat")):
            raise OSError("Le binaire natif du client est nécessaire sous Windows.")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            argv,
            cwd=str(self.cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
        self._fil_stderr = threading.Thread(target=self._lire_stderr, daemon=True)
        self._fil_stderr.start()

    def _lire_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for brut in iter(self.proc.stderr.readline, b""):
            with self._verrou_stderr:
                self._stderr.append(brut.decode("utf-8", "replace").rstrip("\r\n")[:400])

    def lignes(self):
        assert self.proc is not None and self.proc.stdout is not None
        for brut in iter(self.proc.stdout.readline, b""):
            if self._annullee.is_set():
                raise TacheAnnulee
            yield brut.decode("utf-8", "replace").rstrip("\r\n")
        if self._annullee.is_set():
            raise TacheAnnulee

    def annuler(self) -> None:
        self._annullee.set()
        if self.proc is None or self.proc.poll() is not None:
            return
        try:
            self.proc.terminate()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                self.proc.kill()
            except OSError:
                pass

    def attendre(self) -> int:
        assert self.proc is not None
        code = self.proc.wait()
        if self._fil_stderr is not None:
            self._fil_stderr.join(timeout=2)
        return code

    def stderr_texte(self) -> str:
        with self._verrou_stderr:
            return "\n".join(self._stderr)

    @property
    def annullee(self) -> bool:
        return self._annullee.is_set()
