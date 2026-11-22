"""Ouvrir un volume dans un modèle RenderWare et y poser des triangles texturés."""
from collections import defaultdict
from dataclasses import dataclass
from math import dist, isfinite, sqrt
from struct import Struct, pack, unpack_from

import maillage_rw as rw
from ombres_majestic import croix, liste_indices, produit, unite, vecteur
from textures import chunks, wrap


UV = Struct("<2f")
OUVERTURES = {"hotelwindow1","hotelwindow2","hot_doors"}
PEAUX = {"hotelpeach","majescticalt","clevelanderdetails","black"}
NOMS = {"platre":"ro_platre","bois":"ro_noyer","lin":"ro_lin","laiton":"ro_laiton",
        "velours":"ro_velours","sol":"ro_terrazzo","metal":"ro_acier",
        "lumiere":"ro_opaline","verre":"ro_glace"}


@dataclass(frozen=True)
class Sommet:
    position: tuple
    couleur: tuple
    uv: tuple
    normale: tuple = ()

    def entre(self, autre, t):
        def melanger(a,b):
            return tuple(x+(y-x)*t for x,y in zip(a,b))
        return Sommet(melanger(self.position,autre.position),melanger(self.couleur,autre.couleur),
                      melanger(self.uv,autre.uv),melanger(self.normale,autre.normale))


class Sommets:
    """Conserve les coutures UV et les discontinuités d'éclairage du modèle."""
    def __init__(self, geo):
        if len(geo.uv)!=1:
            raise ValueError("Ce modèle doit porter une couche UV")
        self.geo = geo
        self.position = bytearray(geo.positions)
        self.couleurs = bytearray(geo.couleurs)
        self.uv = bytearray(geo.uv[0])
        self.normales = bytearray(geo.normales)
        self.avec_normales = bool(geo.normales)
        self.cache = {}
        self.rayon = geo.sphere[3]

    def lire(self, i):
        return Sommet(rw.VEC.unpack_from(self.position,i*12),tuple(self.couleurs[i*4:i*4+4]),
                      UV.unpack_from(self.uv,i*8),rw.VEC.unpack_from(self.normales,i*12) if self.avec_normales else ())

    def ajouter(self, v):
        if not all(isfinite(q) for q in (*v.position,*v.uv,*v.couleur)):
            raise ValueError("Sommet non fini dans le volume")
        p=rw.VEC.pack(*v.position)
        c=bytes(min(255,max(0,round(x))) for x in v.couleur)
        uv=UV.pack(*v.uv)
        n=rw.VEC.pack(*unite(v.normale)) if self.avec_normales else b""
        key=(p,c,uv,n)
        i=self.cache.get(key)
        if i is None:
            i=len(self.position)//12
            if i>=65535:
                raise ValueError("Le modèle atteint la limite RenderWare de 65 535 sommets")
            self.cache[key]=i
            self.position.extend(p)
            self.couleurs.extend(c)
            self.uv.extend(uv)
            self.normales.extend(n)
            self.rayon=max(self.rayon,dist(v.position,self.geo.sphere[:3])+.01)
        return i

    def terminer(self, faces):
        g=self.geo
        g.positions=bytes(self.position)
        g.couleurs=bytes(self.couleurs)
        g.uv=[bytes(self.uv)]
        g.normales=bytes(self.normales)
        g.faces=b"".join(rw.TRI.pack(b,a,m,c) for a,b,c,m in faces)
        g.flags &= ~1
        g.sphere=(*g.sphere[:3],self.rayon,*g.sphere[4:])


def aire_double(a,b,c):
    n=croix(vecteur(b,a),vecteur(c,a))
    return sqrt(produit(n,n))


def decouper(polygone, direction, offset):
    """Coupe un polygone convexe. Le plan est inclus dans la moitié intérieure."""
    dedans,dehors=[],[]
    a=polygone[-1]
    da=produit(a.position,direction)-offset
    for b in polygone:
        db=produit(b.position,direction)-offset
        ia,ib=da>=-1e-7,db>=-1e-7
        if ia!=ib:
            intersection=a.entre(b,max(0.,min(1.,da/(da-db))))
            dedans.append(intersection)
            dehors.append(intersection)
        (dedans if ib else dehors).append(b)
        a,da=b,db
    return dedans,dehors


def prisme(panneau):
    t=(*panneau["t"],0.)
    n=(*panneau["n"],0.)
    z=(0.,0.,1.)
    limites=((t,panneau["s0"]-.002,panneau["s1"]+.002),
             (z,panneau["z0"]-.002,panneau["z1"]+.002),(n,panneau["d"]-1.1,panneau["d"]+.008))
    return tuple(plan for axe,mini,maxi in limites for plan in
                 ((axe,mini),(tuple(-a for a in axe),-maxi)))


