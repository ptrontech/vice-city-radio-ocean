"""Rattache les six matériaux originaux de vitrage aux seuls modèles du Majestic."""
from pathlib import Path
from struct import Struct, pack, unpack_from

import facades
import maillage_rw as rw
import textures


MATERIAUX = {
    # (nom d'atelier, dimensions, rectangle occupé dans l'ancien atlas)
    "hotelwindow1": ("ch", 1024, 512, (-.009, -2.224, .501, -2.000)),
    "hotelwindow2": ("hall", 1024, 512, (.000, -3.000, .501, -2.600)),
    "hot_doors": ("porte", 512, 512, (.000, -3.000, .500, -2.500)),
}
ARCHIVES = Path(__file__).resolve().parents[1] / "medias" / "majestic"
UV = Struct("<2f")
EMAIL_ORIGINE = "majescticalt"  # Orthographe de la native commerciale.
EMAIL = "romj_email"
# Teintes échantillonnées de l'atlas. Les champs blancs gardent leur lumière d'origine.
PIGMENTS = (
    ((210,199,107), (119,160,148)),  # pilastre vert d'eau
    ((239,174,255), (218,197,161)),  # bordure ivoire
    ((202,116,238), (193,133,115)),  # arête corail
    ((86,110,181), (93,122,117)),    # retour vert grisé
)


def nom_natif(type_baie, nuit):
    return f"romj_{type_baie}_{'n' if nuit else 'j'}"


def refermer(version, parties, groupe, geo):
    rw.remplacer(groupe, rw.GEOMETRY, rw.assembler(geo))
    rw.remplacer(parties, rw.GEOMETRY_LIST, rw.assembler(groupe))
    return textures.wrap(rw.CLUMP, version, rw.assembler(parties))


def preparer_uv(blob):
    """Déplie chaque morceau d'atlas avant interpolation des UV sur les murs ombrés."""
    version, parties, groupe, geo, g, mats = rw.ouvrir_modele(blob)
    noms = rw.noms_materiaux(mats)
    if not set(MATERIAUX).issubset(noms) or len(g.uv) != 1:
        raise ValueError("Les matériaux attendus du Majestic ne sont pas présents")
    par_materiau = {}
    for b, a, indice, c in rw.TRI.iter_unpack(g.faces):
        par_materiau.setdefault(noms[indice], set()).update((a, b, c))
    uv = bytearray(g.uv[0])
    couleurs = bytearray(g.couleurs)
    # Le modèle de nuit contient le matériau d’occultation « black ». Le verre des
    # chambres d’origine y est presque noir. Le fond lumineux est visible derrière la vitre.
    nuit = "black" in noms
    for nom, (_, largeur, hauteur, cadre) in MATERIAUX.items():
        indices = par_materiau[nom]
        if any(indices & autres for cle, autres in par_materiau.items() if cle != nom):
            raise ValueError(f"Sommets partagés entre un vitrage et un autre matériau : {nom}")
        x0, y0, x1, y1 = cadre
        for i in indices:
            u, v = UV.unpack_from(uv, i * UV.size)
            s, t = (u-x0)/(x1-x0), (v-y0)/(y1-y0)
            if not (-.09 <= s <= 1.09 and -.09 <= t <= 1.09):
                raise ValueError(f"Le tracé UV de {nom} diffère du modèle reconnu")
            # Un demi-texel protège les joints des atlas en filtrage bilinéaire.
            u = (0.5+min(1.,max(0.,s))*(largeur-1))/largeur
            v = (0.5+min(1.,max(0.,t))*(hauteur-1))/hauteur
            UV.pack_into(uv, i*UV.size, u, v)
            if nuit:
                plancher = (91,82,69) if nom == "hotelwindow1" else (77,69,56)
                for canal, minimum in enumerate(plancher):
                    k = 4*i+canal
                    couleurs[k] = minimum+round((255-minimum)*couleurs[k]/255)
    g.uv[0] = bytes(uv)
    g.couleurs = bytes(couleurs)
    rw.remplacer(geo, rw.STRUCT, g.ecrire())
    return refermer(version, parties, groupe, geo)


