"""Régénère les 2 secondes noires et muettes de Radio Océan, placées sous CC0 1.0.

Aucune image, bande sonore ou donnée provenant du jeu n'entre dans l'encodage.
Le jeu utilise directement medias/intro-noire.mpg. FFmpeg ne sert qu'à la fabrication.
Fabrication vérifiée avec FFmpeg 7.1-essentials_build-www.gyan.dev pour Windows x64,
issu de la distribution PyPI imageio-ffmpeg 0.6.0.
Roue officielle SHA-256 02fa47c83703c37df6bfe4896aab339013f62bf02c5ebf2dce6da56af04ffc0a.
Reproduction : python outils/generer_intro.py --ffmpeg chemin/vers/ffmpeg.exe
"""
import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

DIGEST = "d40db6fbb3b6bb71d7c71956e20aa227b55760f14982df5a82463e823f52314c"
DEST = Path(__file__).resolve().parents[1] / "medias" / "intro-noire.mpg"

def generate(ffmpeg):
    options = [
        "-hide_banner", "-loglevel", "error", "-nostdin",
        "-f", "lavfi", "-i", "color=c=black:s=640x480:r=25",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "2", "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "mpeg1video", "-pix_fmt", "yuv420p", "-g", "12", "-bf", "0",
        "-threads:v", "1", "-q:v", "8", "-c:a", "mp2", "-b:a", "128k",
        "-flags:v", "+bitexact", "-flags:a", "+bitexact",
        "-fflags", "+bitexact", "-map_metadata", "-1", "-f", "mpeg",
    ]
    DEST.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=DEST.parent) as temp:
        candidate = Path(temp) / "noire.mpg"
        subprocess.run([ffmpeg, *options, str(candidate)], check=True)
        digest = sha256(candidate.read_bytes()).hexdigest()
        if digest != DIGEST:
            raise SystemExit(f"Empreinte différente avec cet encodeur, fichier conservé en l'état : {digest}")
        if DEST.is_file() and sha256(DEST.read_bytes()).hexdigest() == DIGEST:
            return
        if DEST.exists():
            raise SystemExit(f"Un autre fichier occupe {DEST}")
        candidate.replace(DEST)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Régénérer le clip de lancement CC0.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    generate(parser.parse_args().ffmpeg)
    print(DEST)
