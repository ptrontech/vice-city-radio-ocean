"""Inventorie les bâtiments extérieurs et reconstruit leurs baies sur la copie PC 1.0."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from math import atan2, hypot, pi
from pathlib import Path
import re
from struct import iter_unpack, unpack_from
from zlib import crc32

import baies_atlas_ville as atlas
import lumiere_facades_ville as lumiere
import maillage_rw as rw
import releve_facades_ville as releve
import textures
from collision_hall_majestic import blocs as blocs_collision
from ombres_majestic import liste_indices
from volume_rw import Sommet, Sommets, decouper, retirer_prisme, aire_double


def empreinte(blob):
    size=12+unpack_from("<I",blob,4)[0]
    if size>len(blob) or any(blob[size:]):
        raise ValueError("DFF incomplet ou octets étrangers après la géométrie")
    return sha256(memoryview(blob)[:size]).hexdigest()


def chemin(origine, ref):
    courant=Path(origine)
    for partie in ref.replace("\\","/").split("/"):
        f=courant/partie
        if f.exists():
            courant=f
        else:
            choix=[p for p in courant.iterdir() if p.name.casefold()==partie.casefold()]
            if len(choix)!=1:
                raise FileNotFoundError(f)
            courant=choix[0]
    return courant


def sections(fichier):
    section=""
    for ligne in fichier.read_text(encoding="latin1").splitlines():
        texte=ligne.split("#",1)[0].strip().lower()
        if not texte:
            continue
        if "," not in texte:
            section=texte
        else:
            yield section,[x.strip() for x in texte.split(",")]


def carte(origine):
    definitions={};placements=defaultdict(list)
    dat=chemin(origine,"data/gta_vc.dat")
    for ligne in dat.read_text(encoding="latin1").splitlines():
        contenu=ligne.split("#",1)[0].strip().split(maxsplit=1)
        if len(contenu)!=2:
            continue
        genre,ref=contenu;genre=genre.upper()
        if genre not in ("IDE","IPL") or not ref.lower().endswith((".ide",".ipl")):
            continue
        path=chemin(origine,ref)
        for section,a in sections(path):
            if genre=="IDE" and section in ("objs","tobj") and len(a)>=5:
                definitions[a[1]]={"id":int(a[0]),"txd":a[2],"heures":list(map(int,a[-2:])) if section=="tobj" else []}
            elif genre=="IPL" and section=="inst" and len(a)>=13:
                placements[a[1]].append({"id":int(a[0]),"zone":int(a[2]),"quartier":path.parent.name.lower(),
                    "xyz":tuple(map(float,a[3:6])),"echelle":tuple(map(float,a[6:9])),"quaternion":tuple(map(float,a[9:13]))})
    return definitions,placements


def monde_ipl(point, lieu):
    a,b,c=[p*s for p,s in zip(point,lieu["echelle"])]
    x,y,z,w=lieu["quaternion"];ox,oy,oz=lieu["xyz"]
    return (ox+a*(1-2*y*y-2*z*z)+b*2*(x*y+z*w)+c*2*(x*z-y*w),
            oy+a*2*(x*y-z*w)+b*(1-2*x*x-2*z*z)+c*2*(y*z+x*w),
            oz+a*2*(x*z+y*w)+b*2*(y*z-x*w)+c*(1-2*x*x-2*y*y))


def cadre(p, matrices):
    pt=tuple(p)
    for mat in matrices:
        pt=tuple(sum(pt[j]*mat[j*3+i] for j in range(3))+mat[9+i] for i in range(3))
    return pt


def cadres_atomiques(parties):
    frame_data=rw.corps(list(textures.chunks(rw.corps(parties,14))),1)
    nombres=unpack_from("<I",frame_data)[0];matrices=[]
    for i in range(nombres):
        m=unpack_from("<12fiI",frame_data,4+56*i)
        parent=m[12]
        if parent>=i:
            raise ValueError("Hiérarchie des repères incohérente")
        matrices.append([m[:12]]+([] if parent<0 else matrices[parent]))
    sorties=defaultdict(list)
    for typ,_,body in parties:
        if typ==20:
            frame,geo=unpack_from("<II",rw.corps(list(textures.chunks(body)),1))
            sorties[geo].append(matrices[frame])
    return sorties


def meme_repere(transfos):
    origine=((0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
    return len(transfos)==1 and all(max(abs(q-p) for q,p in zip(cadre(pt,transfos[0]),pt))<.002 for pt in origine)


def ordre_reparti(baies):
    groupes=defaultdict(list)
    for b in baies:
        angle=round(atan2(b["n"][1],b["n"][0])/(pi/4))%8
        cle=angle,round(b["centre"][2]/3.5),b["nom"]
        groupes[cle].append(b)
    files=[sorted(items,key=lambda b:(b["centre"][0],b["centre"][1])) for k,items in sorted(groupes.items())]
    while files:
        for f in files:
            yield f.pop(0)
        files=[f for f in files if f]


def variante(nom):
    return re.sub(r"(?:(?:_?(?:d[ya]|nt|day|night|nite))(?=\d*$))","",nom,flags=re.I)


def candidats(g,mats,identite,collision,textures_modele,nuit,nom):
    surface=g.surface(mats)
    pos,faces=surface["positions"],surface["triangles"]
    mi,ma=releve.encadre(pos);centre=tuple((u+v)/2 for u,v in zip(mi,ma))
    if ma[2]-mi[2]<1.4 or max(ma[0]-mi[0],ma[1]-mi[1])<1.75:
        return []
    matis=list(iter_unpack("<2f",g.uv[0]))
    panels=[]
    for b in releve.rectangles(surface,matis):
        m=b["nom"]
        if m in atlas.ENDUIT:
            b["genre"]="mur"
        if b["genre"]=="fenetre":
            tri=faces[b["faces"][0]][:3]
            panels.extend(atlas.diviser(b,[pos[j] for j in tri],[matis[j] for j in tri]))
        else:
            panels.append(b)
    mtable=Counter(mats[f[3]] for f in faces if releve.aire_mat(mats[f[3]])=="mur")
    teinte_mur=next((textures_modele[m][1] for m,_ in mtable.most_common() if textures_modele.get(m,(False,None))[1]), None)
    tris=[]
    for i,(a,b,c,_) in enumerate(faces):
        pts=pos[a],pos[b],pos[c]
        tris.append((i,pts,releve.encadre(pts)))
    fenetres=[];murs=[]
    for b in panels:
        w,h=b["largeur"],b["hauteur"]
        if sum((x-c)*n for x,c,n in zip(b["centre"],centre,b["n"]))<-.6:
            continue
        if b["genre"]=="fenetre":
            if .69<=w<=32 and .68<=h<=20:
                fenetres.append(b)
        elif 3.4<=w<=75 and 2.45<=h<=43 and w/h>=.67:
            murs.append(b)
    faits=[];volumes=[];nb_piece=0
    for b in ordre_reparti(fenetres):
        w,h=b["largeur"],b["hauteur"]
        vitrine=bool(releve.VITRINE.search(b["nom"]))
        bas=b["centre"][2]-mi[2]
        forme=.93<=w<=6.8 and .92<=h<=4.5 and .28<=w/h<=4.2 and .29<=b["repetitions"]<=1.35
        opaque=textures_modele.get(b["nom"],(False,None))[0] and not atlas.PROTEGES.search(b["nom"])
        nette=bool(releve.VITRENETTE.search(b["nom"]) or b["nom"] in atlas.PIECES) and opaque
        protegée=bas>2.40 or (identite and releve.barre_collision(b,collision))
        profondeurs=[]
        if forme and nette and protegée and identite and nb_piece<12:
            profondeurs=[min(1.82,max(1.22,w*.65)),1.14,.94]
            profondeurs=sorted(set(profondeurs),reverse=True)
        profondeur=releve.prof_libre(b,tris,profondeurs+[.16,.075]) if opaque else 0.
        interieur=profondeur>=.9
        if interieur:
            # Éviter que deux pièces d'angle ou deux fenêtres des ailes d'un U
            # occupent le même volume, même si le compartiment commercial est vide.
            coins=[releve.monde((x,y,z),b) for x in (.035,w-.035) for y in (.05,profondeur) for z in (.035,h-.035)]
            boite=releve.encadre(coins)
            if any(releve.recouvrent(boite,autre) for autre in volumes):
                interieur=False;profondeur=.14
            else:
                volumes.append(boite);nb_piece+=1
        mode="piece" if interieur else "retrait"
        b.update(mode=mode,profondeur=max(.018,profondeur),deplacement=0 if interieur else profondeur,
                 vitrine=vitrine,nuit=nuit)
        faits.append(b)
        if len(faits)>=48:
            break
    if not fenetres or len(murs)<2:
        murs.extend(releve.corniches_toit(surface))
    # Couronnements sur des murs explicitement nommés ; pas de nouvelles baies
    # sur les enseignes, les peintures, les portes et les façades en atlas.
    sommets_murs=[]
    for b in ordre_reparti(murs):
        sommet=b["centre"][2]+b["hauteur"]
        if sommet<mi[2]+.46*(ma[2]-mi[2]):
            continue
        if any(abs(sommet-z)<.22 and hypot(b["centre"][0]-x,b["centre"][1]-y)<min(b["largeur"],w)*.28 for x,y,z,w in sommets_murs):
            continue
        b.update(mode="corniche",profondeur=.10,deplacement=0,vitrine=False,nuit=nuit)
        faits.append(b);sommets_murs.append((*b["centre"][:2],sommet,b["largeur"]))
        if len(sommets_murs)>= (3 if fenetres else 8):
            break
    for b in faits:
        pt=[round(q*2) for q in b["centre"]]
        b["graine"]=crc32((variante(nom)+"/"+",".join(map(str,pt))).encode("ascii","replace"))
        propre=textures_modele.get(b["nom"],(False,None))[1] if b["mode"]=="corniche" else teinte_mur
        if propre:
            b["teinte"]=tuple(max(42,min(206,round(v*.65+52))) for v in propre)
        b.pop("uv_bornes",None)
        for attr in ("genre","repetitions"):
            b.pop(attr)
    return faits


def analyser(nom,blob,collision_data,lieu,ide,textures_modele):
    if nom in releve.PROTEGER or "majestic2c" in nom:
        return None,"Majestic conservé"
    if releve.MOBILIER.search(nom):
        return None,"voie, accessoire, végétation ou intérieur"
    _,parts=rw.clump(blob)
    groupe=list(textures.chunks(rw.corps(parts,rw.GEOMETRY_LIST)))
    frames=cadres_atomiques(parts)
    brut=[(list(textures.chunks(data)),v) for typ,v,data in groupe if typ==rw.GEOMETRY]
    donnees=[]
    for geo,_ in brut:
        noms=rw.noms_materiaux(list(textures.chunks(rw.corps(geo,rw.MATLIST))))
        donnees.append(noms)
    materiaux={m for noms in donnees for m in noms};genres={releve.aire_mat(m) for m in materiaux}
    toit=any(re.search(r"roof|tile_roof|rooftop",m) for m in materiaux)
    arch=bool(releve.EDIFICE.search(nom) or "fenetre" in genres or ("mur" in genres and toit))
    if not arch and not re.search(r"container|crate|bin_|box_|dockwall|debris|antenna|bleach|stair|ramp|parking|parkland|slab|pole|pylon|tank|planter|platform|grnd|ground|rubble|tarmac|scaff|barrel",nom):
        for (geo,_),noms in zip(brut,donnees):
            g=rw.Geometrie.lire(rw.corps(geo,1));surf=g.surface(noms)
            mi,ma=releve.encadre(surf["positions"])
            if min(ma[j]-mi[j] for j in (0,1))<4.5 or ma[2]-mi[2]<3.65:continue
            rives=releve.corniches_toit(surf)
            # Deux murs de directions différentes tenant réellement le même toit.
            if any(abs(v["n"][0]*b["n"][1]-v["n"][1]*b["n"][0])>.52 for k,b in enumerate(rives) for v in rives[k+1:]):
                arch=True;break
    if not arch:
        return None,"aucun indice architectural"
    coll=releve.geometrie_collision(collision_data)
    usage=releve.famille(nom,materiaux,lieu["quartier"])
    nuit=bool(ide["heures"] and ide["heures"][0]>ide["heures"][1])
    plan={"nom":nom,"source":empreinte(blob),"famille":usage,"geometries":[],"quartier":lieu["quartier"],"id":ide["id"]}
    meilleur=None
    for index,((geo,_),noms) in enumerate(zip(brut,donnees)):
        if index not in frames:
            continue
        g=rw.Geometrie.lire(rw.corps(geo,rw.STRUCT))
        if len(g.uv)!=1 or len(g.positions)//12>56000:
            continue
        baies=candidats(g,noms,meme_repere(frames[index]),coll,textures_modele,nuit,nom)
        if not baies:
            continue
        plan["geometries"].append({"index":index,"baies":baies})
        for b in baies:
            v=(b["mode"]=="piece", b["mode"]=="retrait",min(b["largeur"],6)*min(b["hauteur"],4))
            if meilleur is not None and v<=meilleur[0]:
                continue
            w,h=b["largeur"],b["hauteur"];distance=min(11.,max(4.3,.85*w))
            def point(x,y,z):
                return monde_ipl(cadre(releve.monde((x,y,z),b),frames[index][0]),lieu)
            meilleur=(v,{"oeilA":point(w*.5-1.8,-distance,h*.46),"oeilB":point(w*.5+1.8,-distance,h*.49),
                         "cible":point(w*.5,min(.55,b["profondeur"]*.55),h*.44),"mode":b["mode"],"materiau":b["nom"]})
    if not plan["geometries"]:
        for index,((geo,_),noms) in enumerate(zip(brut,donnees)):
            if index not in frames:continue
            g=rw.Geometrie.lire(rw.corps(geo,rw.STRUCT))
            if len(g.uv)!=1 or len(g.positions)//12>54500:continue
            surface=g.surface(noms);mesures=lumiere.mesurer(surface,g.couleurs,nuit)
            if mesures:
                plan["geometries"].append({"index":index,"baies":[],"eclairage":mesures})
        if not plan["geometries"]:
            # Un nom de bâtiment peut désigner seulement ses néons, ses vitrages
            # ou son parking. Ne pas compter ces annexes comme des bâtiments.
            if re.search(r"pool|termsign|bikeshop_glass|ballust|_gls|stadspaces|glass|clublight|shopdoor|neon|factoryint|factorypol|mallseats|garagedoors|_al$|fnce|marinaveg|glss|balcony|grd$|clubdoor|_windows$|recycl|rcycl|rail\d|stad_road|starblocker|fenc|water|hotelsign|signday|signight|icedoor|terminachek",nom):
                return None,"annexe séparée (verre, cour, accès, signe ou mobilier)"
            return None,"candidat bâtiment sans paroi verticale opaque exploitable"
    if meilleur:
        plan["camera"]=meilleur[1]
    return plan,None


def transformer(blob,plan):
    """Transforme l'entrée native ; un deuxième passage retourne les octets déjà montés."""
    from decor_facades_ville import construire_decor
    h=empreinte(blob)
    if h==plan.get("sortie"):
        return blob
    if h!=plan["source"]:
        raise ValueError("La façade a été modifiée par une autre version : "+plan["nom"])
    version,parties=rw.clump(blob)
    groupe=list(textures.chunks(rw.corps(parties,rw.GEOMETRY_LIST)))
    indexs=[i for i,x in enumerate(groupe) if x[0]==rw.GEOMETRY]
    for operation in plan["geometries"]:
        i=indexs[operation["index"]];tag,ver,data=groupe[i]
        geo=list(textures.chunks(data));g=rw.Geometrie.lire(rw.corps(geo,rw.STRUCT))
        mats=list(textures.chunks(rw.corps(geo,rw.MATLIST)))
        extensions=list(textures.chunks(rw.corps(geo,rw.EXTENSION)))
        cache=Sommets(g);original=[(a,b,c,m) for b,a,m,c in rw.TRI.iter_unpack(g.faces)]
        ajouts=[];prismes=defaultdict(list);direct={}
        for j,*facteurs in operation.get("eclairage",[]):
            a,b,c,m=original[j];ids=[]
            for k,f in zip((a,b,c),facteurs):
                v=cache.lire(k)
                couleur=tuple(max(0,min(255,round(ch*f/255))) for ch in v.couleur[:3])+(v.couleur[3],)
                ids.append(cache.ajouter(Sommet(v.position,couleur,v.uv,v.normale)))
            direct[j]=(*ids,m)
        for panneau in operation["baies"]:
            mode=panneau["mode"]
            interieur=panneau
            if mode!="corniche" and (mode=="piece" or panneau["deplacement"]>0):
                # Conserver sur place le cadre et les UV de l'atlas commercial,
                # même quand plusieurs fenêtres étaient peintes sur le même quadrilatère.
                w,h=panneau["largeur"],panneau["hauteur"]
                dx,dz=min(.105,w*.045),min(.11,h*.052)
                interieur=dict(panneau,largeur=w-2*dx,hauteur=h-2*dz,
                               centre=releve.monde((w/2,0,dz),panneau))
                nx,ny=panneau["n"];t=(-ny,nx,0.);cx,cy,cz=interieur["centre"]
                tab=cx*t[0]+cy*t[1];demi=interieur["largeur"]/2
                limites=((t,tab-demi),((ny,-nx,0.),-tab-demi),((0.,0.,1.),cz),((0.,0.,-1.),-cz-interieur["hauteur"]))
                delta=((-nx*panneau["deplacement"],-ny*panneau["deplacement"],0.) if mode=="retrait" else None)
                for face in panneau["faces"]:
                    prismes[face].append((limites,delta))
            for tri in construire_decor(interieur,plan["famille"],panneau["graine"]):
                ajouts.append(tuple((*releve.monde(v[:3],interieur),*v[3:]) for v in tri))
        def emettre(poly,m,decalage=None):
            for k in range(1,len(poly)-1):
                verts=[poly[0],poly[k],poly[k+1]]
                if aire_double(*(v.position for v in verts))<=1e-7:continue
                if decalage:
                    verts=[Sommet(tuple(p+d for p,d in zip(v.position,decalage)),v.couleur,v.uv,v.normale) for v in verts]
                faces.append((*[cache.ajouter(v) for v in verts],m))
        faces=[]
        for j,(a,b,c,m) in enumerate(original):
            if j not in prismes:
                faces.append(direct.get(j,(a,b,c,m)));continue
            restants=[[cache.lire(k) for k in (a,b,c)]]
            for limites,delta in prismes[j]:
                prochains=[]
                for poly in restants:
                    morceaux=retirer_prisme(poly,limites)
                    if len(morceaux)==1 and morceaux[0] is poly:
                        prochains.append(poly);continue
                    prochains.extend(morceaux)
                    if delta:
                        centre=poly
                        for axe,d in limites:
                            if len(centre)<3:break
                            centre,_=decouper(centre,axe,d)
                        if len(centre)>=3:emettre(centre,m,delta)
                restants=prochains
            for poly in restants:emettre(poly,m)
        cache.terminer(faces)
        if ajouts:
            indice=rw.ajouter_materiau(mats)
            annexes=rw.ajouter_triangles(g,ajouts,indice)
            faces.extend((*tri,indice) for tri in annexes)
        rw.remplacer(extensions,rw.BIN_MESH,liste_indices(faces))
        rw.remplacer(geo,rw.EXTENSION,rw.assembler(extensions))
        rw.remplacer(geo,rw.MATLIST,rw.assembler(mats))
        rw.remplacer(geo,rw.STRUCT,g.ecrire())
        groupe[i]=tag,ver,rw.assembler(geo)
    rw.remplacer(parties,rw.GEOMETRY_LIST,rw.assembler(groupe))
    sortie=textures.wrap(rw.CLUMP,version,rw.assembler(parties))
    if plan.get("sortie") and empreinte(sortie)!=plan["sortie"]:
        raise ValueError("Le générateur actuel ne correspond pas au plan de cette façade")
    return sortie


