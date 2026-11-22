"""Pièces de carrosserie originales pour les véhicules PC de Vice City.

Les cotes sont en mètres dans le repère du véhicule, +Y vers le capot.
Les centres lumineux restent les repères du DFF. Un rayon sur la carrosserie
intacte détermine la profondeur et le composant mobile de chaque pièce.
"""
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache, partial
from math import cos, dist, pi, sin, sqrt
from struct import Struct, pack, unpack_from

import maillage_rw as rw
from textures import chunks, wrap


@dataclass(frozen=True)
class Optique:
    x: float
    dz: float
    largeur: float
    hauteur: float
    forme: str = "rect"


@dataclass(frozen=True)
class Style:
    grille: tuple  # demi-largeur, décalage vertical, demi-hauteur, dessin
    avant: Optique
    arriere: Optique
    entourage: str = "satin"


_SENTINEL = Style((.265, .026, .096, "vertical"), Optique(.585,.025,.217,.098,"double"), Optique(.567,.006,.375,.098), "noir")
_SABRE = Style((.505,-.005,.097,"sport"), Optique(.768,.006,.202,.098,"ronds2"), Optique(.787,-.015,.070,.137), "satin")
_FLOTTE = Style((.352,.016,.106,"quadrille"), Optique(.607,.013,.222,.091,"double"), Optique(.611,.005,.337,.104), "noir")
_STYLES = {
    "admiral": Style((.288,-.062,.135,"vertical"), Optique(.634,-.064,.208,.101), Optique(.652,-.047,.239,.081)),
    "sentinel": _SENTINEL, "sentxs": _SENTINEL,
    "sabre": _SABRE, "sabretur": _SABRE,
    "greenwoo": Style((.380,.012,.152,"vertical"), Optique(.675,-.022,.201,.104,"double"), Optique(.660,-.025,.322,.093)),
    "oceanic": Style((.279,.003,.106,"classique"), Optique(.480,.000,.235,.094,"ronds2"), Optique(.947,-.015,.073,.169,"ovale")),
    "regina": Style((.459,-.026,.125,"vertical"), Optique(.711,-.020,.180,.108,"double"), Optique(.966,-.001,.065,.147),"noir"),
    "landstal": Style((.465,.021,.144,"quadrille"), Optique(.685,.033,.157,.102), Optique(.912,.040,.077,.145)),
    "idaho": Style((.457,.035,.114,"quadrille"), Optique(.815,.031,.103,.104), Optique(.565,.025,.216,.057),"noir"),
    "taxi": _FLOTTE, "police": _FLOTTE,
    "washing": Style((.313,.035,.153,"quadrille"), Optique(.688,.023,.165,.081), Optique(.877,.011,.071,.090)),
    "virgo": Style((.276,.037,.165,"vertical"), Optique(.554,.031,.185,.079,"double"), Optique(.856,.060,.081,.119)),
    "peren": Style((.528,-.110,.141,"classique"), Optique(.810,.040,.112,.112,"rond"), Optique(.831,.014,.055,.178,"ovale")),
    "stallion": Style((.707,.010,.110,"coupe"), Optique(.844,.009,.091,.096,"rond"), Optique(.799,-.025,.110,.128),"noir"),
    "esperant": Style((.372,.050,.152,"vertical"), Optique(.651,.005,.150,.080), Optique(.914,.000,.060,.141)),
    "bobcat": Style((.568,.021,.096,"quadrille"), Optique(.761,.010,.161,.090), Optique(.938,.011,.064,.129)),
    "blistac": Style((.484,.013,.065,"sport"), Optique(.715,.019,.149,.070), Optique(.623,.002,.340,.065),"noir"),
    "cheetah": Style((.474,.009,.070,"sport"), Optique(.672,.004,.165,.078), Optique(.604,.015,.243,.070,"ronds3"),"noir"),
}

# Le gain suit le matériau dynamique de voiture. Les valeurs évitent les deux
# couleurs marqueurs utilisées par GTA pour repeindre la carrosserie.
_MATIERES = {
    "fond": ((35,40,42), .55,.00,.72),
    "noir": ((57,63,64), .56,.06,.77),
    "satin": ((166,175,175), .62,.28,.84),
    "alu": ((117,126,124), .60,.17,.82),
    "rubis": ((100,31,29), .53,.07,.77),
}
_VEC = Struct("<3f")
_FACE = Struct("<4H")
_SPHERE = Struct("<4f2I")
_CADRE = Struct("<12f2i")
_AXES = ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def _dff(nom):
    base = str(nom).replace(chr(92),"/").rsplit("/",1)[-1].lower()
    return base if "." in base else base + ".dff"


