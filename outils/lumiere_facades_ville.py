"""Lumière diffuse et occlusion du modèle natif pour les façades sans baie exploitable."""
import re
from math import sqrt
from ombres_majestic import Obstacles, croix, produit, rayon, unite, vecteur

PROTEGES=re.compile(r"(?:poster|billboard|graff|neon|sign|letter|door|glass|gls|lamp|light|fence|rail|glass|black|mural|tree|leaf|shad|wire|advert|reflect|_int|blinds|grill|curtain|water|grate)")


def mesurer(surface, couleurs, nuit=False):
    pos=surface["positions"];faces=surface["triangles"];mats=surface["materiaux"]
    if not pos or not faces:
        return []
    minimum=min(p[2] for p in pos);maximum=max(p[2] for p in pos)
    if maximum-minimum<2.45:
        return []
    opaque=[];candidats=[]
    for i,(a,b,c,m) in enumerate(faces):
        if not mats[m] or PROTEGES.search(mats[m]) or min(couleurs[j*4+3] for j in (a,b,c))<205:
            continue
        p,q,r=pos[a],pos[b],pos[c]
        n=croix(vecteur(q,p),vecteur(r,p))
        aire=sqrt(produit(n,n))
        if aire<.09:
            continue
        opaque.append((p,q,r));n=tuple(v/aire for v in n)
        if abs(n[2])<.65 and aire>=.62 and max(p[2],q[2],r[2])-min(p[2],q[2],r[2])>=.75:
            candidats.append((i,(a,b,c),n))
    if not candidats:
        return []
    arbre=Obstacles(opaque)
    facteurs={};mesures=[]
    for i,inds,n in candidats:
        facteurs_face=[]
        # Évaluer l'hémisphère réellement visible à la verticale et de chaque côté.
        rayons=[rayon((n[0]*.40-n[1]*k,n[1]*.40+n[0]*k,.81)) for k in (-.65,0,.65)]
        for j in inds:
            v=pos[j];key=(j,*(round(q,2) for q in n))
            if key not in facteurs:
                origine=tuple(v[k]+n[k]*.052 for k in range(3))
                bloques=sum(arbre.intersecte(origine,d,inv,3.75) for d,inv in rayons)
                # Un léger modelé diffus conserve le chromatisme d'origine sur les
                # murs sans décrochement ; la vraie occlusion accentue les angles.
                incidence=max(0.,n[0]*.61-n[1]*.54+n[2]*.49)
                niveau=max(0.,min(1.,(v[2]-minimum)/min(4.2,maximum-minimum)))
                facteur=.935+.085*incidence+.024*niveau-(.145 if nuit else .235)*bloques/3
                facteurs[key]=round(255*facteur)
            facteurs_face.append(facteurs[key])
        if any(abs(k-255)>=3 for k in facteurs_face):
            mesures.append([i,*facteurs_face])
    return mesures
