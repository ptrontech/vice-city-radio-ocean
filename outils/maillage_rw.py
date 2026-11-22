"""Ajoute des volumes architecturaux au DFF PC de jour ou de nuit du Majestic.

Les matériaux et les UV d'origine sont conservés. Les pans recevant les ombres
utilisent une tessellation locale. Un matériau supplémentaire porte la couleur des moulures.
Les fichiers DFF du joueur sont lus au moment de l'installation.
"""
from dataclasses import dataclass
from math import dist, isfinite, sqrt
from struct import Struct, pack, unpack_from

from textures import CHUNK, chunks, wrap

STRUCT, EXTENSION, MATERIAL, MATLIST = 1, 3, 7, 8
GEOMETRY, CLUMP, GEOMETRY_LIST, BIN_MESH = 15, 16, 26, 0x50E
VEC = Struct("<3f")
TRI = Struct("<4H")
WHITE = bytes((255, 255, 255, 255))

def entree(sections, tag):
    indices = [i for i, (kind, _, _) in enumerate(sections) if kind == tag]
    if len(indices) != 1:
        raise ValueError(f"Section RenderWare {tag:#x} absente ou ambiguë")
    return indices[0]

def corps(sections, tag):
    return sections[entree(sections, tag)][2]

def remplacer(sections, tag, data):
    i = entree(sections, tag)
    kind, version, _ = sections[i]
    sections[i] = kind, version, data

def assembler(sections):
    return b"".join(wrap(*row) for row in sections)

def clump(blob):
    if len(blob) < CHUNK.size:
        raise ValueError("Modèle tronqué")
    kind, length, version = CHUNK.unpack_from(blob)
    end = CHUNK.size + length
    if kind != CLUMP or end > len(blob) or any(blob[end:]):
        raise ValueError("En-tête du DFF ou alignement IMG invalide")
    return version, list(chunks(blob[CHUNK.size:end]))

def noms_materiaux(parts):
    references = corps(parts, STRUCT)
    count, = unpack_from("<I", references)
    if len(references) != 4 + count * 4:
        raise ValueError("Table des matériaux invalide")
    entries = iter(data for kind, _, data in parts if kind == MATERIAL)
    names = []
    for i in range(count):
        ref, = unpack_from("<i", references, 4 + i * 4)
        if ref >= 0:
            if ref >= i:
                raise ValueError("Référence à un matériau inconnu")
            names.append(names[ref])
            continue
        data = next(entries, None)
        if data is None:
            raise ValueError("Matériau manquant")
        textures = [t for k, _, t in chunks(data) if k == 6]
        if not textures:
            names.append("")
            continue
        strings = [s for k, _, s in chunks(textures[0]) if k == 2]
        names.append(strings[0].split(b"\0", 1)[0].decode("ascii").lower())
    if next(entries, None) is not None:
        raise ValueError("Matériau en trop")
    return tuple(names)

