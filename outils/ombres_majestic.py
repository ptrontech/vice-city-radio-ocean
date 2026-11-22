"""Cuisson locale des ombres architecturales du Majestic sur ses UV et ses couleurs.

Les ombres de contact dépendent des volumes ajoutés. La variante jour comprend une
lumière latérale étendue, la variante nuit garde les teintes de la façade éclairée.
"""
from collections import defaultdict
from math import ceil, dist, sqrt
from struct import Struct, iter_unpack, pack

VEC = Struct("<3f")
UV = Struct("<2f")
TRI = Struct("<4H")
RECEPTEURS = {"hotelpeach", "hotelwindow1", "hotelwindow2", "hot_doors", "fancy_slab128", "bow_abattoir_conc2"}
SKY = ((0,0,1),(.56,.18,.81),(-.47,.42,.78),(.18,-.61,.77),(-.54,-.23,.81))
SUN = ((.68,-.30,.67),(.74,-.23,.63),(.65,-.39,.65))

def vecteur(a,b):
    return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def produit(a,b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def croix(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unite(v):
    l=sqrt(produit(v,v))
    return (v[0]/l,v[1]/l,v[2]/l) if l>1e-9 else (0.,0.,0.)
def limites(points):
    return (tuple(min(p[i] for p in points) for i in range(3)),
            tuple(max(p[i] for p in points) for i in range(3)))

class Obstacles:
    """Arbre de boîtes englobantes des nouvelles pièces opaques."""
    __slots__ = ("bas","haut","gauche","droite","feuilles")
    def __init__(self, faces):
        self.bas,self.haut=limites([p for face in faces for p in face])
        self.gauche=self.droite=None
        self.feuilles=()
        if len(faces)<=9:
            self.feuilles=tuple((a,vecteur(b,a),vecteur(c,a)) for a,b,c in faces)
        else:
            axe=max(range(3),key=lambda i:self.haut[i]-self.bas[i])
            faces.sort(key=lambda f:sum(p[axe] for p in f))
            coupe=len(faces)//2
            self.gauche = Obstacles(faces[:coupe])
            self.droite = Obstacles(faces[coupe:])

    def intersecte(self, point, direction, inverse, portee):
        proche,loin=0.,portee
        for i in range(3):
            if inverse[i] is None:
                if point[i]<self.bas[i] or point[i]>self.haut[i]:return False
                continue
            t0=(self.bas[i]-point[i])*inverse[i]
            t1=(self.haut[i]-point[i])*inverse[i]
            proche = max(proche,min(t0,t1))
            loin = min(loin,max(t0,t1))
            if loin<proche:return False
        if self.gauche is not None:
            return self.gauche.intersecte(point,direction,inverse,portee) or self.droite.intersecte(point,direction,inverse,portee)
        for a,e1,e2 in self.feuilles:
            h = croix(direction,e2)
            det = produit(e1,h)
            if abs(det)<1e-9:continue
            depuis = vecteur(point,a)
            u = produit(depuis,h)/det
            if u<0. or u>1.:continue
            q = croix(depuis,e1)
            v = produit(direction,q)/det
            if v<0. or u+v>1.:continue
            distance=produit(e2,q)/det
            if .018<distance<portee:return True
        return False

def rayon(direction):
    d=unite(direction)
    return d,tuple(1./v if abs(v)>1e-8 else None for v in d)

RAYONS_CIEL=tuple(map(rayon,SKY))
RAYONS_SOLEIL=tuple(map(rayon,SUN))

def factoriser(point,normale,arbre,nuit):
    origine=tuple(point[i]+.035*normale[i] for i in range(3))
    horizon=rayon((normale[0]+.05,normale[1]-.03,max(.28,normale[2])))
    ciel=[r for r in (*RAYONS_CIEL,horizon) if produit(normale,r[0])>.045]
    ombre=sum(arbre.intersecte(origine,d,inv,2.6) for d,inv in ciel)/max(1,len(ciel))
    soleil=0.
    if not nuit and produit(normale,RAYONS_SOLEIL[0][0])>.06:
        soleil=sum(arbre.intersecte(origine,d,inv,9.5) for d,inv in RAYONS_SOLEIL)/len(RAYONS_SOLEIL)
    return 1.-(.23 if nuit else .28)*ombre-.33*soleil

def liste_indices(faces):
    groupes=defaultdict(list)
    for a,b,c,m in faces:groupes[m].extend((a,b,c))
    payload=bytearray(pack("<3I",0,len(groupes),len(faces)*3))
    for m,indices in sorted(groupes.items()):
        payload.extend(pack("<2I",len(indices),m))
        payload.extend(pack(f"<{len(indices)}I",*indices))
    return bytes(payload)

def cuire(geo,surface,architecture,nuit=False):
    """Affiner les pans recevant une ombre et interpoler fidèlement leurs coordonnées UV."""
    obstacles=[tuple(v[:3] for v in face) for face in architecture]
    if not obstacles:return None
    arbre=Obstacles(obstacles)
    positions=surface["positions"]
    couleurs = list(iter_unpack("<4B", geo.couleurs))
    couches=[list(UV.iter_unpack(c)) for c in geo.uv]
    normales=list(VEC.iter_unpack(geo.normales)) if geo.normales else []
    posplus,teintes,normplus=bytearray(),bytearray(),bytearray()
    uvplus=[bytearray() for _ in couches]
    sommets,cache={},{}
    faces=[]
    for a,b,c,m in surface["triangles"]:
        corners = (a,b,c)
        p,q,r = [positions[i] for i in corners]
        if surface["materiaux"][m] not in RECEPTEURS:
            faces.append((a,b,c,m))
            continue
        n=unite(croix(vecteur(q,p),vecteur(r,p)))
        bas,haut=limites((p,q,r))
        if n==(0.,0.,0.) or any(haut[i]<arbre.bas[i]-10 or bas[i]>arbre.haut[i]+3 for i in range(3)):
            faces.append((a,b,c,m))
            continue
        nombre=min(14,max(1,ceil(max(dist(p,q),dist(p,r),dist(q,r))/.88)))
        points={}
        for u in range(nombre+1):
            for v in range(nombre+1-u):
                w=(1.-(u+v)/nombre,u/nombre,v/nombre)
                xyz=tuple(w[0]*p[j]+w[1]*q[j]+w[2]*r[j] for j in range(3))
                cle=tuple(round(x,4) for x in (*xyz,*n))
                if cle not in cache:cache[cle]=factoriser(xyz,n,arbre,nuit)
                points[u,v]=(w,xyz,cache[cle])
        if all(f>=.9999 for _,_,f in points.values()):
            faces.append((a,b,c,m))
            continue
        indices={}
        for main,(w,xyz,facteur) in points.items():
            base = [sum(w[j]*couleurs[corners[j]][k] for j in range(3)) for k in range(4)]
            rgba = tuple(round(c*facteur) for c in base[:3]) + (round(base[3]),)
            coord=VEC.pack(*xyz)
            uv=tuple(UV.pack(*(sum(w[j]*layer[corners[j]][k] for j in range(3)) for k in range(2))) for layer in couches)
            normal=VEC.pack(*unite(tuple(sum(w[j]*normales[corners[j]][k] for j in range(3)) for k in range(3)))) if normales else b""
            cle=coord,rgba,uv,normal
            if cle not in sommets:
                indice=len(positions)+len(sommets)
                if indice >= 65535:
                    raise ValueError("Tessellation trop détaillée pour le Majestic")
                sommets[cle] = indice
                posplus.extend(coord)
                teintes.extend(rgba)
                normplus.extend(normal)
                for data,value in zip(uvplus,uv):data.extend(value)
            indices[main]=sommets[cle]
        for u in range(nombre):
            for v in range(nombre-u):
                f0,f1,f2=indices[u,v],indices[u+1,v],indices[u,v+1]
                faces.append((f0,f1,f2,m))
                if u+v+1<nombre:faces.append((f1,indices[u+1,v+1],f2,m))
    if not posplus:return None
    geo.positions += posplus
    geo.couleurs += teintes
    geo.normales += normplus
    geo.uv=[layer+extra for layer,extra in zip(geo.uv,uvplus)]
    geo.faces=b"".join(TRI.pack(b,a,m,c) for a,b,c,m in faces)
    geo.flags &= ~1
    return liste_indices(faces)
