"""Two original, higher-resolution street materials for classic Vice City PC 1.0.

The authored BC1 mip chains come from the user's own game. No image is bundled.
Usage: python textures.py GAME_DIRECTORY DESTINATION/models/generic.txd
"""
import argparse
from hashlib import file_digest, sha256
import os
from pathlib import Path
import shutil
from struct import Struct, pack, pack_into, unpack_from
from tempfile import NamedTemporaryFile

CHUNK = Struct("<III")
ENTRY = Struct("<II24s")
SECTOR = 2048
RETAIL = {
    "generic.txd": "8f28f214bdc9f103f86ee7bf8a29ed5829ee26a64cce2c0eeb7b1906a37983c2",
    "gta3.dir": "6ba9f9a3c7eebf7f0b162a92b228bdafe6a04d33daec0e11b548d3a057b8a49e",
    "gta3.img": "12547d034a5b114b891582e36b7214794e5eafe1ad75a653bf2d9b3e2e18849a",
}
DONORS = {
    "nbhotel01.txd": ("road2_256", "16c8247b03bea2b505ebd6bbef29ef7f460d7527090e101db12afd1ee86c8923"),
    "nbdecopromnd.txd": ("kbpavementgrass256", "7fa7b3ad1f7385f28827de06dea1a00877af5b2574e1f04d9c4d04cdd72401ec"),
}

def chunks(data):
    pos = 0
    while pos < len(data):
        kind, length, version = CHUNK.unpack_from(data, pos)
        end = pos + CHUNK.size + length
        if end > len(data):
            raise ValueError("Section RenderWare tronquée")
        yield kind, version, data[pos+CHUNK.size:end]
        pos = end

def wrap(kind, version, data):
    return CHUNK.pack(kind, len(data), version) + data

def dictionary(blob):
    kind, size, version = CHUNK.unpack_from(blob)
    if kind != 0x16 or CHUNK.size + size > len(blob) or any(blob[CHUNK.size+size:]):
        raise ValueError("Dictionnaire TXD ou remplissage IMG incorrect")
    return version, list(chunks(blob[CHUNK.size:CHUNK.size+size]))

def name(raw):
    return raw.partition(b"\x00")[0].decode("ascii").lower()

def natives(parts):
    for index, (kind, version, payload) in enumerate(parts):
        if kind != 0x15:
            continue
        inner = list(chunks(payload))
        if not inner or inner[0][0] != 1 or len(inner[0][2]) < 88:
            raise ValueError("Texture native D3D8 incorrecte")
        raster = inner[0][2]
        yield index, version, inner, name(raster[8:40]), raster

def mipmaps(data):
    """Return the encoded BC1 levels and verify the device, opacity flag and block sizes."""
    fmt, alpha, w, h, depth, levels, raster_type, compression = unpack_from("<IIHHBBBB", data, 72)
    if (unpack_from("<I",data)[0], fmt, alpha, w, h, depth, levels, raster_type, compression) != (8, 0x8200, 0, 256, 256, 16, 9, 4, 1):
        raise ValueError("Chaîne BC1 originale incompatible")
    pos = 88
    images = []
    for level in range(levels):
        n = unpack_from("<I",data,pos)[0]
        side = max(1,w >> level)
        if n != ((side + 3) // 4) ** 2 * 8 or pos + 4 + n > len(data):
            raise ValueError("Longueur BC1 incohérente")
        images.append(data[pos+4:pos+4+n])
        pos += 4+n
    if pos != len(data):
        raise ValueError("Données inattendues après les mipmaps")
    return images

def upgrade(blob, donors):
    version, parts = dictionary(blob)
    changed = []
    for index, native_version, inner, material, data in natives(parts):
        if material not in donors:
            continue
        source = donors[material]
        if data[:8] != source[:8] or data[40:72] != source[40:72]:
            raise ValueError(f"Échantillonnage ou masque différent pour {material}")
        kind, data_version, _ = inner[0]
        inner[0] = (kind, data_version, data[:72] + source[72:])
        parts[index] = (0x15, native_version, b"".join(wrap(*item) for item in inner))
        changed.append(material)
    if not changed:
        raise ValueError("Aucun matériau ciblé dans le dictionnaire")
    result = wrap(0x16, version, b"".join(wrap(*item) for item in parts))
    _, verified = dictionary(result)
    for _, _, _, material, data in natives(verified):
        if material in changed and mipmaps(data) != mipmaps(donors[material]):
            raise ValueError(f"Les pixels de {material} diffèrent du donneur")
    return result, changed

def digest(path):
    with path.open("rb") as src:
        return file_digest(src, "sha256")

def replace(path, wanted, write):
    path.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=".radio-textures-", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        with temporary.open("wb") as output:
            write(output)
        if digest(temporary).hexdigest() != wanted:
            raise OSError(f"Erreur de copie de {path.name}")
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)