@dataclass
class Geometrie:
    flags: int
    couleurs: bytes
    uv: list
    faces: bytes
    sphere: tuple
    positions: bytes
    normales: bytes

    @classmethod
    def lire(cls, data):
        flags, nf, nv, morph = unpack_from("<4I", data)
        if morph != 1 or flags & 0x1000000 or not (flags & 8):
            raise ValueError("Ce modèle doit utiliser un maillage PC à couleurs de sommets")
        layers = (flags >> 16) & 255
        if not layers:
            layers = 2 if flags & 128 else int(bool(flags & 4))
        if layers > 8 or not (0 < nv <= 65535):
            raise ValueError("Nombre de sommets ou de couches UV invalide")
        offset = 16
        def prendre(size):
            nonlocal offset
            section = data[offset:offset+size]
            offset += size
            if len(section) != size:
                raise ValueError("Table du maillage incomplète")
            return section
        colors = prendre(nv*4)
        uvs = [prendre(nv*8) for _ in range(layers)]
        triangles = prendre(nf*TRI.size)
        sphere = unpack_from("<4f2I", prendre(24))
        if sphere[4] != 1 or sphere[5] not in (0, 1):
            raise ValueError("Cible morphologique invalide")
        positions = prendre(nv*VEC.size)
        normales = prendre(nv*VEC.size) if sphere[5] else b""
        if offset != len(data):
            raise ValueError("Données de géométrie PC inattendues")
        return cls(flags, colors, uvs, triangles, sphere, positions, normales)

    def ecrire(self):
        return b"".join((pack("<4I", self.flags, len(self.faces)//TRI.size,
                              len(self.positions)//VEC.size, 1),
                         self.couleurs, *self.uv, self.faces, pack("<4f2I", *self.sphere),
                         self.positions, self.normales))

    def surface(self, materiaux):
        return {"positions":tuple(VEC.iter_unpack(self.positions)),
                "triangles":tuple((a,b,c,m) for b,a,m,c in TRI.iter_unpack(self.faces)),
                "materiaux":materiaux}

def ajouter_materiau(parts):
    i = entree(parts, STRUCT)
    kind, version, refs = parts[i]
    count, = unpack_from("<I", refs)
    parts[i] = kind, version, pack("<I", count+1) + refs[4:] + pack("<i", -1)
    blanc = pack("<I", 0) + WHITE + pack("<2I3f", 0, 0, 1., 0., 1.)
    parts.append((MATERIAL,version,wrap(STRUCT,version,blanc)+wrap(EXTENSION,version,b"")))
    return count

def ajouter_split(data, faces, materiau):
    strip, meshes, original_indices = unpack_from("<3I",data)
    if strip not in (0,1):
        raise ValueError("Type de primitive RenderWare non pris en charge")
    offset = 12
    lu = 0
    for _ in range(meshes):
        count, _ = unpack_from("<2I",data,offset)
        offset += 8 + 4*count
        lu += count
    if offset != len(data) or lu != original_indices:
        raise ValueError("Index du maillage source incohérent")
    indices = []
    for a,b,c in faces:
        if strip and indices:
            # Les indices répétés joignent deux triangles sans dessiner une face parasite.
            indices.extend((indices[-1],a))
            if len(indices)%2:
                indices.append(a)
        indices.extend((a,b,c))
    return (pack("<3I",strip,meshes+1,original_indices+len(indices)) + data[12:] +
            pack("<2I",len(indices),materiau) + pack(f"<{len(indices)}I",*indices))

def ajouter_triangles(g, triangles, materiau):
    depart = len(g.positions)//VEC.size
    sommets = {}
    pos, couleurs, normales, faces = bytearray(), bytearray(), bytearray(), []
    cx, cy, cz, ancien_rayon, positions_ok, normals_ok = g.sphere
    rayon = ancien_rayon
    for tri in triangles:
        if len(tri) != 3 or any(len(v) != 6 for v in tri):
            raise ValueError("Chaque face doit contenir trois sommets XYZ et RVB")
        for v in tri:
            if not all(isfinite(c) for c in v[:3]) or any(type(c) is not int or not 0 <= c <= 255 for c in v[3:]):
                raise ValueError("Coordonnée ou couleur invalide dans le relief")
        a,b,c = [v[:3] for v in tri]
        ux,uy,uz = [b[i]-a[i] for i in range(3)]
        vx,vy,vz = [c[i]-a[i] for i in range(3)]
        normale = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        norme = sqrt(sum(n*n for n in normale))
        if norme < 1e-8:
            continue
        normal_raw = VEC.pack(*(n/norme for n in normale)) if normals_ok else b""
        ids = []
        for v in tri:
            xyz, rgba = VEC.pack(*v[:3]), bytes((*v[3:],255))
            key = xyz, rgba, normal_raw
            if key not in sommets:
                index = depart + len(sommets)
                if index >= 65535:
                    raise ValueError("Le relief dépasse la capacité du maillage PC")
                sommets[key] = index
                pos.extend(xyz)
                couleurs.extend(rgba)
                normales.extend(normal_raw)
                rayon = max(rayon, dist(v[:3],(cx,cy,cz))+.01)
            ids.append(sommets[key])
        faces.append(tuple(ids))
    if not faces:
        raise ValueError("Aucune face architecturale à installer")
    g.positions += pos
    g.couleurs += couleurs
    g.normales += normales
    g.uv = [layer + bytes(8*len(sommets)) for layer in g.uv]
    g.faces += b"".join(TRI.pack(b,a,materiau,c) for a,b,c in faces)
    g.sphere = (cx,cy,cz,rayon,positions_ok,normals_ok)
    return faces

def ouvrir_modele(blob):
    version, parties = clump(blob)
    groupe = list(chunks(corps(parties, GEOMETRY_LIST)))
    geo = list(chunks(corps(groupe, GEOMETRY)))
    g = Geometrie.lire(corps(geo, STRUCT))
    mats = list(chunks(corps(geo, MATLIST)))
    return version, parties, groupe, geo, g, mats

def lire_surface(blob):
    _, _, _, _, g, mats = ouvrir_modele(blob)
    return g.surface(noms_materiaux(mats))

def appliquer_relief(blob, nuit=False, constructeur=None, ombres=True):
    if constructeur is None:
        from relief_majestic import construire_relief
        constructeur = construire_relief
    version, parties, groupe, geo, g, mats = ouvrir_modele(blob)
    surface = g.surface(noms_materiaux(mats))
    if "hotelwindow2" not in surface["materiaux"] or "hotelpeach" not in surface["materiaux"]:
        raise ValueError("Ce DFF ne correspond pas au Majestic d’Ocean Drive")
    ajouts = list(constructeur(surface,nuit=nuit))
    extensions = list(chunks(corps(geo, EXTENSION)))
    if ombres:
        from ombres_majestic import cuire
        ombres_cuites = cuire(g, surface, ajouts, nuit=nuit)
        if ombres_cuites is not None:
            remplacer(extensions, BIN_MESH, ombres_cuites)
    indice = ajouter_materiau(mats)
    faces = ajouter_triangles(g,ajouts,indice)
    remplacer(extensions, BIN_MESH, ajouter_split(corps(extensions,BIN_MESH),faces,indice))
    remplacer(geo, EXTENSION, assembler(extensions))
    remplacer(geo, MATLIST, assembler(mats))
    remplacer(geo, STRUCT, g.ecrire())
    remplacer(groupe, GEOMETRY, assembler(geo))
    remplacer(parties, GEOMETRY_LIST, assembler(groupe))
    return wrap(CLUMP,version,assembler(parties))
