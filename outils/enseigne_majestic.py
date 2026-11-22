"""Lettrage Art déco original en relief pour la marquise du Majestic.

Toutes les dimensions sont en unités du modèle. Les lettres se lisent dans le
sens +Y quand on regarde l'entrée depuis Ocean Drive (côté +X).
"""
from math import hypot

LETTRES = {
    "M": (1.12, [[(.02,0),(.02,1),(.55,.43),(1.08,1),(1.08,0)]]),
    "A": (1., [[(.02,0),(.44,1),(.56,1),(.98,0)],[(.23,.41),(.77,.41)]]),
    "J": (.87, [[(.10,1),(.81,1),(.81,.22),(.69,.05),(.54,0),(.22,0),(.06,.12)]]),
    "E": (.85, [[(.80,1),(.03,1),(.03,0),(.80,0)],[(.04,.52),(.65,.52)]]),
    "S": (.96, [[(.91,.90),(.78,1),(.21,1),(.05,.85),(.05,.65),(.21,.51),(.72,.51),
                  (.91,.37),(.91,.16),(.74,0),(.21,0),(.04,.12)]]),
    "T": (1., [[(.02,1),(.98,1)],[(.50,1),(.50,0)]]),
    "I": (.43, [[(.02,1),(.40,1)],[(.21,1),(.21,0)],[(.02,0),(.40,0)]]),
    "C": (1., [[(.95,.85),(.78,1),(.24,1),(.04,.80),(.04,.20),(.24,0),(.78,0),(.95,.15)]]),
}

def nuance(couleur, facteur):
    return tuple(min(255,round(c*facteur)) for c in couleur)

def quad(faces, points, teinte):
    a,b,c,d = [(*p,*teinte) for p in points]
    faces.extend(((a,b,c),(a,c,d)))

def coffret(faces, limites, teinte):
    x0,x1,y0,y1,z0,z1 = limites
    pts = ((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
           (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1))
    for ia,ib,ic,id_,val in ((1,2,6,5,1.),(0,4,7,3,.63),(2,3,7,6,.82),
                             (0,1,5,4,.75),(4,5,6,7,1.13),(0,3,2,1,.47)):
        quad(faces,[pts[i] for i in (ia,ib,ic,id_)],nuance(teinte,val))

def trait(faces, p, q, teinte):
    """Barre coulée à profil biseauté avec deux chants et des extrémités fermées."""
    y,z = p
    dy,dz = q[0]-y,q[1]-z
    longueur = hypot(dy,dz)
    uy,uz = dy/longueur,dz/longueur
    ny,nz = -uz,uy
    def contour(x, demi, cap):
        return [(x,y-uy*cap-ny*demi,z-uz*cap-nz*demi),
                (x,q[0]+uy*cap-ny*demi,q[1]+uz*cap-nz*demi),
                (x,q[0]+uy*cap+ny*demi,q[1]+uz*cap+nz*demi),
                (x,y-uy*cap+ny*demi,z-uz*cap+nz*demi)]
    pied = contour(13.355,.052,.020)
    chant = contour(13.446,.052,.020)
    devant = contour(13.473,.036,.008)
    quad(faces,devant,teinte)
    quad(faces,pied[::-1],nuance(teinte,.47))
    for i in range(4):
        j=(i+1)%4
        quad(faces,[pied[i],pied[j],chant[j],chant[i]],nuance(teinte,.57))
        quad(faces,[chant[i],chant[j],devant[j],devant[i]],nuance(teinte,1.10 if i in (1,2) else .83))

def construire_enseigne(nuit=False):
    faces=[]
    em = (32,68,66) if not nuit else (17,39,44)
    laiton = (199,155,90) if not nuit else (232,173,99)
    texte = (230,193,121) if not nuit else (255,225,168)
    centre = -.62
    # Deux pieds ancrés dans la marquise, un dos en bronze et un panneau émaillé.
    for y in (centre-2.68,centre+2.68):
        coffret(faces,(12.96,13.22,y-.075,y+.075,-9.14,-8.31),nuance(laiton,.69))
    coffret(faces,(13.055,13.30,centre-3.78,centre+3.78,-8.77,-7.59),laiton)
    coffret(faces,(13.30,13.354,centre-3.70,centre+3.70,-8.70,-7.67),em)
    # Trois ailes étagées encadrent l'inscription sans empiéter sur les vitrines.
    for niveau,extension in enumerate((.48,.78,.48)):
        z=-8.48+.235*niveau
        for y0,y1 in ((centre-3.78-extension,centre-3.78),(centre+3.78,centre+3.78+extension)):
            coffret(faces,(13.12,13.27,y0,y1,z,z+.074),laiton)
    mot = "MAJESTIC"
    echelle_y,hauteur,pas=.66,.73,.20
    largeur=sum(LETTRES[l][0]*echelle_y for l in mot)+pas*(len(mot)-1)
    depart=centre-largeur/2
    for lettre in mot:
        avance,lignes=LETTRES[lettre]
        for chemin in lignes:
            trace=[(depart+y*echelle_y,-8.56+z*hauteur) for y,z in chemin]
            for p,q in zip(trace,trace[1:]):
                trait(faces,p,q,texte)
        depart+=avance*echelle_y+pas
    return faces
