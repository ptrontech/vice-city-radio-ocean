"""Extrait uniquement les résultats de Radio Océan du journal de la session."""
from pathlib import Path
import sys
from installer import BASE

def extract(source, label):
    if not label.replace("-","").isalnum():raise ValueError(label)
    lines=source.read_text(encoding="utf-8",errors="replace").splitlines()
    events=[l for l in lines if "PREUVE |" in l or "[\"RadioOc\"]" in l and ("[ERROR]" in l or "Radio Ocean |" in l)]
    output=BASE/"Mesures"/(label+".txt")
    output.write_text("\n".join(events)+"\n",encoding="utf-8")
    return output

if __name__=="__main__": print(extract(Path(sys.argv[1]),sys.argv[2]))
