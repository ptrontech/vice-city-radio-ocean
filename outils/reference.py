"""Prépare le banc de comparaison à partir d'une copie intacte du jeu classique."""
from pathlib import Path
import json
import shutil
from installer import PROJET, BASE, ORIGINE, CACHE, JEU, copy
REF=BASE/"Reference"

def prepare():
    if not (REF/"gta-vc.exe").exists():
        shutil.copytree(ORIGINE,REF)
    loader=CACHE/"GTAVC.WidescreenFix/d3d8.dll"
    former=REF/"dinput8.dll"
    if former.is_file() and former.read_bytes()==loader.read_bytes():
        former.replace(REF/"dinput8.dll.desactive")
    copy(loader,REF/"d3d8.dll")
    (REF/"scripts").mkdir(exist_ok=True)
    for file in ("global.ini","GTAVC.WidescreenFix.asi","GTAVC.WidescreenFix.ini","SilentPatchVC.asi","SilentPatchVC.ini"):
        copy(JEU/"scripts"/file,REF/"scripts"/file)
    copy(JEU/"scripts/III.VC.SA.SaveLoader.asi",REF/"scripts/III.VC.SA.SaveLoader.asi")
    (REF/"scripts/III.VC.SA.SaveLoader.cfg").write_text("[MAIN]\nLoadSlot=9\nSkipLoadingScreens=1\nSkipOutro=1\nUserFilesFolder=Validation\n",encoding="ascii")
    copy(JEU/"scripts/III.VC.SA.WindowedMode.asi",REF/"scripts/III.VC.SA.WindowedMode.asi")
    from lancer import window_config
    window_config(REF,"Validation")
    copy(JEU/"cleo_redux.asi",REF/"cleo_redux.asi")
    for file in ("IniFiles.cleo",):
        copy(JEU/"CLEO/CLEO_PLUGINS"/file,REF/"CLEO/CLEO_PLUGINS"/file)
    shutil.copytree(JEU/"CLEO/.config",REF/"CLEO/.config",dirs_exist_ok=True)
    (REF/"CLEO/CLEO_TEXT").mkdir(exist_ok=True)
    shutil.copytree(JEU/"CLEO/RadioOcean",REF/"CLEO/RadioOcean",dirs_exist_ok=True)
    stub=REF/"CLEO/RadioOcean/index.js";src=stub.read_text(encoding="utf-8").replace(JEU.as_posix()+"/",REF.as_posix()+"/",1)
    stub.write_text(src,encoding="utf-8")
    (REF/"Validation").mkdir(exist_ok=True)
    for file,content in {"atelier-session.ini":"[atelier]\nprofil=Validation\n","Validation/essai.ini":"[atelier]\nscenario=reference\n"}.items():
        (REF/file).write_text(content,encoding="ascii")
    if (JEU/"Validation/gta_vc.set").exists():
        copy(JEU/"Validation/gta_vc.set",REF/"Validation/gta_vc.set")

if __name__=="__main__":prepare()
