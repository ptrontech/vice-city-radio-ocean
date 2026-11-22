"""Déploie uniquement dans la copie personnelle ViceCityAtelier/Jeu."""
from pathlib import Path
from hashlib import sha256
import json
import os
import shutil
import re
import sys

PROJET = Path(__file__).resolve().parents[1]
BASE = PROJET.parent
JEU = BASE / "Jeu"
CACHE = BASE / "Archives"
ORIGINE = Path(os.environ.get("RADIO_OCEAN_ORIGINE","E:/Games/GTA_VC_1.0"))
SOMMES = {
    "GTAVC.WidescreenFix": "955391a35ddd58e27d313b4c04a9ac5de2b23ee64b2ba922f5b2d30f8657e9a1",
    "III.VC.SA.WindowedMode": "37ddaec697f5f165d9bc81619cf42bae6d14da0f2c17e4c7d0ebf05ada77993b",
    "VC.Project2DFX": "c81d191569abc17ac29d77df5b8e7f1c51289345e81521723f6d12d3f1fe2498",
    "SilentPatchVC": "37189b72835316ac1d20d13e686d5fe986ffde51755de5d730ba5795378840ab",
    "cleo_redux_1.5.1.x86": "8dcc0e83e25ab8c57a52d4ca65470b8ec6fc4e94121e5905b826079d75c2807b",
    "ImGuiReduxWin32": "9ddf3286555141d08d43cb9a65a5fb6029c1c38282777cde7da8e1335632498a",
    "III.VC.SA.SaveLoader": "5e1b29094bd46ebe34a2de7946fa8b374b855dbe639442e8371faba120bfa938",
}
def copy(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)

def patch_value(path, key, value):
    value_text = path.read_text(encoding="latin-1")
    pattern = r"(?m)^(" + re.escape(key) + r"\s*=\s*)[^;\s]+"
    result, count = re.subn(pattern, lambda m: m[1]+str(value), value_text)
    if count != 1:
        raise ValueError(f"{key} absent ou ambigu dans {path}")
    path.write_text(result, encoding="latin-1")

def change_palette():
    lines = (ORIGINE/"data/timecyc.dat").read_text(encoding="latin-1").splitlines()
    section, hour, changed = -1, 0, 0
    for i, line in enumerate(lines):
        if line.startswith("////"):
            section += 1
            hour = 0
        cols = line.split()
        if not cols or not re.match(r"^\d", cols[0]):
            continue
        if len(cols) != 52:
            raise ValueError(f"Format de palette inattendu, ligne {i+1}, {len(cols)} colonnes")
        if section == 6:  # Palette spéciale des missions et intérieurs
            continue
        night = [1,1,1,1,.95,.65,.28,.1,0,0,0,0,0,0,0,0,0,.05,.15,.4,.7,.9,1,1][hour]
        dusk = {5:.4,6:.75,7:.4,17:.3,18:.8,19:1,20:.4}.get(hour,0)
        wet = section in (2,3,5)
        def blend(start, target, weight):
            for j, channel in enumerate(target):
                cols[start+j] = str(round(float(cols[start+j])*(1-weight) + channel*weight))
        blend(0,(69,76,99),night*.28)
        blend(15,(27,28,72),night*(.32 if wet else .62))
        blend(18,(72,46,89),night*(.18 if wet else .34))
        blend(18,(243,132,136),dusk*(.16 if wet else .39))
        blend(48,(37,127,142),(.10 if wet else .23)*(1-.45*night))
        if not wet:
            cols[33]=str(round(float(cols[33])*1.08,1))
        lines[i]=" ".join(cols)
        changed += 1
        hour += 1
    if changed != 144:
        raise ValueError(f"Nombre de tranches météo inattendu {changed}")
    (JEU/"data/timecyc.dat").write_text("\n".join(lines)+"\n",encoding="latin-1")