def nommer_vitrages(blob, nuit):
    """Désigne les rasters personnels dans les slots de matériaux des deux seuls DFF."""
    version, parties, groupe, geo, _, mats = rw.ouvrir_modele(blob)
    touches = set()
    for i, (kind, mat_version, payload) in enumerate(mats):
        if kind != rw.MATERIAL:
            continue
        mat = list(textures.chunks(payload))
        slots = [(j, ver, data) for j, (k, ver, data) in enumerate(mat) if k == 6]
        for j, tex_version, data in slots:
            tex = list(textures.chunks(data))
            k = next(i for i, (tag, _, _) in enumerate(tex) if tag == 2)
            tag, str_version, chaine = tex[k]
            nom = textures.name(chaine)
            if nom == EMAIL_ORIGINE:
                nouveau = EMAIL
            elif nom in MATERIAUX:
                nouveau = nom_natif(MATERIAUX[nom][0], nuit)
            else:
                continue
            octets = nouveau.encode("ascii") + b"\0"
            tex[k] = tag, str_version, octets.ljust((len(octets)+3)//4*4, b"\0")
            mat[j] = 6, tex_version, rw.assembler(tex)
            mats[i] = kind, mat_version, rw.assembler(mat)
            touches.add(nom)
    if touches != set(MATERIAUX) | {EMAIL_ORIGINE}:
        raise ValueError("Le nom d'un vitrage n'a pas été adapté dans le modèle")
    rw.remplacer(geo, rw.MATLIST, rw.assembler(mats))
    return refermer(version, parties, groupe, geo)


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


def native_personnelle(nom, largeur, hauteur, nombre, data, modele):
    ver, inner, raster = modele
    if unpack_from("<IIHHBBBB",raster,72)[0:2] != (0x200,0) or raster[87] != 1:
        raise ValueError(f"Le modèle de raster {nom} n'est pas reconnu")
    header = raster[:8]+nom.encode("ascii").ljust(32,b"\0")+bytes(32)
    header += pack("<IIHHBBBB",0x8200,0,largeur,hauteur,16,nombre,4,1)
    elements = list(inner)
    elements[0] = elements[0][0],elements[0][1],header+data
    return 0x15,ver,rw.assembler(elements)


def ajouter_vitrages(blob, dossier=ARCHIVES):
    """Garde chaque native existante et insère les nouveaux rasters avant l'extension TXD."""
    version, parts = textures.dictionary(blob)
    natives = list(textures.natives(parts))
    par_nom = {nom:(ver, inner, raster) for _, ver, inner, nom, raster in natives}
    ajouts = []
    for original, (type_baie, largeur, hauteur, _) in MATERIAUX.items():
        for nuit in (False,True):
            nom = nom_natif(type_baie,nuit)
            if nom in par_nom:
                raise ValueError(f"Nom de texture déjà présent : {nom}")
            count,data = lire_niveaux(dossier/(nom+".bc1"),largeur,hauteur)
            ajouts.append(native_personnelle(nom,largeur,hauteur,count,data,par_nom[original]))
    if EMAIL in par_nom:
        raise ValueError("Émail du Majestic déjà présent")
    count,data = emailler(par_nom[EMAIL_ORIGINE][2])
    ajouts.append(native_personnelle(EMAIL,128,128,count,data,par_nom[EMAIL_ORIGINE]))
    i = rw.entree(parts,rw.STRUCT)
    kind, ver, structure = parts[i]
    if unpack_from("<H",structure)[0] != len(natives):
        raise ValueError("Nombre initial de rasters du dictionnaire incorrect")
    parts[i] = kind,ver,pack("<H",len(natives)+len(ajouts))+structure[2:]
    insert = rw.entree(parts,rw.EXTENSION)
    parts[insert:insert] = ajouts
    return textures.wrap(0x16,version,rw.assembler(parts))
