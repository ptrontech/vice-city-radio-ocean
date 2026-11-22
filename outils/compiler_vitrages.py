"""Découpe les atlas originaux de l'hôtel et produit les mipmaps BC1 de Vice City.

NumPy et Pillow ne sont nécessaires que pour refaire les six fichiers fournis avec le mod.
"""
from argparse import ArgumentParser
from pathlib import Path
from struct import pack

import numpy as np
from PIL import Image


def blocs_bc1(image):
    """Quantifie chaque bloc selon son axe de variation de couleur principal."""
    a=np.asarray(image.convert("RGB"),dtype=np.float32)
    h,w=a.shape[:2]
    a=np.pad(a,((0,(-h)%4),(0,(-w)%4),(0,0)),mode="edge")
    blocs=a.reshape((a.shape[0]//4,4,a.shape[1]//4,4,3)).transpose(0,2,1,3,4).reshape(-1,16,3)
    residus=blocs-blocs.mean(1,keepdims=True)
    covariance=np.einsum("bij,bik->bjk",residus,residus)
    direction=np.tile([.30,.59,.11],(len(blocs),1)).astype(np.float32)
    for _ in range(5):
        direction=np.einsum("bij,bj->bi",covariance,direction)
        direction/=np.maximum(1.e-10,np.linalg.norm(direction,axis=1,keepdims=True))
    proj=np.einsum("bij,bj->bi",residus,direction)
    ids=np.arange(len(blocs))
    def enc(c):
        q=np.rint(c*np.array((31,63,31))/255).astype(np.uint32)
        return (q[:,0]<<11)|(q[:,1]<<5)|q[:,2]
    def dec(q):
        r=(q>>11)&31
        g=(q>>5)&63
        b=q&31
        return np.column_stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2))).astype(float)
    lo=enc(blocs[ids,proj.argmin(1)])
    hi=enc(blocs[ids,proj.argmax(1)])
    q0=np.maximum(hi,lo)
    q1=np.minimum(hi,lo)
    c0,c1=dec(q0),dec(q1)
    palette=np.stack((c0,c1,(2*c0+c1)//3,(c0+2*c1)//3),axis=1)
    choix=np.argmin(((blocs[:,:,None,:]-palette[:,None,:,:])**2).sum(-1),axis=2).astype(np.uint32)
    choix[q0==q1]=0
    bits=np.bitwise_or.reduce(choix<<(2*np.arange(16,dtype=np.uint32)),axis=1)
    return np.column_stack((q0|(q1<<16),bits)).astype("<u4").tobytes()


def comprimer(im):
    """Suite complète BC1. Les données écrites sont indépendantes du jeu commercial."""
    niveau=im.convert("RGB")
    sortie=bytearray()
    while True:
        w,h=niveau.size
        niveau_compresse=blocs_bc1(niveau)
        sortie.extend(pack("<I",len(niveau_compresse)))
        sortie.extend(niveau_compresse)
        if w==1 and h==1:
            return bytes(sortie)
        niveau=niveau.resize((max(1,w//2),max(1,h//2)),Image.Resampling.LANCZOS)


def extraire(atlas):
    w,h=atlas.size
    if abs(w-h)>max(w,h)*.04:
        raise ValueError("L'atlas attendu a deux bandes dans une image carrée")
    y=h//2
    chambres=atlas.crop((0,0,w,y))
    # Les guichets du hall encadrent la porte centrale, un matériau séparé dans le DFF.
    baie=round(w/3)
    gauche=atlas.crop((0,y,baie,h))
    droite=atlas.crop((w-baie,y,w,h))
    hall=Image.new("RGB",(2*baie,h-y))
    hall.paste(gauche,(0,0))
    hall.paste(droite,(baie,0))
    # Les impostes latérales font partie de la baie de 4,3 m qu'encadre la marquise.
    porte=atlas.crop((round(.205*w),y,round(.795*w),h))
    return (("ch",chambres,(1024,512)),("hall",hall,(1024,512)),("porte",porte,(512,512)))


def convertir(dossier, heure, apercus=None):
    suffixe = {"jour":"j","nuit":"n"}[heure]
    with Image.open(dossier/f"atlas-{heure}.png") as src:
        atlas=src.convert("RGB")
    for cle,im,taille in extraire(atlas):
        nom=f"romj_{cle}_{suffixe}"
        im=im.resize(taille,Image.Resampling.LANCZOS)
        (dossier/f"{nom}.bc1").write_bytes(comprimer(im))
        if apercus:
            apercus.mkdir(parents=True,exist_ok=True)
            im.save(apercus/f"{nom}.png")


if __name__=="__main__":
    p=ArgumentParser(description=__doc__)
    p.add_argument("--dossier",type=Path,default=Path(__file__).resolve().parents[1]/"medias"/"majestic")
    p.add_argument("--heure",choices=("jour","nuit","deux"),default="deux")
    p.add_argument("--apercus",type=Path)
    args=p.parse_args()
    for h in (("jour","nuit") if args.heure=="deux" else (args.heure,)):
        convertir(args.dossier,h,args.apercus)
