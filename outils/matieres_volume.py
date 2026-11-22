"""Matières tilables pour des volumes 3D et émail de la façade personnelle."""
from pathlib import Path
from struct import pack,unpack_from
import facades
import maillage_rw as rw
import textures
from volume_rw import NOMS

ARCHIVES=Path(__file__).resolve().parents[1]/"medias"/"matieres"
COTES={"platre":256,"bois":512,"lin":512,"laiton":64,"velours":256,
       "sol":512,"metal":64,"lumiere":64}
EMAIL_ORIGINE = "majescticalt"  # Orthographe de la native commerciale.
EMAIL = "romj_email"
# Teintes échantillonnées de l'atlas. Les champs blancs gardent leur lumière d'origine.
PIGMENTS = (
    ((210,199,107), (119,160,148)),  # pilastre vert d'eau
    ((239,174,255), (218,197,161)),  # bordure ivoire
    ((202,116,238), (193,133,115)),  # arête corail
    ((86,110,181), (93,122,117)),    # retour vert grisé
)


def lire_niveaux(fichier, largeur, hauteur):
    data = fichier.read_bytes()
    pos = 0
    niveaux = 0
    while True:
        n = ((largeur+3)//4)*((hauteur+3)//4)*8
        if pos+4+n > len(data) or unpack_from("<I",data,pos)[0] != n:
            raise ValueError(f"Niveau BC1 absent ou tronqué dans {fichier.name}")
        pos += 4+n
        niveaux += 1
        if (largeur,hauteur) == (1,1):
            break
        largeur,hauteur = max(1,largeur//2), max(1,hauteur//2)
    if pos != len(data):
        raise ValueError(f"Données après le dernier niveau de {fichier.name}")
    return niveaux, data


def pigment(rgb):
    if max(rgb)-min(rgb)<28:
        return rgb
    def ecart(teinte):
        return sum((a-b)**2 for a,b in zip(rgb,teinte[0]))
    source, destination = min(PIGMENTS,key=ecart)
    if ecart((source,destination))>70**2:
        return rgb
    luminosite = sum(k*(a-b) for k,a,b in zip((.30,.59,.11),rgb,source))
    return tuple(min(255,max(0,round(v+luminosite))) for v in destination)


def emailler(raster):
    meta = facades.lire_raster(raster)
    if (meta["w"],meta["h"],meta["niveaux"]) != (128,128,1):
        raise ValueError("Le nuancier d'origine du Majestic est incompatible")
    plans = facades.decoder_bc1(meta["mips"][0],128,128)
    # Le nuancier BC1 réutilise un petit nombre de valeurs. Garder les nuances du stuc.
    pixels = list(zip(*plans))
    couleurs = {p:pigment(p) for p in set(pixels)}
    niveaux = facades.chaine_mipmaps(list(zip(*(couleurs[p] for p in pixels))),128)
    return len(niveaux), b"".join(pack("<I",len(n))+n for n in niveaux)


def ajouter_native(nom,cote,niveaux,data,modele,verre=False):
    v,inner,original=modele
    if original[87]!=(3 if verre else 1):
        raise ValueError(f"Codec natif de la matière incompatible : {nom}")
    header=original[:8]+nom.encode("ascii").ljust(32,b"\x00")+bytes(32)
    header+=pack("<IIHHBBBB",0x8300 if verre else 0x8200,int(verre),cote,cote,16,niveaux,4,3 if verre else 1)
    ch=list(inner)
    ch[0]=ch[0][0],ch[0][1],header+data
    return 0x15,v,rw.assembler(ch)


def verre_clair():
    # BC2 / DXT3. Les deux panneaux du hall conservent 93 % de transmission.
    result=bytearray()
    for n in (16,8,4,2,1):
        nb=((n+3)//4)**2
        # Alpha 1/15 et une nuance gris-bleu uniforme, sans reflet de scène dessiné.
        bloc=bytes([0x11]*8)+pack("<HHI",0xB658,0xB658,0)
        result.extend(pack("<I",16*nb)+bloc*nb)
    return 5,bytes(result)


def ajouter_matieres(blob):
    ver,parts=textures.dictionary(blob)
    natives={nom:(v,inner,raster) for _,v,inner,nom,raster in textures.natives(parts)}
    noms={EMAIL,*NOMS.values()}
    if set(natives)&noms:
        raise ValueError("Une matière de l'atelier est déjà dans le dictionnaire de départ")
    ajouts=[]
    for cle,cote in COTES.items():
        nb,data=lire_niveaux(ARCHIVES/(cle+".bc1"),cote,cote)
        ajouts.append(ajouter_native(NOMS[cle],cote,nb,data,natives["hotelwindow1"]))
    nb,data=verre_clair()
    ajouts.append(ajouter_native(NOMS["verre"],16,nb,data,natives["fpbarnight"],verre=True))
    nb,data=emailler(natives[EMAIL_ORIGINE][2])
    ajouts.append(ajouter_native(EMAIL,128,nb,data,natives[EMAIL_ORIGINE]))
    tag,v,payload=parts[rw.entree(parts,rw.STRUCT)]
    if unpack_from("<H",payload)[0]!=len(natives):
        raise ValueError("Table initiale des textures incorrecte")
    rw.remplacer(parts,tag,pack("<H",len(natives)+len(ajouts))+payload[2:])
    i=rw.entree(parts,rw.EXTENSION)
    parts[i:i]=ajouts
    return textures.wrap(0x16,ver,rw.assembler(parts))


def nommer_email(blob):
    ver,parts,gr,geo,g,mats=rw.ouvrir_modele(blob)
    trouve=False
    for i,(tag,mver,data) in enumerate(mats):
        if tag!=rw.MATERIAL:
            continue
        mat=list(textures.chunks(data))
        for j,(t,tver,payload) in enumerate(mat):
            if t!=6:
                continue
            tex=list(textures.chunks(payload))
            k=next(l for l,(tag_s,_,_) in enumerate(tex) if tag_s==2)
            st,sv,s=tex[k]
            if textures.name(s)!=EMAIL_ORIGINE:
                continue
            texte=EMAIL.encode("ascii")+bytes(1)
            tex[k]=st,sv,texte.ljust((len(texte)+3)//4*4,bytes(1))
            mat[j]=t,tver,rw.assembler(tex)
            mats[i]=tag,mver,rw.assembler(mat)
            trouve=True
    if not trouve:
        raise ValueError("La matière d'émail du Majestic est absente")
    rw.remplacer(geo,rw.MATLIST,rw.assembler(mats))
    rw.remplacer(gr,rw.GEOMETRY,rw.assembler(geo))
    rw.remplacer(parts,rw.GEOMETRY_LIST,rw.assembler(gr))
    return textures.wrap(rw.CLUMP,ver,rw.assembler(parts))
