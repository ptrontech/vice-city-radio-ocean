import argparse
import configparser
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from radio import run

PROJECT=Path(__file__).resolve().parents[1]
GAME=PROJECT.parent/"Jeu"
MODES={"Campagne","Libre","Validation"}

def window_config(folder, mode, wide=False):
    width,height=(3440,1440) if wide else (1920,1080)
    testing=mode=="Validation"
    content=(f"[MAIN]\nWindowMode={2 if wide else 1}\nConfineCursor={0 if testing else 1}\n"
             f"PauseOnFocusLoss={0 if testing else 1}\nResumeOnFocus=1\n"
             f"[WINDOW]\nWidth={width}\nHeight={height}\nMaximized=0\nPositionX=-1\nPositionY=-1\n")
    (folder/"scripts/III.VC.SA.WindowedMode.cfg").write_text(content,encoding="ascii")

def set_startup_movies(game, show):
    """Alterne les deux logos complets et le clip de lancement compatible avec DirectShow."""
    from hashlib import sha256
    from tempfile import NamedTemporaryFile
    import os

    digest = "d40db6fbb3b6bb71d7c71956e20aa227b55760f14982df5a82463e823f52314c"
    clip_size = 59392
    movies = game / "movies"
    fast = None
    if not show:
        fast = (PROJECT / "medias" / "intro-noire.mpg").read_bytes()
        if len(fast) != clip_size or sha256(fast).hexdigest() != digest:
            raise RuntimeError("L'introduction courte de Radio Océan est incomplète. Redéploie le projet.")

    for name in ("Logo.mpg", "GTAtitles.mpg"):
        active = movies / name
        backup = movies / (name + ".radio-ocean")
        has_active = active.is_file()
        is_short = has_active and active.stat().st_size == clip_size and sha256(active.read_bytes()).hexdigest() == digest
        if show:
            if backup.is_file():
                if has_active and not is_short:
                    raise RuntimeError(f"Deux vidéos distinctes existent pour {name}. Préserve ta version personnalisée avant de restaurer l'originale.")
                backup.replace(active)
            continue
        if is_short:
            continue
        if has_active and backup.exists():
            raise RuntimeError(f"Le fichier {name} a été personnalisé depuis sa sauvegarde. Préserve cette copie avant de choisir le mode rapide.")

        # Écrire entièrement le nouveau clip avant de déplacer la vidéo commerciale.
        with NamedTemporaryFile(dir=movies, prefix=name + ".", suffix=".tmp", delete=False) as handle:
            staged = Path(handle.name)
            try:
                handle.write(fast)
                handle.flush()
                os.fsync(handle.fileno())
            except OSError:
                handle.close()
                staged.unlink(missing_ok=True)
                raise
        parked_now = False
        try:
            if has_active:
                active.rename(backup)
                parked_now = True
            # L'ancien mode rapide a déjà déplacé active vers backup. Il est repris ici.
            staged.replace(active)
        except OSError:
            if parked_now and backup.exists() and not active.exists():
                backup.rename(active)
            raise
        finally:
            staged.unlink(missing_ok=True)


def start(mode, slot=None):
    if mode not in MODES:raise ValueError(mode)
    # Toutes les entrées passent par un verrou Windows, libéré automatiquement après arrêt.
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateMutexW.restype=ctypes.c_void_p
    mutex=kernel.CreateMutexW(None,False,"Local\\ViceCityRadioOceanLauncher")
    if not mutex or ctypes.get_last_error()==183:raise RuntimeError("La copie Radio Océan est déjà ouverte.")
    try:
        lines=subprocess.check_output(["tasklist","/FI","IMAGENAME eq gta-vc.exe","/FO","CSV","/NH"],
            creationflags=subprocess.CREATE_NO_WINDOW).decode("mbcs","replace")
        if '"gta-vc.exe"' in lines.lower():raise RuntimeError("Ferme la partie Vice City en cours avant de changer de profil.")
        cfg=json.loads((PROJECT/"config.json").read_text(encoding="utf-8"))
        slot=slot if slot is not None else (9 if mode!="Campagne" else -1)
        (GAME/"scripts/III.VC.SA.SaveLoader.cfg").write_text(f"[MAIN]\nLoadSlot={slot}\nSkipLoadingScreens=1\nSkipOutro=1\nUserFilesFolder={mode}\n",encoding="ascii")
        (GAME/"atelier-session.ini").write_text(f"[atelier]\nprofil={mode}\n",encoding="ascii")
        from installer import change_palette, deploy_script
        deploy_script(cfg)
        change_palette(nuits_orage=cfg.get("nuitsOrage",False))
        window_config(GAME,mode,cfg.get("ultralarge",False) and mode!="Validation")
        set_startup_movies(GAME,cfg.get("videosLancement",False) and mode!="Validation")
        proc=subprocess.Popen([str(GAME/"gta-vc.exe")],cwd=GAME)
        worker=threading.Thread(target=run,args=(GAME/mode,cfg["modeleIA"],lambda:proc.poll() is not None),daemon=True)
        worker.start()
        return proc.wait()
    finally:kernel.CloseHandle(ctypes.c_void_p(mutex))

