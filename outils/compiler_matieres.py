"""Prépare les revêtements réutilisables des objets 3D du quartier (outil de création)."""
from argparse import ArgumentParser
from hashlib import sha256
import json
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


def surface(im, cle):
    # Les teintes de chaque meuble proviennent de ses propres sommets prééclairés.
    # Le matériau fournit les nervures, fibres et inclusions indépendantes de la pièce.
    taille = 512 if cle in {"bois","sol","lin"} else 256
    img=im.convert("RGB").resize((taille,taille),Image.Resampling.LANCZOS)
    a=np.asarray(img,dtype=float)
    lum=.30*a[:,:,0]+.59*a[:,:,1]+.11*a[:,:,2]
    p10,p90=np.percentile(lum,(10,90))
    amplitude={"bois":75,"lin":51,"platre":28,"sol":105,"velours":58}[cle]
    l=213+(lum-np.mean(lum))*amplitude/max(15,p90-p10)
    # Préserve un peu de la couleur des grains de pierre et du noyer.
    chroma=(a-lum[:,:,None])
    if cle not in {"sol","bois"}:
        chroma*=.10
    else:
        chroma-=chroma.mean((0,1))
        chroma*=.42
    return Image.fromarray((l[:,:,None]+chroma).clip(42,255).astype("uint8"))


def metallerie(taille, cle):
    rng=np.random.default_rng({"laiton":54,"metal":75,"lumiere":92}[cle])
    y,x=np.mgrid[:taille,:taille]
    if cle=="lumiere":
        luminance=246+2*np.cos(x/12)*np.sin(y/9)+rng.normal(0,.7,x.shape)
    else:
        lignes=rng.normal(0,2.5,taille)
        luminance=228+lignes[y]+2.0*np.sin((x+3*y)*np.pi*2/taille)+rng.normal(0,.9,x.shape)
    return Image.fromarray(np.repeat(luminance[:,:,None].clip(0,255).astype("uint8"),3,axis=2))


def compiler(cache,sortie):
    sortie.mkdir(parents=True,exist_ok=True)
    refs=json.loads((sortie/"sources.json").read_text(encoding="utf8"))
    for cle,info in refs.items():
        fichier=cache/(info["asset"]+".jpg")
        if sha256(fichier.read_bytes()).hexdigest()!=info["sha256"]:
            raise ValueError("Source de matière incorrecte : "+info["asset"])
        with Image.open(fichier) as src:
            (sortie/(cle+".bc1")).write_bytes(comprimer(surface(src,cle)))
    for cle in ("metal","laiton","lumiere"):
        (sortie/(cle+".bc1")).write_bytes(comprimer(metallerie(64,cle)))


if __name__=="__main__":
    p=ArgumentParser(description=__doc__)
    p.add_argument("cache",type=Path,help="Dossier des cinq photos de matière Poly Haven")
    p.add_argument("--sortie",type=Path,default=Path(__file__).resolve().parents[1]/"medias"/"matieres")
    args=p.parse_args()
    compiler(args.cache,args.sortie)
