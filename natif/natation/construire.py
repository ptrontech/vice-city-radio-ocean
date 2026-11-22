"""Compile le rendu de nage x86 avec MSVC, l'API CLEO Redux et le SDK VC épinglés."""
from hashlib import sha256
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REVISION="62a1080902627b3edec0124acf02127ba8c0dcdb"
CLEO_REVISION="bbf6773fe8cc1bfa95c73509a25928f97b0d8d13"
RACINE=Path(__file__).resolve().parent

def outils():
    vswhere=Path(os.environ["ProgramFiles(x86)"])/"Microsoft Visual Studio/Installer/vswhere.exe"
    vs=Path(subprocess.check_output([str(vswhere),"-latest","-products","*","-requires","Microsoft.VisualStudio.Component.VC.Tools.x86.x64","-property","installationPath"],text=True).strip())
    vcvars=vs/"VC/Auxiliary/Build/vcvars32.bat"
    if not vcvars.is_file():
        raise RuntimeError("MSVC x86 et un SDK Windows 10 sont nécessaires.")
    invocation='call vcvars32.bat >nul && set'
    raw=subprocess.check_output([os.environ["COMSPEC"],"/d","/c",invocation],cwd=vcvars.parent,encoding="mbcs",errors="replace")
    env=dict(line.split("=",1) for line in raw.splitlines() if "=" in line and not line.startswith("="))
    return env

def construire(sdk,cleo,dest):
    revision=subprocess.check_output(["git","-C",str(sdk),"rev-parse","HEAD"],text=True).strip()
    if revision!=REVISION:raise ValueError("Révision du Plugin-SDK incompatible : "+revision)
    fichiers={"cleo_redux_sdk.h":"c7b1e01f415c0fb59c00e630278a68c2e87a05739d247e284b01a73a038204a7",
              "cleo_redux.lib":"9774a4d4e3c535757935af9e4e807e45e8066b05af356f4f8fa6c36c91b7d121"}
    for nom,empreinte in fichiers.items():
        if sha256((cleo/nom).read_bytes()).hexdigest()!=empreinte:
            raise ValueError("La dépendance CLEO 1.5.1 est différente : "+nom)
    env=outils()
    chemin=next(v for k,v in env.items() if k.casefold()=="path")
    cl=shutil.which("cl.exe",path=chemin); link=shutil.which("link.exe",path=chemin)
    base=sdk/"plugin_vc/game_vc"
    includes=[cleo,sdk/"plugin_vc",base,base/"enums",base/"rw",sdk/"shared",sdk/"shared/game",sdk/"safetyhook"]
    cpp=[RACINE/"Natation.cpp",*[base/(s+".cpp") for s in ("common","CPools","CAnimManager","CEntity","CMatrix","CPhysical","RenderWare")],
         *[sdk/"shared"/(s+".cpp") for s in ("GameVersion","Patch","Events","DynAddress","PluginBase")]]
    with tempfile.TemporaryDirectory(prefix="radio-natation-") as tmp:
        # Toutes les sorties et les intermédiaires sont privés à cette compilation.
        flags=["/nologo","/std:c++latest","/EHsc","/O2","/MT","/Gy","/Gw","/W0","/DGTA_VC","/DGTAVC","/DRW","/DNOMINMAX","/D_CRT_SECURE_NO_WARNINGS","/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS"]
        cmd=[cl,*flags,*["/I"+str(x) for x in includes],"/c",*[str(x) for x in cpp]]
        subprocess.run(cmd,cwd=tmp,env=env,check=True)
        out=Path(tmp)/"RadioOceanNatation.cleo"
        subprocess.run([link,"/nologo","/DLL","/MACHINE:X86","/OPT:REF","/OPT:ICF","/INCREMENTAL:NO","/DYNAMICBASE","/NXCOMPAT","/Brepro","/OUT:"+str(out),*[str(p) for p in Path(tmp).glob("*.obj")],str(cleo/"cleo_redux.lib"),"kernel32.lib","user32.lib","psapi.lib"],cwd=tmp,env=env,check=True)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(out,dest)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--plugin-sdk",type=Path,required=True);ap.add_argument("--cleo-sdk",type=Path,required=True)
    ap.add_argument("--sortie",type=Path,required=True)
    a=ap.parse_args();construire(a.plugin_sdk.resolve(),a.cleo_sdk.resolve(),a.sortie.resolve())
