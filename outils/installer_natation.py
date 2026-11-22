"""Raccorde la pose de natation et les hauteurs d'eau des données personnelles du jeu."""
from hashlib import sha256
import json
import math
from pathlib import Path
from tempfile import NamedTemporaryFile

# Commandes privées de cette extension. La table PC complète reste gérée par CLEO Redux.
EXTENSION="RadioOceanNatation"
SIGNATURES=(
    ("7D30","RADIO_NAGE_ETAT",[("ped","Char")],[("noyade","int")]),
    ("7D32","RADIO_NAGE_POSITION",[("ped","Char"),("x","float"),("y","float"),("z","float")],[]),
    ("7D31","RADIO_NAGE_POSTURE",[("ped","Char"),("inclinaison","float"),("cadence","float")],[]),
)

def niveaux(path):
    zones=[]
    for ligne in path.read_text(encoding="ascii",errors="replace").splitlines():
        ligne=ligne.split(";",1)[0].strip()
        if ligne=="*":break
        if not ligne:continue
        vals=[v.strip() for v in ligne.strip(",").split(",")]
        if len(vals)!=5:raise ValueError(f"Ligne d'eau invalide dans {path}")
        z,x1,y1,x2,y2=map(float,vals)
        if not all(math.isfinite(v) for v in (z,x1,y1,x2,y2)) or x2<=x1 or y2<=y1:
            raise ValueError(f"Rectangle d'eau invalide dans {path}")
        zones.append([z,x1,y1,x2,y2])
    if not zones:raise ValueError(f"Aucun plan d'eau dans {path}")
    return zones

def ecrire_si_change(cible,data):
    if cible.is_file() and cible.read_bytes()==data:return
    cible.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile(prefix=cible.name+".",dir=cible.parent,delete=False) as f:
        tmp=Path(f.name)
        try:f.write(data)
        except OSError:
            f.close();tmp.unlink(missing_ok=True);raise
    try:tmp.replace(cible)
    finally:tmp.unlink(missing_ok=True)

def preparer_nage(jeu,projet):
    zones=niveaux(jeu/"data/water.dat")
    lib=(projet/"medias/RadioOceanNatation.cleo").read_bytes()
    if sha256(lib).hexdigest()!=EMPREINTE:
        raise ValueError("Le module de pose Radio Océan diffère de la compilation vérifiée.")
    fichier=jeu/"CLEO/.config/vc.json"
    table=json.loads(fichier.read_text(encoding="utf-8-sig"))
    extension=next((e for e in table["extensions"] if e["name"]==EXTENSION),None)
    autres=[c for e in table["extensions"] if e is not extension for c in e["commands"]]
    commandes=[]
    for id_,nom,entrees,sorties in SIGNATURES:
        if any(c["id"].upper()==id_ or c["name"]==nom for c in autres):
            raise ValueError("Commande de natation déjà employée dans le catalogue : "+id_)
        entree={"id":id_,"name":nom,"num_params":len(entrees)+len(sorties),
            "input":[{"name":n,"type":t} for n,t in entrees]}
        if sorties:entree["output"]=[{"name":n,"type":t,"source":"var_any"} for n,t in sorties]
        commandes.append(entree)
    if not extension or extension["commands"]!=commandes:
        if extension:extension["commands"]=commandes
        else:table["extensions"].append({"name":EXTENSION,"commands":commandes})
        ecrire_si_change(fichier,json.dumps(table,ensure_ascii=False,separators=(",",":")).encode("utf-8"))
    ecrire_si_change(jeu/"CLEO/CLEO_PLUGINS/RadioOceanNatation.cleo",lib)
    return zones

EMPREINTE="b3a8014f2e4b1fcd83152560bb73c37be0c8e6355e9162c03cc210dbc5ad893c"
