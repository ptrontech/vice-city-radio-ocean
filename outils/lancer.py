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
        window_config(GAME,mode,cfg.get("ultralarge",False) and mode!="Validation")
        startup=None
        if mode=="Validation":
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=4
        proc=subprocess.Popen([str(GAME/"gta-vc.exe")],cwd=GAME,startupinfo=startup)
        worker=threading.Thread(target=run,args=(GAME/mode,cfg["modeleIA"],lambda:proc.poll() is not None),daemon=True)
        worker.start()
        return proc.wait()
    finally:kernel.CloseHandle(ctypes.c_void_p(mutex))

def configure(parent):
    cfgpath=PROJECT/"config.json";config=json.loads(cfgpath.read_text(encoding="utf-8"))
    pane=tk.Toplevel(parent);pane.title("Commandes de Radio Océan");pane.resizable(False,False)
    ttk.Label(pane,text="Clique puis appuie sur la lettre qui ouvrira le journal.").pack(padx=18,pady=12)
    status=ttk.Label(pane,text="Journal clavier  ·  "+chr(config["toucheJournal"]));status.pack(pady=4)
    ttk.Label(pane,text="Manette  ·  Sélection pour le journal, croix directionnelle pour naviguer.").pack(padx=18)
    ultra=tk.BooleanVar(value=config.get("ultralarge",False))
    def display():
        config["ultralarge"]=ultra.get()
        cfgpath.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    ttk.Checkbutton(pane,text="Utiliser tout l’écran ultralarge (3440 × 1440)",variable=ultra,command=display).pack(padx=18,pady=8)
    def on_key(event):
        if len(event.keysym)!=1 or not event.keysym.isascii() or not event.keysym.isalpha():return
        config["toucheJournal"]=ord(event.keysym.upper());cfgpath.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
        source=GAME/"CLEO/RadioOcean/index.js";lines=source.read_text(encoding="utf-8").splitlines(True)
        deployed={**config,"racine":GAME.as_posix()+"/"}
        lines[0]="const CONFIG = "+json.dumps(deployed,ensure_ascii=True)+";\n";source.write_text("".join(lines),encoding="utf-8")
        status.configure(text="Journal clavier  ·  "+event.keysym.upper())
    pane.bind("<KeyPress>",on_key);ttk.Button(pane,text="Terminé",command=pane.destroy).pack(pady=12);pane.focus_force()

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
    ttk.Button(outer,text="Affichage et touche du journal",command=lambda:configure(win)).pack(fill="x",pady=3)
    win.mainloop()
    if chosen:return start(chosen[0])
if __name__=="__main__":
    try:sys.exit(main() or 0)
    except Exception as exc:
        messagebox.showerror("Radio Océan",str(exc))
        raise