def retirer(actuel,original,plan):
    if empreinte(original)!=plan["source"] or empreinte(actuel) not in {plan["source"],plan["sortie"]}:
        raise ValueError("Source ou façade installée non reconnue")
    return original


def inventorier(origine, *, signer=True):
    """Analyse tous les noms placés par les IPL chargés, y compris les exclusions."""
    origine=Path(origine)
    ide,placements=carte(origine)
    dossier=chemin(origine,"models")
    index={textures.name(n):(s,k) for s,k,n in textures.ENTRY.iter_unpack(chemin(dossier,"gta3.dir").read_bytes())}
    plans={};etat={}
    with chemin(dossier,"gta3.img").open("rb") as image:
        def lire(nom):
            secteur,taille=index[nom];image.seek(2048*secteur);return image.read(taille*2048)
        col={};palettes={}
        def palette(dico):
            if dico not in palettes:
                key=dico+".txd"
                if key in index:
                    parts=textures.dictionary(lire(key))[1]
                    palettes[dico]={nom:atlas.profil_raster(raster) for _,_,_,nom,raster in textures.natives(parts)}
                else:
                    palettes[dico]={}
            return palettes[dico]
        for nom in sorted(n for n in index if n.endswith(".col")):
            col.update(blocs_collision(lire(nom)))
        col.update(blocs_collision(chemin(dossier,"coll/generic.col").read_bytes()))
        for nom,tous in sorted(placements.items()):
            dehors=[s for s in tous if s["zone"]==0]
            fiche={"quartiers":dict(Counter(p["quartier"] for p in dehors)),"placements":len(tous),"exterieurs":len(dehors)}
            etat[nom]=fiche
            entree=nom+".dff"
            if not dehors:motif="intérieur de mission ou de bâtiment"
            elif nom.startswith("lod") or "_lod" in nom:motif="niveau de détail lointain"
            elif entree not in index or nom not in ide:motif="source IDE/DFF absente"
            else:
                blob=lire(entree)
                variante_dyn=re.sub(r"(?:_?(?:nt|nite|night))$","_dy",nom)
                plan,motif=analyser(nom,blob,col.get(nom) or col.get(variante_dyn),dehors[0],ide[nom],palette(ide[nom]["txd"]))
                if plan:
                    plans[entree]=plan
                    continue
            fiche["motif"]=motif
        from voisinage_facades_ville import verifier
        voisins=verifier(plans,placements,ide,index,lire,palette)
        for entree,plan in plans.items():
            if signer:
                plan["sortie"]=empreinte(transformer(lire(entree),plan))
            detail=Counter(b["mode"] for g in plan["geometries"] for b in g["baies"])
            nb_lumiere=sum(len(g.get("eclairage",[])) for g in plan["geometries"])
            if nb_lumiere:detail["faces_eclairees"]=nb_lumiere
            plan["compte"]=dict(detail)
            etat[plan["nom"]].update(motif="transformé",operations=dict(detail),famille=plan["famille"])
    return {"plans":plans,"modeles":etat,"definitions":len(ide),"placements":sum(map(len,placements.values())),"pieces_preservees_voisins":voisins}


def planifier(origine):
    return inventorier(origine)["plans"]


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origine",type=Path);parser.add_argument("--rapport",type=Path,required=True)
    parser.add_argument("--releve-seul",action="store_true")
    args=parser.parse_args()
    resultat=inventorier(args.origine,signer=not args.releve_seul)
    args.rapport.parent.mkdir(parents=True,exist_ok=True)
    args.rapport.write_text(json.dumps(resultat,ensure_ascii=False,indent=1),encoding="utf-8")
    print(len(resultat["plans"]),"modèles transformables sur",len(resultat["modeles"]),"noms de modèles placés")