def retirer_prisme(polygone, plans):
    for axe,borne in plans:
        if max(produit(v.position,axe) for v in polygone)<borne-1e-7:
            return [polygone]
    reste=polygone
    sorties=[]
    for axe,borne in plans:
        reste,exterieur=decouper(reste,axe,borne)
        if len(reste)<3:
            return [polygone]
        if len(exterieur)>=3:
            sorties.append(exterieur)
    if sum(aire_double(reste[0].position,reste[i].position,reste[i+1].position)
           for i in range(1,len(reste)-1))<1e-6:
        return [polygone]
    return sorties


def terminer_modele(ouvert, sommets, faces):
    ver,parties,groupe,geo,g,mats=ouvert
    sommets.terminer(faces)
    extensions=list(chunks(rw.corps(geo,rw.EXTENSION)))
    rw.remplacer(extensions,rw.BIN_MESH,liste_indices(faces))
    rw.remplacer(geo,rw.EXTENSION,rw.assembler(extensions))
    rw.remplacer(geo,rw.STRUCT,g.ecrire())
    rw.remplacer(geo,rw.MATLIST,rw.assembler(mats))
    rw.remplacer(groupe,rw.GEOMETRY,rw.assembler(geo))
    rw.remplacer(parties,rw.GEOMETRY_LIST,rw.assembler(groupe))
    return wrap(rw.CLUMP,ver,rw.assembler(parties))


def ouvrir_baies(blob, panneaux):
    """Retire les vitrages opaques et découpe les murs de doublage dans chaque ouverture."""
    modele=rw.ouvrir_modele(blob)
    g,mats=modele[-2:]
    noms=rw.noms_materiaux(mats)
    cache=Sommets(g)
    faces=[]
    plans=[prisme(p) for p in panneaux]
    for b,a,m,c in rw.TRI.iter_unpack(g.faces):
        nom=noms[m]
        if nom in OUVERTURES:
            continue
        if nom not in PEAUX:
            faces.append((a,b,c,m))
            continue
        original=[cache.lire(i) for i in (a,b,c)]
        pieces=[original]
        for limites in plans:
            pieces=[bout for poly in pieces for bout in retirer_prisme(poly,limites)]
            if not pieces:
                break
        if len(pieces)==1 and pieces[0] is original:
            faces.append((a,b,c,m))
            continue
        for poly in pieces:
            for i in range(1,len(poly)-1):
                t=(poly[0],poly[i],poly[i+1])
                if aire_double(*(v.position for v in t))>1e-7:
                    faces.append((*[cache.ajouter(v) for v in t],m))
    return terminer_modele(modele,cache,faces)


def materiau_texture(mats, nom):
    tag,version,table=mats[rw.entree(mats,rw.STRUCT)]
    nombre,=unpack_from("<I",table)
    rw.remplacer(mats,tag,pack("<I",nombre+1)+table[4:]+pack("<i",-1))
    # Les artistes prééclairent chaque surface par sommet. Le verre doit garder
    # de la transparence par sa native DXT3, y compris dans un maillage mixte.
    amb,diff=(.08,.06) if nom=="lumiere" else (.10,.16)
    mat=pack("<I",0)+rw.WHITE+pack("<2I3f",0,1,amb,0.,diff)
    texte=NOMS[nom].encode("ascii")+b"\0"
    tex=wrap(rw.STRUCT,version,pack("<I",0x1106))+wrap(2,version,texte.ljust((len(texte)+3)//4*4,b"\0"))
    tex+=wrap(2,version,bytes(4))+wrap(rw.EXTENSION,version,b"")
    payload=wrap(rw.STRUCT,version,mat)+wrap(6,version,tex)+wrap(rw.EXTENSION,version,b"")
    mats.append((rw.MATERIAL,version,payload))
    return nombre


def meubler(blob, triangles):
    """Ajoute les objets et leurs matériaux. La dernière passe dessine les surfaces vitrées."""
    modele=rw.ouvrir_modele(blob)
    g,mats=modele[-2:]
    cache=Sommets(g)
    faces=[(a,b,c,m) for b,a,m,c in rw.TRI.iter_unpack(g.faces)]
    par_matiere=defaultdict(list)
    for nom,*coords in triangles:
        if nom not in NOMS or len(coords)!=3 or any(len(v)!=8 for v in coords):
            raise ValueError(f"Triangle ou matériau intérieur inconnu : {nom}")
        par_matiere[nom].append(coords)
    if not par_matiere:
        raise ValueError("Le volume ne contient aucun meuble ni mur")
    for nom in NOMS:
        if nom not in par_matiere:
            continue
        m=materiau_texture(mats,nom)
        for coords in par_matiere[nom]:
            a,b,c=[v[:3] for v in coords]
            normal=unite(croix(vecteur(b,a),vecteur(c,a)))
            if normal==(0.,0.,0.):
                continue
            ids=[]
            for v in coords:
                ids.append(cache.ajouter(Sommet(v[:3],(*v[3:6],255),v[6:],normal)))
            faces.append((*ids,m))
    return terminer_modele(modele,cache,faces)
