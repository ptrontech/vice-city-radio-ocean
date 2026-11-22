"""Reproduit le projet à partir d'une copie personnelle de Vice City PC 1.0."""
import hashlib
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from installer import BASE, CACHE, JEU, ORIGINE, SOMMES, install

URLS={
    "GTAVC.WidescreenFix":"https://github.com/ThirteenAG/WidescreenFixesPack/releases/download/gtavc/GTAVC.WidescreenFix.zip",
    "SilentPatchVC":"https://github.com/CookiePLMonster/SilentPatch/releases/download/1.1-BUILD34.1-SA/SilentPatchVC.zip",
    "VC.Project2DFX":"https://github.com/ThirteenAG/III.VC.SA.IV.Project2DFX/releases/download/gtavc/VC.Project2DFX.zip",
    "cleo_redux_1.5.1.x86":"https://github.com/cleolibrary/CLEO-Redux/releases/download/1.5.1/cleo_redux_1.5.1.x86.zip",
    "ImGuiReduxWin32":"https://github.com/user-grinch/ImGuiRedux/releases/download/Win32-latest/ImGuiReduxWin32.zip",
    "III.VC.SA.SaveLoader":"https://github.com/ThirteenAG/III.VC.SA.SaveLoader/releases/download/v3.0.1/III.VC.SA.SaveLoader.zip",
    "III.VC.SA.WindowedMode":"https://github.com/ThirteenAG/III.VC.SA.WindowedMode/releases/download/v3.0.5/III.VC.SA.WindowedMode.zip",
}
DEFS={"vc":"f478264933205ce5719e786f5f4eefd97e9d24cf77a8fe376e65e107197e328a",
      "unknown_x86":"93d1dd008002509db977dc98aaa9c4fab217cc715d9f069af23ab73ed2155e0b"}
LIBRARY="4ea6da3c50e25a4607df826dd1114b290549cfde"

def ensure(path,url,expected):
    def digest(candidate):
        with candidate.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
    if path.is_file():
        if digest(path)!=expected:raise ValueError(f"Empreinte différente pour {path.name}. Conserver le fichier pour vérification.")
        return
    request=urllib.request.Request(url,headers={"User-Agent":"ViceCityAtelier"})
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as sink:
        tmp=Path(sink.name)
    try:
        with urllib.request.urlopen(request,timeout=45) as src,tmp.open("wb") as out:
            shutil.copyfileobj(src,out)
        if digest(tmp)!=expected:raise ValueError(f"Nouvelle version non validée pour {path.name}")
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def prepare():
    if JEU.resolve()==ORIGINE.resolve() or JEU.resolve().is_relative_to(ORIGINE.resolve()):
        raise ValueError("Choisir des répertoires séparés.")
    original=ORIGINE/"gta-vc.exe"
    if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest()!="04e4db72629eaa786fdd182ac224f4fd6d68806f5f4fe5c1fb5f756dc4da11d7":
        raise ValueError("Fournir la copie personnelle de Vice City PC 1.0 validée pour ce projet.")
    CACHE.mkdir(parents=True,exist_ok=True)
    if set(URLS)!=set(SOMMES):raise ValueError("Catalogue de dépendances incomplet")
    for key,url in URLS.items():ensure(CACHE/(key+".zip"),url,SOMMES[key])
    for name,expected in DEFS.items():
        ensure(CACHE/(name+".json"),f"https://raw.githubusercontent.com/sannybuilder/library/{LIBRARY}/{name}/{name}.json",expected)
    if not JEU.exists():
        if BASE.resolve().is_relative_to(ORIGINE.resolve()):raise ValueError("Choisir un dossier Atelier extérieur au jeu original.")
        with tempfile.TemporaryDirectory(dir=BASE) as tmp:
            target=Path(tmp)/"Jeu"
            shutil.copytree(ORIGINE,target)
            target.rename(JEU)
    install()
if __name__=="__main__":prepare()