def cible_voiture(nom):
    return _dff(nom) in EFFETS_VOITURES


def _produit(a,b):
    return sum(x*y for x,y in zip(a,b))


def _rotation(axes, point):
    return tuple(sum(axes[j][i]*point[j] for j in range(3)) for i in range(3))


def _monde(rep, point):
    return tuple(x+y for x,y in zip(_rotation(rep[0],point),rep[1]))


def _local(rep, point):
    delta = tuple(x-y for x,y in zip(point,rep[1]))
    return tuple(_produit(axis,delta) for axis in rep[0])


def _cadres(sections):
    table = list(chunks(rw.corps(sections,14)))
    raw = rw.corps(table,1)
    noms = [next((d.split(bytes(1))[0].decode("ascii") for k,_,d in chunks(ext)
                  if k==0x253F2FE), "") for kind,_,ext in table if kind==3]
    if len(noms)!=unpack_from("<I",raw)[0] or len(raw)!=4+len(noms)*_CADRE.size:
        raise ValueError("Table des repères de véhicule invalide")
    reperes=[]
    for i, ligne in enumerate(_CADRE.iter_unpack(raw[4:])):
        parent=ligne[12]
        if not -1<=parent<i:
            raise ValueError("Parent mobile invalide")
        rep=(_AXES,(0.,0.,0.)) if parent<0 else reperes[parent]
        axes=tuple(_rotation(rep[0],ligne[j:j+3]) for j in (0,3,6))
        if any(abs(_produit(a,b)-int(i==j))>.001 for i,a in enumerate(axes) for j,b in enumerate(axes)):
            raise ValueError("Repère mobile avec échelle non prise en charge")
        reperes.append((axes,_monde(rep,ligne[9:12])))
    return noms,reperes