def install():
    if JEU.resolve() == ORIGINE.resolve() or sha256((JEU/"gta-vc.exe").read_bytes()).hexdigest() != "04e4db72629eaa786fdd182ac224f4fd6d68806f5f4fe5c1fb5f756dc4da11d7":
        raise SystemExit("Version de travail incompatible")
    import zipfile
    for name, checksum in SOMMES.items():
        archive = CACHE / (name+".zip")
        if sha256(archive.read_bytes()).hexdigest() != checksum:
            raise SystemExit("Empreinte incorrecte : "+name)
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if not ((CACHE/name/entry.filename).resolve()).is_relative_to((CACHE/name).resolve()):
                    raise ValueError(entry.filename)
            z.extractall(CACHE/name)
    wide = CACHE / "GTAVC.WidescreenFix"
    copy(wide/"d3d8.dll",JEU/"d3d8.dll")
    shutil.copytree(wide/"scripts",JEU/"scripts",dirs_exist_ok=True)
    patch_value(JEU/"scripts/global.ini","LoadFromScriptsOnly",0)
    patch_value(JEU/"scripts/GTAVC.WidescreenFix.ini","NoIslandLoading",0)
    patch_value(JEU/"scripts/GTAVC.WidescreenFix.ini","CarSpeedDependantFOV",0)
    copy(CACHE/"III.VC.SA.WindowedMode/III.VC.SA.WindowedMode.asi",JEU/"scripts/III.VC.SA.WindowedMode.asi")
    sp=CACHE/"SilentPatchVC"
    for name in ["SilentPatchVC.asi","SilentPatchVC.ini"]:
        copy(sp/name,JEU/"scripts"/name)
    patch_value(JEU/"scripts/SilentPatchVC.ini","ShowPropertyBlips",1)
    shutil.copytree(sp/"data",JEU/"data",dirs_exist_ok=True)
    for name in ("VCLodLights.asi","VCLodLights.dat","III.VC.SA.LimitAdjuster.asi","III.VC.SA.LimitAdjuster.ini"):
        copy(CACHE/"VC.Project2DFX"/name,JEU/"scripts"/name)
    redux=CACHE/"cleo_redux_1.5.1.x86"
    copy(redux/"cleo_redux.asi",JEU/"cleo_redux.asi")
    for name in ("IniFiles","Input","TextLoader"):
        copy(redux/"CLEO/CLEO_PLUGINS"/(name+".cleo"),JEU/"CLEO/CLEO_PLUGINS"/(name+".cleo"))
    copy(CACHE/"ImGuiReduxWin32/ImGuiReduxWin32.cleo",JEU/"CLEO/CLEO_PLUGINS/ImGuiReduxWin32.cleo")
    copy(CACHE/"III.VC.SA.SaveLoader/III.VC.SA.SaveLoader.asi",JEU/"scripts/III.VC.SA.SaveLoader.asi")
    for name in ("vc","unknown_x86"):
        copy(CACHE/(name+".json"),JEU/"CLEO/.config"/(name+".json"))
    (JEU/"CLEO/.config/cleo.ini").write_text("[General]\nPermissionLevel=Strict\nAllowCs=0\nAllowJs=1\n[Permissions]\nfs=1\nmem=0\ndll=0\n")
    for folder in ("Campagne","Libre","Validation"):
        (JEU/folder).mkdir(exist_ok=True)
        original_settings=BASE/"SauvegardeInitiale/GTA Vice City User Files/gta_vc.set"
        if original_settings.is_file() and not (JEU/folder/"gta_vc.set").exists():
            copy(original_settings,JEU/folder/"gta_vc.set")
    dest=JEU/"CLEO/RadioOcean"
    dest.mkdir(exist_ok=True)
    cfg=json.loads((PROJET/"config.json").read_text(encoding="utf-8"))
    cfg["racine"]=JEU.as_posix()+"/"
    (JEU/"CLEO/CLEO_TEXT").mkdir(exist_ok=True)
    js="\n".join(p.read_text(encoding="utf-8") for p in sorted((PROJET/"jeu").glob("*.js")))
    (dest/"index.js").write_text("const CONFIG = "+json.dumps(cfg,ensure_ascii=True)+";\n"+js,encoding="utf-8")
    (dest/"mod.json").write_text('{"permissions":["fs"]}')
    change_palette()
    from textures import construire
    construire(ORIGINE,JEU/"models/generic.txd")

if __name__ == "__main__":
    install()