def configure(parent):
    cfgpath=PROJECT/"config.json"
    config=json.loads(cfgpath.read_text(encoding="utf-8"))
    pane=tk.Toplevel(parent)
    pane.title("Affichage et commandes de Radio Océan")
    pane.resizable(False,False)
    block=ttk.Frame(pane,padding=18)
    block.pack(fill="both")
    letters={chr(code):code for code in range(65,91)}
    keys={"Action du jeu uniquement":0,"Maj":16,"Espace":32,"Ctrl":17,**letters}
    def selector(label,values,code):
        ttk.Label(block,text=label).pack(anchor="w",pady=(6,2))
        current=next((key for key,value in values.items() if value==code),None)
        if current is None:
            current=f"Touche Windows {code}"
            values[current]=code
        field=ttk.Combobox(block,state="readonly",values=list(values),width=34)
        field.set(current)
        field.pack(fill="x")
        return field
    journal=selector("Ouvrir le journal",letters,config["toucheJournal"])
    sprint=selector("Touche de sprint suivie par le carnet",keys,config.get("toucheSprint",16))
    ttk.Label(block,text="Choisis la même touche Sprint dans les commandes de GTA.",wraplength=360).pack(anchor="w",pady=4)
    ttk.Label(block,text="Manette  ·  Sélection ouvre le journal, la croix haut/bas parcourt les options.",wraplength=360).pack(anchor="w",pady=6)
    ultra=tk.BooleanVar(value=config.get("ultralarge",False))
    ttk.Checkbutton(block,text="Utiliser tout l’écran ultralarge (3440 × 1440)",variable=ultra).pack(anchor="w",pady=6)
    orage=tk.BooleanVar(value=config.get("nuitsOrage",False))
    ttk.Checkbutton(block,text="Nuits d’orage (pluie et ouragan)",variable=orage).pack(anchor="w",pady=4)
    movies=tk.BooleanVar(value=config.get("videosLancement",False))
    ttk.Checkbutton(block,text="Afficher les deux vidéos de lancement",variable=movies).pack(anchor="w",pady=4)
    def save():
        config.update(toucheJournal=letters[journal.get()],toucheSprint=keys[sprint.get()],ultralarge=ultra.get(),videosLancement=movies.get(),nuitsOrage=orage.get())
        tmp=cfgpath.with_suffix(".tmp")
        tmp.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(cfgpath)
        pane.destroy()
    ttk.Button(block,text="Enregistrer",command=save).pack(anchor="e",pady=(9,0))
    pane.transient(parent)
    pane.grab_set()

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--profil",choices=sorted(MODES));args=parser.parse_args()
    if args.profil:return start(args.profil)
    win=tk.Tk();win.title("Vice City · Radio Océan");win.resizable(False,False)
    outer=ttk.Frame(win,padding=22);outer.pack()
    ttk.Label(outer,text="Radio Océan",font=("Segoe UI",22,"bold")).pack(anchor="w")
    ttk.Label(outer,text="Ocean Beach, 1986. Les bandes de la prochaine émission viennent d'arriver.",wraplength=415).pack(anchor="w",pady=(2,15))
    chosen=[]
    def choose(mode):chosen.append(mode);win.destroy()
    ttk.Button(outer,text="Jouer la campagne",command=lambda:choose("Campagne")).pack(fill="x",pady=3)
    ttk.Button(outer,text="Mode libre · 3 livraisons et 1 800 $",command=lambda:choose("Libre")).pack(fill="x",pady=3)
    ttk.Button(outer,text="Affichage et commandes",command=lambda:configure(win)).pack(fill="x",pady=3)
    win.mainloop()
    if chosen:return start(chosen[0])
if __name__=="__main__":
    try:sys.exit(main() or 0)
    except Exception as exc:
        messagebox.showerror("Radio Océan",str(exc))
        raise
