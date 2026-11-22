"""Vérifie la continuité du quai sur les fichiers géométriques fournis par l'utilisateur.

Usage : python tests/quai_geometrie.py "E:/Games/GTA_VC_1.0".
Les maillages, fichiers de circulation et placements restent sur le disque local.
"""
import json
import math
import re
import struct
import sys
from pathlib import Path

def models(file):
    data = file.read_bytes()
    out, offset = {}, 0
    while offset < len(data):
        magic, size = struct.unpack_from("<4sI", data, offset)
        assert magic == b"COLL", file
        name = data[offset+8:offset+30].split(b"\0",1)[0].decode("latin1").lower()
        cur = offset+72
        def count():
            nonlocal cur
            value = struct.unpack_from("<I",data,cur)[0]
            cur += 4
            return value
        for stride in (20,24,28):
            number=count()
            cur += number*stride
        number = count()
        verts=[struct.unpack_from("<3f",data,cur+12*i) for i in range(number)]
        cur += number*12
        faces=count()
        out[name] = [tuple(verts[i] for i in struct.unpack_from("<3I",data,cur+16*j)) for j in range(faces)]
        assert cur+16*faces == offset+8+size
        offset += size+8
    return out

def transform(mesh, x, y, z, rot, size=(1,1,1)):
    qx,qy,qz,qw=rot
    def vertex(v):
        a,b,c=(v[i]*size[i] for i in range(3))
        return (x+a*(1-2*qy*qy-2*qz*qz)+b*(2*qx*qy+2*qw*qz)+c*(2*qx*qz-2*qw*qy),
                y+a*(2*qx*qy-2*qw*qz)+b*(1-2*qx*qx-2*qz*qz)+c*(2*qy*qz+2*qw*qx),
                z+a*(2*qx*qz+2*qw*qy)+b*(2*qy*qz-2*qw*qx)+c*(1-2*qx*qx-2*qy*qy))
    return [tuple(vertex(v) for v in triangle) for triangle in mesh]

def heights(mesh,x,y):
    for (x1,y1,z1),(x2,y2,z2),(x3,y3,z3) in mesh:
        denom=(y2-y3)*(x1-x3)+(x3-x2)*(y1-y3)
        if abs(denom)<.0001:continue
        a=((y2-y3)*(x-x3)+(x3-x2)*(y-y3))/denom
        b=((y3-y1)*(x-x3)+(x1-x3)*(y-y3))/denom
        if min(a,b,1-a-b)>=-.00001:yield a*z1+b*z2+(1-a-b)*z3

def samples(a,b,step):
    count=max(1, math.ceil(math.dist(a,b)/step))
    for i in range(count+1):
        yield tuple(x+(y-x)*i/count for x,y in zip(a,b))

def boat_clearance(path, decks):
    groups=[]
    for line in path.read_text().splitlines():
        values=[v.strip() for v in line.split(",")]
        if len(values)==2:
            groups.append((int(values[0]),[]))
        elif len(values)>=11:
            s=list(map(float,values))
            groups[-1][1].append((int(s[0]),int(s[1]),s[3]/16,s[4]/16))
    nearest=float("inf")
    for kind,links in groups:
        if kind!=2:continue
        for typ,tip,x,y in links:
            if not typ or not 0<=tip<len(links) or not links[tip][0]:continue
            ex,ey=links[tip][2:]
            if max(x,ex)<-890 or min(x,ex)>-690 or max(y,ey)<-450 or min(y,ey)>-215:continue
            for px,py in samples((x,y),(ex,ey),0.5):
                for _,cx,cy,_,angle in decks:
                    heading=math.radians(angle)
                    dx,dy=px-cx,py-cy
                    across=abs(dx*math.cos(heading)+dy*math.sin(heading))
                    along=abs(-dx*math.sin(heading)+dy*math.cos(heading))
                    nearest=min(nearest,math.hypot(max(0,across-4),max(0,along-21.4)))
    return nearest

def main(root):
    src=(Path(__file__).resolve().parents[1]/"jeu/07_quai.js").read_text(encoding="utf-8")
    plan=json.loads(re.search(r"^const quaiPlan = (.*?);$",src,re.M|re.S).group(1))
    maps=root/"data/maps"; local=models(maps/"littleha/littleha.col")
    deck=local["lhjetty"]; originals=[]; original_deck=[]
    for name in ("littleha","haiti","haitiN","docks","islandsf","washints","washintn","oceandrv"):
        folder=maps/name
        model_set=local if name=="littleha" else models(next(folder.glob("*.col")))
        for line in next(folder.glob("*.ipl")).read_text(encoding="latin1").splitlines():
            parts=[v.strip() for v in line.split(",")]
            if len(parts)!=13 or int(parts[2]) not in (0,13):continue
            model=parts[1].lower();x,y,z,sx,sy,sz,*rot=map(float,parts[3:])
            if model.startswith("lod") or model not in model_set:continue
            tris=transform(model_set[model],x,y,z,rot,(sx,sy,sz))
            if model=="lhjetty":original_deck.extend(tris)
            for tri in tris:
                if min(v[0] for v in tri)<-748 and max(v[0] for v in tri)>-820 and min(v[1] for v in tri)<-258 and max(v[1] for v in tri)>-375:
                    originals.append(tri)
    sections=plan["objets"][:2];added=[]
    for model,x,y,z,angle in sections:
        assert model==1431
        h=-math.radians(angle)/2
        added += transform(deck,x,y,z,(0,0,math.sin(h),math.cos(h)))
    orig_where=next(line for line in (root/"data/navig.zon").read_text().splitlines() if line.startswith("HAVANA,"))
    assert len(orig_where.split(","))==9
    water=next(float(line.split(",")[0]) for line in (root/"data/water.dat").read_text().splitlines() if line[:1].isdigit())
    assert abs(water-6)<.01
    assert any(7.1<h<7.4 for h in heights(original_deck,*plan["entree"][:2]))
    original_shore=list(heights(originals,-812,-342))
    assert any(9.8<h<10.3 for h in original_shore)
    for x,y,_ in plan["parcours"][2:]:
        assert not any(water<h<15 for h in heights(originals,x,y)), ("surface d'origine",x,y)
    count=0
    for a,b in zip(plan["parcours"],plan["parcours"][1:]):
        for x,y,z in samples(a,b,.25):
            assert any(abs(h-(z-1))<.13 for h in heights(original_deck+added,x,y)), ("rupture du ponton",x,y)
            count+=1
    clearance=boat_clearance(maps/"paths.ipl",sections)
    # Entre deux échantillons distants de 50 cm, le minimum réel peut être inférieur de 25 cm.
    assert math.isfinite(clearance) and clearance-.25>20
    print(f"{count} appuis vérifiés tous les 25 cm, eau {water:.2f} m, chenal à plus de {clearance-.25:.1f} m")

if __name__=="__main__": main(Path(sys.argv[1]))
