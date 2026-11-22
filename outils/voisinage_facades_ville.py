"""Contrôle d'intersection des chambres décoratives avec les autres bâtiments placés."""
from collections import defaultdict
from itertools import product
from math import floor

import maillage_rw as rw
import textures
from ombres_majestic import croix, produit
from releve_facades_ville import encadre, interieur_triangle, recouvrent, monde


def unite_affine(f):
    o=f((0.,0.,0.))
    axes=[tuple(v-o[k] for k,v in enumerate(f(p))) for p in ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))]
    return o,axes


def appliquer(trans,p):
    o,(a,b,c)=trans;x,y,z=p
    return (o[0]+a[0]*x+b[0]*y+c[0]*z,o[1]+a[1]*x+b[1]*y+c[1]*z,o[2]+a[2]*x+b[2]*y+c[2]*z)


def inverse(trans):
    o,(a,b,c)=trans
    lignes=croix(b,c),croix(c,a),croix(a,b);det=produit(a,lignes[0])
    if abs(det)<1e-8:raise ValueError("Échelle IPL nulle")
    return o,tuple(tuple(t/det for t in ligne) for ligne in lignes)


def locale(inv,p):
    o,axes=inv;x,y,z=p[0]-o[0],p[1]-o[1],p[2]-o[2]
    return tuple(a*x+b*y+c*z for a,b,c in axes)


def cellules(zone):
    lo,hi=zone
    return product(range(floor(lo[0]/24),floor(hi[0]/24)+1),range(floor(lo[1]/24),floor(hi[1]/24)+1))


def heures(ide):
    h=ide.get("heures")
    if not h or h[0]==h[1]:return set(range(24))
    return {(h[0]+i)%24 for i in range((h[1]-h[0])%24)}


def verifier(plans,placements,definitions,index,lire,palette):
    from facades_ville import cadres_atomiques,cadre,monde_ipl
    from releve_facades_ville import est_lointain,est_accessoire
    cellules_cibles=defaultdict(set);cibles=[]
    for nom,plan in plans.items():
        ident=plan["nom"]
        for geo in plan["geometries"]:
            for nb,b in enumerate(geo["baies"]):
                if b["mode"]!="piece":continue
                for place,lieu in enumerate(placements[ident]):
                    if lieu["zone"]!=0:continue
                    t=unite_affine(lambda p:monde_ipl(monde(p,b),lieu))
                    w,h,d=b["largeur"],b["hauteur"],b["profondeur"]
                    limites=((.07,-.022,.07),(w-.07,d,h-.07))
                    monde_bbox=encadre([appliquer(t,p) for p in product(*zip(*limites))])
                    n=len(cibles);cle=(nom,geo["index"],nb)
                    cibles.append((cle,place,inverse(t),limites,monde_bbox,heures(definitions[ident])))
                    for cell in cellules(monde_bbox):cellules_cibles[cell].add(n)
    exclus={}
    for nom,lieux in sorted(placements.items()):
        if nom not in definitions or nom+".dff" not in index or est_lointain(nom):
            continue
        # Les arbres, véhicules et mobiliers placés à l'extérieur ne représentent pas
        # une cloison. Le verre déjà transparent ne doit jamais devenir un mur.
        if est_accessoire(nom):continue
        lieux=[(i,p) for i,p in enumerate(lieux) if p["zone"]==0]
        if not lieux:continue
        actives=heures(definitions[nom])
        _,parties=rw.clump(lire(nom+".dff"));groupe=list(textures.chunks(rw.corps(parties,rw.GEOMETRY_LIST)))
        frames=cadres_atomiques(parties);dico=palette(definitions[nom]["txd"])
        for ig,(_,_,data) in enumerate(x for x in groupe if x[0]==rw.GEOMETRY):
            if ig not in frames:continue
            geo=list(textures.chunks(data));g=rw.Geometrie.lire(rw.corps(geo,1))
            pos=tuple(rw.VEC.iter_unpack(g.positions));bbox=encadre(pos)
            noms=rw.noms_materiaux(list(textures.chunks(rw.corps(geo,rw.MATLIST))))
            opaque=[not (m and dico.get(m,(True,None))[0] is False) and not any(tag in m for tag in ("shadow","seethru","twink","neon","fence")) for m in noms]
            faces=[(a,b,c) for b,a,m,c in rw.TRI.iter_unpack(g.faces) if opaque[m] and min(g.couleurs[4*k+3] for k in (a,b,c))>185]
            if not faces:continue
            for place,lieu in lieux:
                for mats in frames[ig]:
                    t=unite_affine(lambda p:monde_ipl(cadre(p,mats),lieu))
                    box=encadre([appliquer(t,p) for p in product(*zip(*bbox))])
                    ids=set()
                    for cell in cellules(box):ids.update(cellules_cibles.get(cell,()))
                    cible=[]
                    for i in ids:
                        cle,p,inv,limites,boite,heurs=cibles[i]
                        if cle in exclus or (cle[0]==nom+".dff" and p==place and cle[1]==ig):continue
                        if actives.isdisjoint(heurs) or not recouvrent(box,boite):continue
                        cible.append((cle,inv,limites,boite))
                    if not cible:continue
                    wp=[appliquer(t,p) for p in pos]
                    for a,b,c in faces:
                        tri=(wp[a],wp[b],wp[c]);zmin,zmax=min(v[2] for v in tri),max(v[2] for v in tri)
                        for cle,inv,limites,boite in cible:
                            if cle in exclus or zmin>boite[1][2] or zmax<boite[0][2]:continue
                            if not all(min(p[k] for p in tri)<=boite[1][k] and max(p[k] for p in tri)>=boite[0][k] for k in (0,1)):continue
                            if interieur_triangle([locale(inv,p) for p in tri],limites):
                                exclus[cle]=nom
    for (nom,ig,idx),voisin in exclus.items():
        geo=next(g for g in plans[nom]["geometries"] if g["index"]==ig)
        b=geo["baies"][idx];b.update(mode="retrait",profondeur=.018,deplacement=0,garde_voisin=voisin)
    return len(exclus)