def construire(origine, destination):
    base = (Path(origine)/"models").resolve()
    dest = Path(destination).resolve()
    if dest.name.lower() != "generic.txd" or dest.parent == base:
        raise ValueError("Le dossier de sortie doit être une autre installation")
    directory = (base/"gta3.dir").read_bytes()
    loose = (base/"generic.txd").read_bytes()
    source_img = base/"gta3.img"
    whole = digest(source_img)
    if (sha256(directory).hexdigest(), sha256(loose).hexdigest(), whole.hexdigest()) != (
            RETAIL["gta3.dir"], RETAIL["generic.txd"], RETAIL["gta3.img"]):
        raise ValueError("Installation source différente du jeu personnel vérifié")
    entries = [(offset, size, name(n)) for offset,size,n in ENTRY.iter_unpack(directory)]
    donors = {}
    originals = []
    with source_img.open("rb") as image:
        for i,(offset,size,filename) in enumerate(entries):
            if filename not in DONORS and filename != "generic.txd":
                continue
            image.seek(offset*SECTOR)
            blob = image.read(size*SECTOR)
            if filename == "generic.txd":
                originals.append((i,blob))
                continue
            material, expected = DONORS[filename]
            hits = [data for _,_,_,n,data in natives(dictionary(blob)[1]) if n==material]
            if len(hits)!=1 or sha256(hits[0][88:]).hexdigest()!=expected:
                raise ValueError(f"Source du matériau {material} inattendue")
            mipmaps(hits[0])
            donors[material]=hits[0]
    if len(donors)!=2 or len(originals)!=2:
        raise ValueError("Sources de textures incomplètes")
    new_loose, loose_materials = upgrade(loose,donors)
    if set(loose_materials) != set(donors):
        raise ValueError("Le dictionnaire externe est incomplet")
    new_dir = bytearray(directory)
    tail = bytearray()
    length = source_img.stat().st_size
    if length % SECTOR:
        raise ValueError("Image IMG mal alignée")
    for index,blob in originals:
        upgraded,_ = upgrade(blob,donors)
        count = (len(upgraded)+SECTOR-1)//SECTOR
        pack_into("<II",new_dir,index*ENTRY.size,(length+len(tail))//SECTOR,count)
        tail.extend(upgraded)
        tail.extend(bytes(count*SECTOR-len(upgraded)))
    whole.update(tail)
    def write_image(target):
        with source_img.open("rb") as src:
            shutil.copyfileobj(src,target,1024*1024)
        target.write(tail)
    changes = [
        (dest.parent/"gta3.img", whole.hexdigest(), write_image),
        (dest.parent/"gta3.dir", sha256(new_dir).hexdigest(), lambda f:f.write(new_dir)),
        (dest, sha256(new_loose).hexdigest(), lambda f:f.write(new_loose)),
    ]
    # All retail sectors survive in place. The old index remains valid if installation stops before its swap.
    pending = []
    for path, expected, populate in changes:
        if path.exists():
            current = digest(path).hexdigest()
            if current == expected:
                continue
            if current != RETAIL[path.name.lower()]:
                raise ValueError(f"Une autre modification existe dans {path}")
        pending.append((path, expected, populate))
    for path,expected,populate in pending:
        replace(path,expected,populate)
    return {"materials": sorted(loose_materials), "mipmaps": 9, "img_extra_bytes": len(tail),
            "sha256": {path.name: wanted for path,wanted,_ in changes}}

if __name__ == "__main__":
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origine",type=Path)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    print(json.dumps(construire(args.origine,args.destination),indent=2))
