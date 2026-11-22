"""Habille une seule face de panneau à Escobar International avec l’affiche du projet."""
from pathlib import Path
from struct import pack, pack_into, unpack_from

import maillage_rw as rw
import textures
from matieres_volume import lire_niveaux

NOM = "ro_oceandrive"
SOURCE = "ap_billb2"
MODELE = "ap_billboards3.dff"
DICTIONNAIRE = "ap_billboard.txd"
FICHIER = Path(__file__).resolve().parents[1] / "medias" / "affiche" / "ocean-drive.bc1"
LARGEUR, HAUTEUR = 512, 256


def preparer_image(photo, sortie):
    from PIL import Image
    from compiler_matieres import comprimer
    with Image.open(photo) as im:
        # Le support mesure 15,66 x 8,69 m. Conserver le lettrage au recadrage.
        largeur = min(im.width, round(im.height * 15.66 / 8.69))
        gauche = round((im.width - largeur) * .17)
        affiche = im.crop((gauche, 0, gauche + largeur, im.height))
        native = affiche.resize((LARGEUR, HAUTEUR), Image.Resampling.LANCZOS)
        Path(sortie).write_bytes(comprimer(native))


def poser_dictionnaire(blob):
    version, parts = textures.dictionary(blob)
    natives = {name:(v, inner, data) for _, v, inner, name, data in textures.natives(parts)}
    if NOM in natives:
        return blob
    v, inner, original = natives[SOURCE]
    if original[87] != 1 or unpack_from("<I",original)[0] != 8:
        raise ValueError("Le panneau attendu est une texture PC BC1.")
    niveaux, blocs = lire_niveaux(FICHIER, LARGEUR, HAUTEUR)
    entete = original[:8] + NOM.encode("ascii").ljust(32,b"\0") + bytes(32)
    entete += pack("<IIHHBBBB",0x8200,0,LARGEUR,HAUTEUR,16,niveaux,4,1)
    inner = list(inner)
    inner[0] = inner[0][0], inner[0][1], entete+blocs
    i = rw.entree(parts,rw.STRUCT)
    tag, ver, desc = parts[i]
    if unpack_from("<H",desc)[0] != len(natives):
        raise ValueError("Le nombre de textures de l’aéroport est incohérent.")
    parts[i] = tag,ver,pack("<H",len(natives)+1)+desc[2:]
    parts.insert(rw.entree(parts,rw.EXTENSION),(0x15,v,rw.assembler(inner)))
    return textures.wrap(0x16,version,rw.assembler(parts))


def poser_modele(blob):
    ver, parties, groupe, geo, geometrie, mats = rw.ouvrir_modele(blob)
    noms = rw.noms_materiaux(mats)
    if NOM in noms:
        return blob
    if noms.count(SOURCE)!=1:
        raise ValueError("Le support d’affiche ne correspond pas au panneau attendu.")
    indice = noms.index(SOURCE)
    rect, autres = set(), set()
    for b,a,m,c in rw.TRI.iter_unpack(geometrie.faces):
        (rect if m==indice else autres).update((a,b,c))
    if len(rect)!=4 or rect & autres:
        raise ValueError("La face d’affichage ne forme pas un rectangle indépendant.")
    uv = bytearray(geometrie.uv[0])
    for k in rect:
        u,v = unpack_from("<2f",uv,k*8)
        if not (-.005<=u<=1.005 and .495<=v<=1.005):
            raise ValueError("La face sélectionnée n’utilise plus la moitié basse du panneau.")
        pack_into("<2f",uv,k*8,u,2*v-1)
    geometrie.uv[0] = bytes(uv)
    for i,(tag,mver,data) in enumerate(mats):
        if tag!=rw.MATERIAL:
            continue
        mat=list(textures.chunks(data))
        j=next((i for i,(t,_,_) in enumerate(mat) if t==6),None)
        if j is None: continue
        t,tver,payload=mat[j]
        tex=list(textures.chunks(payload))
        k=next(i for i,(s,_,_) in enumerate(tex) if s==2)
        s,sv,ancien=tex[k]
        if textures.name(ancien)!=SOURCE: continue
        texte=NOM.encode("ascii")+b"\0"
        tex[k]=s,sv,texte.ljust((len(texte)+3)//4*4,b"\0")
        mat[j]=t,tver,rw.assembler(tex)
        mats[i]=tag,mver,rw.assembler(mat)
        break
    rw.remplacer(geo,rw.MATLIST,rw.assembler(mats))
    rw.remplacer(geo,rw.STRUCT,geometrie.ecrire())
    rw.remplacer(groupe,rw.GEOMETRY,rw.assembler(geo))
    rw.remplacer(parties,rw.GEOMETRY_LIST,rw.assembler(groupe))
    return textures.wrap(rw.CLUMP,ver,rw.assembler(parties))


EFFETS_AFFICHE = {MODELE:poser_modele, DICTIONNAIRE:poser_dictionnaire}
