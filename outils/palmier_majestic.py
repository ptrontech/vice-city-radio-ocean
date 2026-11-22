"""Palmier en folioles 3D pour le modèle 459 devant le Majestic (Vice City PC).

Le générateur reprend le repère, les mesures et le matériau d'écorce de l'exemplaire
local du joueur. Les folioles sont des surfaces repliées recto-verso. Aucun TXD requis.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import cos, dist, hypot, pi, sin, sqrt
from struct import pack, unpack_from

import maillage_rw as rw
from textures import chunks, wrap

NOM = "veg_palmkbb11.dff"
SOURCE = ("kbbark_test1", "fuzzyplant256")
TAU = 2*pi


@dataclass(frozen=True)
class Silhouette:
    centre: tuple
    pied: tuple
    rayon_pied: tuple
    sommet_tronc: tuple
    bornes: tuple
    sphere: tuple

    @classmethod
    def mesurer(cls,g):
        pts = list(rw.VEC.iter_unpack(g.positions))
        faces = list(rw.TRI.iter_unpack(g.faces))
        tronc = {pts[i] for b,a,m,c in faces if m == 0 for i in (a,b,c)}
        if len(tronc) < 12:
            raise ValueError("Tronc source incomplet")
        def limites(v):
            return tuple((min(k),max(k)) for k in zip(*v))
        bornes = limites(pts)
        bas,haut = min(v[2] for v in tronc), max(v[2] for v in tronc)
        r0 = limites([p for p in tronc if p[2] < bas+.07])
        r1 = limites([p for p in tronc if p[2] > haut-.07])
        milieu = lambda r: tuple((a+b)/2 for a,b in r)
        return cls(milieu(bornes),(*milieu(r0)[:2], bas),
                   tuple((b-a)/2 for a,b in r0[:2]),milieu(r1),bornes,g.sphere)


def couleur(rgb, facteur):
    return tuple(min(255,max(0,round(c*facteur))) for c in rgb)


def sommet(p, rgb, uv=(0.,0.)):
    return tuple(p),tuple(rgb),uv


class Maillage:
    def __init__(self):
        self.index = {}
        self.positions, self.normales, self.uv = [], [], []
        self.couleurs = bytearray()
        self.faces = defaultdict(list)

    def triangle(self,materiau,a,b,c):
        pa,pb,pc = a[0],b[0],c[0]
        ux,uy,uz = [pb[j]-pa[j] for j in range(3)]
        vx,vy,vz = [pc[j]-pa[j] for j in range(3)]
        n = (uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx)
        longueur = sqrt(sum(v*v for v in n))
        if longueur < 1e-8:
            return
        n = tuple(round(v/longueur,5) for v in n)
        ids = []
        for p,rgb,uv in (a,b,c):
            cle = (p,rgb,uv,n)
            i = self.index.get(cle)
            if i is None:
                i = len(self.positions)
                if i >= 65535:
                    raise ValueError("Limite d'indices RenderWare")
                self.index[cle] = i
                self.positions.append(p)
                self.normales.append(n)
                self.uv.append(uv)
                self.couleurs.extend((*rgb,255))
            ids.append(i)
        self.faces[materiau].append(tuple(ids))

    def feuille(self,a,b,c):
        # Le moteur peut éliminer les faces arrière. Une vraie face porte la normale
        # de chaque côté de la foliole, avec un revers moins saturé.
        self.triangle(1,a,b,c)
        def revers(v):
            return sommet(v[0],couleur(v[1],.79),v[2])
        self.triangle(1,revers(c),revers(b),revers(a))


def construire_tronc(m,forme):
    x,y,z0 = forme.pied
    x1,y1,z1 = forme.sommet_tronc
    rx,ry = forme.rayon_pied
    hauteur = forme.bornes[2][1]-z0
    couronne = (x1+.04, y1+.03, z0+hauteur*.740)
    z_fin = couronne[2]+.13
    # Chaque cicatrice foliaire possède une lèvre et une gorge réelles. Les UV
    # d'écorce suivent toute la hauteur, autour des dix pans du tronc.
    anneaux = [(z0,1.0,1.0)]
    for i in range(1,19):
        t=i/19
        z=z0+(z_fin-z0)*t
        anneaux.extend(((z-.045,1.0,.89),(z,1.085,1.10),(z+.032,.98,.97)))
    anneaux.append((z_fin,.99,1.0))
    ronds=[]
    for z,relief,ton in anneaux:
        t=(z-z0)/(z_fin-z0)
        courbe=min(1.,(z-z0)/(z1-z0))
        cx=x+(x1-x)*courbe+max(0.,t-.74)*.12
        cy=y+(y1-y)*courbe+max(0.,t-.74)*.10
        rayon = .39+.61*(1-t)**2.7+.16*max(0.,(t-.72)/.28)
        result=[]
        for j in range(11):
            a=TAU*(j%10)/10
            irreg=1+.017*sin(3*a+.55)
            xyz=(cx+rx*rayon*relief*irreg*cos(a),cy+ry*rayon*relief*irreg*sin(a),z)
            rgb=couleur((172,162,132) if t<.79 else (122,145,91),ton*(.94+.06*cos(a-.6)))
            result.append(sommet(xyz,rgb,(j/10,(z-z0)*.98)))
        ronds.append(result)
    for bas,haut in zip(ronds,ronds[1:]):
        for j in range(10):
            m.triangle(0,bas[j],bas[j+1],haut[j+1])
            m.triangle(0,bas[j],haut[j+1],haut[j])
    for j in range(1,9):
        m.triangle(0,ronds[0][0],ronds[0][j+1],ronds[0][j])
        m.triangle(0,ronds[-1][0],ronds[-1][j],ronds[-1][j+1])
    return couronne


def palme(m,coeur,angle,longueur,arche,chute,paires,teinte,variation):
    radial=(cos(angle),sin(angle)); travers=(-radial[1],radial[0])
    def point(t):
        rotation=.16*sin(variation)*sin(pi*t)+.13*cos(variation+.4)*t*t
        a=angle+rotation
        return (coeur[0]+longueur*t*cos(a),coeur[1]+longueur*t*sin(a),
                coeur[2]+arche*4*t*(1-t)+chute*t**1.8)

    # Rachis triangulaire fermé ; l'arête claire suit sa courbure.
    sections=[]
    for i in range(8):
        t=i/7
        x,y,z=point(t)
        ep=.008+.048*(1-t)**1.4
        sections.append([sommet((x+travers[0]*ep,y+travers[1]*ep,z),couleur(teinte,.86)),
                         sommet((x-travers[0]*ep,y-travers[1]*ep,z),couleur(teinte,.86)),
                         sommet((x,y,z+ep*.95),couleur(teinte,1.40))])
    for a,b in zip(sections,sections[1:]):
        for j in range(3):
            k=(j+1)%3
            m.triangle(1,a[j],b[j],b[k])
            m.triangle(1,a[j],b[k],a[k])

    for i in range(paires):
        for cote in (-1,1):
            t=.10+.82*(i+(.23 if cote>0 else 0))/(paires-1+.24)
            x,y,z=point(t)
            l=(.23+.52*sin(pi*t)**.77)*(1-.36*t)*(1+.09*sin(variation+i*2.1+cote))
            dx=radial[0]*(.25+.34*t)+travers[0]*cote
            dy=radial[1]*(.25+.34*t)+travers[1]*cote
            h=hypot(dx,dy)
            dx,dy=dx/h,dy/h
            lx,ly=-dy,dx
            pente=l*(.29+.28*t+.10*cos(variation+i))
            largeur=(.037+.024*sin(pi*t))* (1+.10*sin(variation+i))
            ton=1+.075*sin(variation+1.31*i+cote*.4)
            base=sommet((x,y,z+.008),couleur(teinte,.79*ton))
            pointe=sommet((x+dx*l,y+dy*l,z-pente),couleur(teinte,1.24*ton))
            xm,ym=x+.39*l*dx,y+.39*l*dy
            zm=z+.045-.26*pente
            e1=sommet((xm+lx*largeur,ym+ly*largeur,zm+.020),couleur(teinte,1.12*ton))
            e2=sommet((xm-lx*largeur,ym-ly*largeur,zm-.014),couleur(teinte,.88*ton))
            m.feuille(base,pointe,e1)
            m.feuille(base,e2,pointe)


def construire_palmes(forme):
    m=Maillage()
    cx,cy,cz=construire_tronc(m,forme)
    # Les vieilles palmes tombent sous le cœur ; les adultes s'étalent, les
    # jeunes se dressent. L'angle de chaque couronne décale les rangées.
    niveaux=((6, .27, 2.12, .64,-2.31,12,(99,117,55)),
             (7, .82, 2.10,1.00,-.64,14,(72,119,55)),
             (4,1.35, 1.58,1.10, .60,12,(95,139,62)))
    for rang,(n,depart,l,a,d,nb,base) in enumerate(niveaux):
        for j in range(n):
            phase=1.73+j*2.37+rang*1.52
            angle=depart+TAU*j/n+.12*sin(phase)
            ton=(126,125,65) if rang==0 and j in (1,4) else base
            palme(m,(cx,cy,cz+rang*.12),angle,l*(1+.065*sin(phase+.5)),a,
                  d*(1+.08*cos(phase)),nb,couleur(ton,1+.08*cos(phase)),phase)
    # Deux jeunes lances étroites, la plus haute rejoint exactement le sommet du DFF.
    sommet_z=forme.bornes[2][1]
    for i,(angle,envergure,hauteur) in enumerate(((.86,.45,sommet_z),(3.07,.62,sommet_z-.27))):
        r=(cos(angle),sin(angle)); s=(-r[1],r[0]); longueur=hauteur-cz
        pied=sommet((cx,cy,cz),(69,108,42))
        nervure=sommet((cx+.20*r[0],cy+.20*r[1],cz+.57*longueur),(151,164,72))
        pointe=sommet((cx+envergure*r[0],cy+envergure*r[1],hauteur),(154,169,77))
        for cote in (-1,1):
            bord=sommet((cx+.17*r[0]+cote*.10*s[0],cy+.17*r[1]+cote*.10*s[1],
                         cz+.53*longueur-.035),(112+7*i,142,56))
            m.feuille(pied,nervure,bord)
            m.feuille(nervure,pointe,bord)
    return m


def transformer_palmier(blob):
    version,parties,groupe,geo,g,mats=rw.ouvrir_modele(blob)
    noms=rw.noms_materiaux(mats)
    if noms != SOURCE or len(g.positions) != 39*12 or len(g.faces) != 52*8:
        raise ValueError("Le palmier doit être la géométrie PC originale de veg_palmkbb11")
    if b"veg_palmkbb11" not in rw.corps(parties,14) or len(g.uv)!=1:
        raise ValueError("Repère du palmier non reconnu")
    forme=Silhouette.mesurer(g)
    m=construire_palmes(forme)
    for xyz in m.positions:
        if any(x<a-.025 or x>b+.025 for x,(a,b) in zip(xyz,forme.bornes)):
            raise ValueError("Hors des limites de l'arbre source")
        if dist(xyz,g.sphere[:3]) > g.sphere[3]:
            raise ValueError("Hors de la sphère de visibilité")
    # Conserver l'écorce locale ; les feuilles sont des surfaces opaques en 3D
    # éclairées par les lumières natives, sans atlas transparent ni matériau émissif.
    indices_mats=[i for i,(k,_,_) in enumerate(mats) if k==rw.MATERIAL]
    k,vm,_=mats[indices_mats[1]]
    mat=pack("<I4BII3f",0,255,255,255,255,0,0,.72,.035,1.)
    mats[indices_mats[1]]=k,vm,wrap(rw.STRUCT,vm,mat)+wrap(rw.EXTENSION,vm,b"")
    g.flags=(g.flags|0x10)&~1
    g.sphere=(*g.sphere[:5],1)
    g.positions=b"".join(rw.VEC.pack(*p) for p in m.positions)
    g.normales=b"".join(rw.VEC.pack(*n) for n in m.normales)
    g.uv=[b"".join(pack("<2f",*uv) for uv in m.uv)]
    g.couleurs=bytes(m.couleurs)
    g.faces=b"".join(rw.TRI.pack(b,a,mat,c) for mat in (0,1) for a,b,c in m.faces[mat])
    total=len(g.faces)//rw.TRI.size
    if total>3900: raise ValueError("Budget de triangles du palmier dépassé")
    binmesh=bytearray(pack("<3I",0,2,total*3))
    for mat in (0,1):
        indices=[i for tri in m.faces[mat] for i in tri]
        binmesh.extend(pack("<II",len(indices),mat))
        binmesh.extend(pack(f"<{len(indices)}I",*indices))
    exts=list(chunks(rw.corps(geo,rw.EXTENSION)))
    rw.remplacer(exts,rw.BIN_MESH,bytes(binmesh))
    rw.remplacer(geo,rw.EXTENSION,rw.assembler(exts))
    rw.remplacer(geo,rw.STRUCT,g.ecrire())
    rw.remplacer(geo,rw.MATLIST,rw.assembler(mats))
    rw.remplacer(groupe,rw.GEOMETRY,rw.assembler(geo))
    rw.remplacer(parties,rw.GEOMETRY_LIST,rw.assembler(groupe))
    return wrap(rw.CLUMP,version,rw.assembler(parties))


EFFETS_PALMIER={NOM:transformer_palmier}