@dataclass
class Geometrie:
    flags: int
    ancienne_surface: bytes
    prelight: bytes
    uv: tuple
    faces: bytes
    sphere: tuple
    positions: bytes
    normales: bytes

    @classmethod
    def lire(cls,data,version):
        flags,nf,nv,morph = unpack_from("<4I",data)
        if version not in (0x0C02FFFF,0x1003FFFF) or morph!=1 or flags&0x01000000 or not 0<nv<=65535:
            raise ValueError("Géométrie de véhicule incompatible")
        couches=(flags>>16)&255 or (2 if flags&128 else int(bool(flags&4)))
        offset=16
        def lire_n(taille):
            nonlocal offset
            section=data[offset:offset+taille]
            if len(section)!=taille:
                raise ValueError("Table de véhicule tronquée")
            offset+=taille
            return section
        ancienne=lire_n(12 if version==0x0C02FFFF else 0)
        couleurs=lire_n(4*nv if flags&8 else 0)
        uv=tuple(lire_n(8*nv) for _ in range(couches))
        faces=lire_n(nf*_FACE.size)
        sphere=_SPHERE.unpack(lire_n(_SPHERE.size))
        if sphere[4:]!=(1,1):
            raise ValueError("Normales dynamiques de voiture manquantes")
        positions=lire_n(nv*_VEC.size)
        normales=lire_n(nv*_VEC.size)
        if offset!=len(data): raise ValueError("Fin de table inattendue")
        return cls(flags,ancienne,couleurs,uv,faces,sphere,positions,normales)

    def ecrire(self):
        return b"".join((pack("<4I",self.flags,len(self.faces)//8,len(self.positions)//12,1),
            self.ancienne_surface,self.prelight,*self.uv,self.faces,_SPHERE.pack(*self.sphere),
            self.positions,self.normales))


@dataclass
class Panneau:
    geo_id: int
    repere: tuple
    triangles: tuple

    def intersections(self,x,z):
        for xmin,xmax,zmin,zmax,a,b,c,det in self.triangles:
            if not xmin-.0001<=x<=xmax+.0001 or not zmin-.0001<=z<=zmax+.0001:
                continue
            u=((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/det
            v=((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/det
            if min(u,v,1-u-v)>=-.0003:
                yield u*a[1]+v*b[1]+(1-u-v)*c[1]


def _panneau(numero, repere, geo, rep_avant, rep_arriere):
    pos=[_monde(repere,p) for p in _VEC.iter_unpack(geo.positions)]
    tris=[]
    for ib,ia,_,ic in _FACE.iter_unpack(geo.faces):
        a,b,c=(pos[i] for i in (ia,ib,ic))
        if max(a[1],b[1],c[1])<rep_avant-.68 and min(a[1],b[1],c[1])>rep_arriere+.68:
            continue
        det=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
        if abs(det)>.000005:
            tris.append((min(a[0],b[0],c[0]),max(a[0],b[0],c[0]),min(a[2],b[2],c[2]),
                         max(a[2],b[2],c[2]),a,b,c,det))
    return Panneau(numero,repere,tuple(tris))


class Parement:
    """Une pièce est solidaire d'un seul composant intact de la voiture."""
    def __init__(self,panneaux,signe,ancre,x,z,largeur,hauteur,faces):
        self.signe=signe
        self.y_ref=ancre
        self.x=x
        self.z=z
        votes=defaultdict(list)
        for dx,dz in ((0,0),(-.65,0),(.65,0),(0,-.45),(0,.45)):
            hits=[(signe*y,-p.geo_id,p) for p in panneaux for y in
                  p.intersections(x+dx*largeur,z+dz*hauteur) if abs(y-ancre)<.55]
            if hits:
                y,_,winner=max(hits,key=lambda hit:hit[:2])
                votes[winner.geo_id].append((y*signe,winner))
        if not votes:
            raise ValueError(f"Aucun appui de carrosserie à {x:.2f}, {ancre:.2f}, {z:.2f}")
        echantillons=max(votes.values(),key=len)
        self.y0=sorted(v for v,_ in echantillons)[len(echantillons)//2]
        self.panneau=echantillons[0][1]
        self.faces=faces[self.panneau.geo_id]
        self._profondeur=lru_cache(maxsize=None)(self._rayon)

    def _rayon(self,x,z):
        ys=[y for y in self.panneau.intersections(x,z) if abs(y-self.y_ref)<.55 and abs(y-self.y0)<.24]
        return max(ys,key=lambda y:self.signe*y) if ys else self.y0

    def point(self,x,z,epaisseur):
        return (x,self._profondeur(x,z)+self.signe*epaisseur,z)

    def quad(self,matiere,a,b,c,d):
        pts=[_local(self.panneau.repere,self.point(*q)) for q in (a,b,c,d)]
        if self.signe>0: pts.reverse()
        self.faces[matiere].extend(((pts[0],pts[1],pts[2]),(pts[0],pts[2],pts[3])))


def _contour(x,z,rx,rz,rond=False):
    if rond:
        return [(x+rx*cos(i*pi/8),z+rz*sin(i*pi/8)) for i in range(16)]
    c=min(rx*.30,rz*.31)
    return [(x-rx+c,z-rz),(x+rx-c,z-rz),(x+rx,z-rz+c),(x+rx,z+rz-c),
            (x+rx-c,z+rz),(x-rx+c,z+rz),(x-rx,z+rz-c),(x-rx,z-rz+c)]


def _cadre(p,x,z,rx,rz,forme,finition,arriere=False):
    rond=forme in ("rond","ovale")
    # Le joint noir porte une lèvre bombée. La lentille d'origine demeure
    # ouverte au centre pour conserver les optiques et le matériau du jeu.
    taille=min(rx,rz)
    niveaux=((0,.006),(.08,.022),(.19,.034),(.26,.013))
    anneaux=[[(px,pz,d) for px,pz in _contour(x,z,rx-taille*t,rz-taille*t,rond)] for t,d in niveaux]
    for couleur,externe,interne in zip(("noir",finition,"rubis" if arriere else "alu"),anneaux,anneaux[1:]):
        for i in range(len(externe)):
            j=(i+1)%len(externe)
            p.quad(couleur,externe[i],externe[j],interne[j],interne[i])


def _lame(p,x,z,longueur,demi,vertical=False,matiere="alu",base=.023):
    # Profil à trois facettes pour que le reflet se déplace avec la voiture.
    profil=((-demi,base),(-demi*.42,base+.009),(demi*.34,base+.010),(demi,base))
    n=max(1,int(longueur/.115)) if not vertical else 1
    def pt(l,t):
        return (x+t[0],z+l,t[1]) if vertical else (x+l,z+t[0],t[1])
    for i in range(n):
        a=-longueur+2*longueur*i/n
        b=-longueur+2*longueur*(i+1)/n
        for u,v in zip(profil,profil[1:]):
            quad=(pt(a,u),pt(b,u),pt(b,v),pt(a,v))
            p.quad(matiere,*(reversed(quad) if vertical else quad))


def _grille(p,rx,rz,motif,finition,centre=None):
    x,z=p.x if centre is None else centre,p.z
    if motif=="coupe":
        # Le méplat peint entre les deux demi-calandres appartient au Stallion.
        demi=(rx-.085)/2
        for cote in (-1,1):
            _grille(p,demi,rz,"vertical",finition,cote*(demi+.085))
        return
    # L'alvéole sombre reste sous les lames. Les sections épousent le nez
    # central, souvent constitué de deux pans se rejoignant au milieu.
    for i in range(8):
        a=x-rx+2*rx*i/8
        b=x-rx+2*rx*(i+1)/8
        p.quad("fond",(a,z-rz,.006),(b,z-rz,.006),(b,z+rz,.006),(a,z+rz,.006))
    _cadre(p,x,z,rx+.014,rz+.011,"rect",finition)
    if motif in ("vertical","quadrille"):
        nombre=(max(7,round(rx*26)) if motif!="quadrille" else 5)
        for i in range(nombre):
            xx=x+rx*(i-(nombre-1)/2)*1.79/nombre
            _lame(p,xx,z,rz*.88,.010 if motif=="vertical" else .008,True,
                  "satin" if motif=="vertical" else "alu",.017 if motif=="quadrille" else .025)
    if motif in ("vertical","quadrille","classique","sport"):
        nombre={"vertical":2,"quadrille":3,"classique":3,"sport":4}[motif]
        for i in range(nombre):
            zz=z+rz*(i-(nombre-1)/2)*1.55/nombre
            _lame(p,x,zz,rx*.967,.008 if motif!="classique" else .013,False,
                  "noir" if motif=="vertical" else "alu",.013 if motif=="vertical" else .028)
    if motif=="sport":
        _lame(p,x,z,rz*.91,.018,True,"satin",.035)


def _optiques(p,opt,finition,arriere):
    x,z=p.x,p.z
    if opt.forme in ("ronds2","ronds3"):
        n=2 if opt.forme=="ronds2" else 3
        pas=2*opt.largeur/n
        for i in range(n):
            _cadre(p,x+(i-(n-1)/2)*pas,z,min(pas*.45,opt.hauteur*1.13),opt.hauteur,
                   "rond",finition,arriere)
    else:
        _cadre(p,x,z,opt.largeur,opt.hauteur,opt.forme,finition,arriere)
        if opt.forme=="double":
            _lame(p,x,z,opt.hauteur*.80,.009,True,"noir",.019)
        elif arriere and opt.largeur>opt.hauteur*1.6:
            _lame(p,x,z,opt.largeur*.88,.006,False,"rubis",.014)


def _structure_matiere(nom):
    rgb,amb,spec,diff=_MATIERES[nom]
    return pack("<I4BII3f",0,*rgb,255,0,0,amb,spec,diff)


def _ajouter(geo,composants,plans):
    mats=list(chunks(rw.corps(composants,rw.MATLIST)))
    extensions=list(chunks(rw.corps(composants,rw.EXTENSION)))
    binmesh=rw.corps(extensions,rw.BIN_MESH)
    refs=rw.corps(mats,rw.STRUCT)
    nombre=unpack_from("<I",refs)[0]
    version=next(v for k,v,_ in mats if k==rw.STRUCT)
    nouvelles=[]
    positions=bytearray()
    normales=bytearray()
    faces=bytearray()
    total=len(geo.positions)//12
    rayon=geo.sphere[3]
    for nom,triangles in sorted(plans.items()):
        mat=nombre+len(nouvelles)
        indices=[]
        cache={}
        for a,b,c in triangles:
            u=tuple(q-p for p,q in zip(a,b));v=tuple(q-p for p,q in zip(a,c))
            n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            norme=sqrt(_produit(n,n))
            if norme<1e-8: continue
            normal=_VEC.pack(*(j/norme for j in n))
            ids=[]
            for point in (a,b,c):
                xyz=_VEC.pack(*point)
                cle=(xyz,normal)
                if cle not in cache:
                    idx=total+len(positions)//12
                    if idx>=65535: raise ValueError("Nombre de sommets de véhicule dépassé")
                    cache[cle]=idx
                    positions.extend(xyz)
                    normales.extend(normal)
                    rayon=max(rayon,dist(point,geo.sphere[:3])+.001)
                ids.append(cache[cle])
            aa,bb,cc=ids
            indices.append((aa,bb,cc));faces.extend(_FACE.pack(bb,aa,mat,cc))
        if indices:
            binmesh=rw.ajouter_split(binmesh,indices,mat)
            nouvelles.append((rw.MATERIAL,version,wrap(rw.STRUCT,version,_structure_matiere(nom))+
                              wrap(rw.EXTENSION,version,b"")))
    if not nouvelles: raise ValueError("Le véhicule n'a reçu aucune face utilisable")
    ajoutes=len(positions)//12
    geo.flags|=0x40
    geo.faces+=faces;geo.positions+=positions;geo.normales+=normales
    geo.uv=tuple(uv+bytes(8*ajoutes) for uv in geo.uv)
    if geo.prelight: geo.prelight+=bytes((255,255,255,255))*ajoutes
    geo.sphere=(*geo.sphere[:3],rayon,*geo.sphere[4:])
    rw.remplacer(mats,1,pack("<I",nombre+len(nouvelles))+refs[4:]+pack("<i",-1)*len(nouvelles))
    mats.extend(nouvelles)
    rw.remplacer(extensions,rw.BIN_MESH,binmesh)
    rw.remplacer(composants,1,geo.ecrire())
    rw.remplacer(composants,rw.MATLIST,rw.assembler(mats))
    rw.remplacer(composants,rw.EXTENSION,rw.assembler(extensions))


def _appliquer(style,blob):
    version,sections=rw.clump(blob)
    noms,reperes=_cadres(sections)
    avant,arriere=(reperes[noms.index(nom)][1] for nom in ("headlights","taillights"))
    liste=list(chunks(rw.corps(sections,rw.GEOMETRY_LIST)))
    liens=[i for i,(k,_,_) in enumerate(liste) if k==rw.GEOMETRY]
    panneaux=[];geo_edit={}
    signature=_structure_matiere("fond")
    for kind,_,data in sections:
        if kind!=20: continue
        fr,gi,_,_=unpack_from("<4I",rw.corps(list(chunks(data)),1))
        if noms[fr] not in ("chassis_hi","bonnet_hi_ok","boot_hi_ok","bump_front_hi_ok","bump_rear_hi_ok","wing_lf_hi_ok","wing_rf_hi_ok"):
            continue
        i=liens[gi];_,ver,payload=liste[i]
        ge=list(chunks(payload))
        mats=list(chunks(rw.corps(ge,rw.MATLIST)))
        originaux=[rw.corps(list(chunks(d)),1) for k,_,d in mats if k==rw.MATERIAL]
        if signature in originaux: return blob
        geometrie=Geometrie.lire(rw.corps(ge,1),ver)
        if not geometrie.flags&0x40 and any(d[4:8]!=bytes((255,255,255,255)) for d in originaux):
            continue
        geo_edit[gi]=(geometrie,ge)
        panneaux.append(_panneau(gi,reperes[fr],geometrie,avant[1],arriere[1]))
    formes=defaultdict(lambda:defaultdict(list))
    rx,dz,rz,motif=style.grille
    p=Parement(panneaux,1,avant[1],0,avant[2]+dz,rx,rz,formes)
    _grille(p,rx,rz,motif,style.entourage)
    for signe,ancre,opt in ((1,avant,style.avant),(-1,arriere,style.arriere)):
        for main in (-1,1):
            p=Parement(panneaux,signe,ancre[1],main*opt.x,ancre[2]+opt.dz,opt.largeur,opt.hauteur,formes)
            _optiques(p,opt,style.entourage,signe<0)
    for gi,plans in formes.items():
        ge,parts=geo_edit[gi]
        _ajouter(ge,parts,plans)
        i=liens[gi];liste[i]=(*liste[i][:2],rw.assembler(parts))
    rw.remplacer(sections,rw.GEOMETRY_LIST,rw.assembler(liste))
    return wrap(rw.CLUMP,version,rw.assembler(sections))


EFFETS_VOITURES={nom+".dff":partial(_appliquer,style) for nom,style in _STYLES.items()}


def transformer_voiture(nom,blob):
    """Transforme l'entrée d'IMG désignée, ou restitue les octets hors sélection."""
    effet=EFFETS_VOITURES.get(_dff(nom))
    return blob if effet is None else effet(blob)
