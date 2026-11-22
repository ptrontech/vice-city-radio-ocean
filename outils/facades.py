"""Façade de l'hôtel d'Ocean Drive, deux cibles avec grain d'origine :
  - htl_ext03.txd : béton bow_abattoir_conc2 (soubassement, seuil) 128 -> 256, 9 niveaux ;
  - od_hotels1.txd : crépi hotelpeach (murs verticaux) 64 -> 128, 8 niveaux.
Le niveau à la taille d'origine (niveau 1) reprend l'original BC1 octet pour octet, après
contrôle de cohérence ; seuls les niveaux 0 et 2 et suivants sont recalculés.

Intégration (Codex) :
    from facades import TXD_CIBLES, ameliorer_txd
    if nom in TXD_CIBLES:
        nouveau = ameliorer_txd(nom, blob)      # blob = TXD lu dans gta3.img, sans remplissage requis

`ameliorer_txd` n'utilise que le blob passé : aucune ressource locale supplémentaire.
Le résultat est un dictionnaire TXD sans remplissage IMG (à aligner sur 2048 octets comme
textures.py). Rien n'est écrit sur disque ; l'index IMG et le retrait réversible restent à
la charge du générateur de voirie.

Méthode (mathématiques seulement, aucun octet de pixel du jeu dans ce fichier) :
  1. Décodage BC1 du béton `bow_abattoir_conc2` (128 × 128, opaque, un niveau).
  2. Agrandissement ×2 par Catmull-Rom TORIQUE (échantillonnage avec rebouclage), puis
     rétro-projection : la moyenne de chaque bloc 2 × 2 redonne exactement le pixel d'origine
     (lumière et motif conservés).
  3. Grain : résiduel haute fréquence R = L - flou(L) de la VRAIE surface (L = luminance),
     donc de même nature que le matériau. R est recopié sur la grille 256 par miroir
     (période 256, continu, donc périodique) : ses détails tombent dans la bande au-delà
     de la finesse de la source. Amplitude faible (RMS <= 3 niveaux, crête <= 9), atténuée
     là où le gradient est fort (bords des panneaux), puis rendue de moyenne nulle sur chaque
     bloc 2 × 2 : ni changement de teinte, ni de lumière. Ajouté de façon identique à R, V, B.
  4. Chaîne de 9 mipmaps (256 -> 1) par moyenne 2 × 2, encodée en BC1 (4 couleurs, opaque).
  5. Seul le matériau ciblé est remplacé ; nom, masque, échantillonneur (octets 0-71 du raster),
     chunks d'extension et toutes les autres textures (dont `clevelanderdetails`) restent
     identiques à l'octet. `verifier` le contrôle avant de rendre le résultat.

Python standard uniquement (encodeur BC1 inclus, Pillow inutile). Réutilise les fonctions
RenderWare de textures.py (chunks, wrap, dictionary, natives).
"""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from struct import pack, unpack_from


def _charger_textures():
    chemin = Path(__file__).resolve().with_name("textures.py")
    spec = importlib.util.spec_from_file_location("radio_textures_voirie", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


textures = _charger_textures()

TXD_CIBLES = ("htl_ext03.txd", "od_hotels1.txd")
MATERIAUX = {"htl_ext03.txd": "bow_abattoir_conc2",     # soubassement et seuil
             "od_hotels1.txd": "hotelpeach"}            # crépi des murs verticaux
MATERIAU_BETON = "bow_abattoir_conc2"                   # matériau par défaut des outils de comparatif
MATERIAU_CREPI = "hotelpeach"
DECORATION = "clevelanderdetails"   # doit rester identique à l'octet
# matériau -> (côté source, côté cible, nombre de mipmaps de la cible)
PROFILS = {MATERIAU_BETON: (128, 256, 9), MATERIAU_CREPI: (64, 128, 8)}
# Tailles de niveaux et octets BC1 à partir de l’octet 88 du raster d’origine.
ORIGINE_SHA256 = {
    MATERIAU_BETON: "d15de2af1d9c8fb5331c5f806736c0dc834b5ed7d1b5d9fab7bca5a652960dec",
    MATERIAU_CREPI: "e69f7c45be7ca72212cb5584d1424e6760fb40dec53bb5156b670f9e0f79ba14",
}

COTE_SOURCE, COTE_CIBLE, NIVEAUX = PROFILS[MATERIAU_BETON]   # valeurs du béton par défaut
TOLERANCE_LUMIERE, TOLERANCE_TEINTE, TOLERANCE_MIPMAPS = 5.0, 1.5, 6.0
GAIN_GRAIN = 0.6        # part du résiduel réinjectée
RMS_MAX = 3.0           # grain final <= 3 niveaux RMS (sur 255)
CRETE_MAX = 9.0
RMS_MIN_SOURCE = 0.4    # en dessous : surface sans grain exploitable
RMS_MIN_GRAIN = 0.15
KAPPA_BORD = 24.0       # gradient (niveaux/pixel) qui divise le grain par 4
DRAPEAU_MIPMAP, DRAPEAU_AUTO_MIPMAP = 0x8000, 0x4000


# --------------------------------------------------------------------------- BC1

def _vers_rgb(c):
    r, g, b = c >> 11, (c >> 5) & 63, c & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def _palette(c0, c1):
    p0, p1 = _vers_rgb(c0), _vers_rgb(c1)
    if c0 > c1:
        return [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
    return [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)), None]


def decoder_bc1(data, w, h):
    """Décode un niveau BC1 en trois listes plates R, V, B. Refuse les blocs transparents."""
    R, G, B = [0] * (w * h), [0] * (w * h), [0] * (w * h)
    pos = 0
    for by in range((h + 3) // 4):
        for bx in range((w + 3) // 4):
            c0, c1, bits = unpack_from("<HHI", data, pos)
            pos += 8
            pal = _palette(c0, c1)
            for py in range(min(4, h - by * 4)):
                for px in range(min(4, w - bx * 4)):
                    couleur = pal[(bits >> (2 * (4 * py + px))) & 3]
                    if couleur is None:
                        raise ValueError("Bloc BC1 transparent : texture non opaque")
                    i = (by * 4 + py) * w + bx * 4 + px
                    R[i], G[i], B[i] = couleur
    return R, G, B


def _quantifier(r, g, b):
    q = lambda x, m: min(m, max(0, int(round(x * m / 255.0))))
    return (q(r, 31) << 11) | (q(g, 63) << 5) | q(b, 31)


def _evaluer(pix, q0, q1):
    if q0 < q1:
        q0, q1 = q1, q0
    if q0 == q1:
        base = _vers_rgb(q0)
        err = sum((p[0] - base[0]) ** 2 + (p[1] - base[1]) ** 2 + (p[2] - base[2]) ** 2 for p in pix)
        return err, [0] * len(pix), q0, q1
    pal = _palette(q0, q1)
    err, idx = 0.0, []
    for p in pix:
        meilleur, k = None, 0
        for j, c in enumerate(pal):
            d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
            if meilleur is None or d < meilleur:
                meilleur, k = d, j
        err += meilleur
        idx.append(k)
    return err, idx, q0, q1


def _moindres_carres(pix, idx):
    alphas = (1.0, 0.0, 2 / 3, 1 / 3)
    aa = bb = ab = 0.0
    ap, bp = [0.0] * 3, [0.0] * 3
    for p, i in zip(pix, idx):
        a = alphas[i]
        b = 1.0 - a
        aa += a * a
        bb += b * b
        ab += a * b
        for k in range(3):
            ap[k] += a * p[k]
            bp[k] += b * p[k]
    det = aa * bb - ab * ab
    if abs(det) < 1e-9:
        return None
    e0 = [(bb * ap[k] - ab * bp[k]) / det for k in range(3)]
    e1 = [(aa * bp[k] - ab * ap[k]) / det for k in range(3)]
    return _quantifier(*e0), _quantifier(*e1)


def _bloc_bc1(pix):
    n = len(pix)
    m = [sum(p[k] for p in pix) / n for k in range(3)]
    d = [(p[0] - m[0], p[1] - m[1], p[2] - m[2]) for p in pix]
    cxx = sum(x * x for x, _, _ in d)
    cyy = sum(y * y for _, y, _ in d)
    czz = sum(z * z for _, _, z in d)
    if cxx + cyy + czz < 1e-9:
        q = _quantifier(*m)
        return pack("<HHI", q, q, 0)
    cxy = sum(x * y for x, y, _ in d)
    cxz = sum(x * z for x, _, z in d)
    cyz = sum(y * z for _, y, z in d)
    v = (cxx + cxy + cxz, cxy + cyy + cyz, cxz + cyz + czz)
    for _ in range(6):
        v = (cxx * v[0] + cxy * v[1] + cxz * v[2], cxy * v[0] + cyy * v[1] + cyz * v[2],
             cxz * v[0] + cyz * v[1] + czz * v[2])
        norme = math.sqrt(sum(x * x for x in v))
        if norme < 1e-12:
            v = (1.0, 1.0, 1.0)
            norme = math.sqrt(3.0)
        v = tuple(x / norme for x in v)
    t = [x * v[0] + y * v[1] + z * v[2] for x, y, z in d]
    lo, hi = min(t), max(t)
    e0 = [m[k] + v[k] * lo for k in range(3)]
    e1 = [m[k] + v[k] * hi for k in range(3)]
    candidat = (_quantifier(*e0), _quantifier(*e1))
    meilleur = None
    for _ in range(3):
        err, idx, c0, c1 = _evaluer(pix, *candidat)
        if meilleur is None or err < meilleur[0]:
            meilleur = (err, idx, c0, c1)
        suite = _moindres_carres(pix, idx) if c0 != c1 else None
        if suite is None:
            break
        candidat = suite
    _, idx, c0, c1 = meilleur
    bits = 0
    for k, i in enumerate(idx):
        bits |= i << (2 * k)
    return pack("<HHI", c0, c1, bits)


def encoder_bc1(canaux, w, h):
    """Encode trois plans flottants 0-255 en BC1 4 couleurs (jamais transparent)."""
    R, G, B = canaux
    sortie = bytearray()
    for by in range((h + 3) // 4):
        for bx in range((w + 3) // 4):
            pix = []
            for py in range(4):
                y = min(by * 4 + py, h - 1)
                for px in range(4):
                    i = y * w + min(bx * 4 + px, w - 1)
                    pix.append((R[i], G[i], B[i]))
            sortie += _bloc_bc1(pix)
    return bytes(sortie)


# --------------------------------------------------------------------------- images torique

def _cr(t):
    return ((-t ** 3 + 2 * t ** 2 - t) / 2, (3 * t ** 3 - 5 * t ** 2 + 2) / 2,
            (-3 * t ** 3 + 4 * t ** 2 + t) / 2, (t ** 3 - t ** 2) / 2)


_POIDS_PAIR, _POIDS_IMPAIR = _cr(0.75), _cr(0.25)   # sorties 2i (position i-1/4) et 2i+1 (i+1/4)


def agrandir(c, n):
    """Plan n×n -> 2n×2n : Catmull-Rom torique + rétro-projection (moyenne 2×2 = source)."""
    m = 2 * n
    tmp = [0.0] * (n * m)
    for y in range(n):
        o = y * n
        for x in range(n):
            a, b, cc, d = c[o + (x - 2) % n], c[o + (x - 1) % n], c[o + x], c[o + (x + 1) % n]
            e = c[o + (x + 2) % n]
            p, q = _POIDS_PAIR, _POIDS_IMPAIR
            tmp[y * m + 2 * x] = p[0] * a + p[1] * b + p[2] * cc + p[3] * d
            tmp[y * m + 2 * x + 1] = q[0] * b + q[1] * cc + q[2] * d + q[3] * e
    sortie = [0.0] * (m * m)
    p, q = _POIDS_PAIR, _POIDS_IMPAIR
    for y in range(n):
        h0, h1, h2, h3, h4 = ((y + k) % n * m for k in (-2, -1, 0, 1, 2))
        for x in range(m):
            sortie[2 * y * m + x] = p[0] * tmp[h0 + x] + p[1] * tmp[h1 + x] + p[2] * tmp[h2 + x] + p[3] * tmp[h3 + x]
            sortie[(2 * y + 1) * m + x] = q[0] * tmp[h1 + x] + q[1] * tmp[h2 + x] + q[2] * tmp[h3 + x] + q[3] * tmp[h4 + x]
    for y in range(n):
        for x in range(n):
            i = 2 * y * m + 2 * x
            moyenne = (sortie[i] + sortie[i + 1] + sortie[i + m] + sortie[i + m + 1]) / 4
            ecart = c[y * n + x] - moyenne
            sortie[i] += ecart
            sortie[i + 1] += ecart
            sortie[i + m] += ecart
            sortie[i + m + 1] += ecart
    return sortie


def reduire(c, n):
    """Moyenne 2×2 : plan n×n -> n/2 × n/2."""
    m = n // 2
    return [(c[2 * y * n + 2 * x] + c[2 * y * n + 2 * x + 1] + c[(2 * y + 1) * n + 2 * x]
             + c[(2 * y + 1) * n + 2 * x + 1]) / 4 for y in range(m) for x in range(m)]


def _flou(c, n):
    tmp = [0.0] * (n * n)
    for y in range(n):
        o = y * n
        for x in range(n):
            tmp[o + x] = (c[o + (x - 2) % n] + 4 * c[o + (x - 1) % n] + 6 * c[o + x]
                          + 4 * c[o + (x + 1) % n] + c[o + (x + 2) % n]) / 16
    sortie = [0.0] * (n * n)
    for y in range(n):
        h0, h1, h2, h3, h4 = ((y + k) % n * n for k in (-2, -1, 0, 1, 2))
        for x in range(n):
            sortie[y * n + x] = (tmp[h0 + x] + 4 * tmp[h1 + x] + 6 * tmp[h2 + x] + 4 * tmp[h3 + x] + tmp[h4 + x]) / 16
    return sortie


def luminance(R, G, B):
    return [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in zip(R, G, B)]


def energie_hf(L, n):
    """RMS de L - flou(L) : mesure du détail le plus fin."""
    f = _flou(L, n)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(L, f)) / len(L))


# --------------------------------------------------------------------------- grain

def calculer_grain(R, G, B, n=COTE_SOURCE):
    """Grain périodique (2n×2n) tiré de la surface source ; renvoie (grain, statistiques)."""
    L = luminance(R, G, B)
    residu = [a - b for a, b in zip(L, _flou(L, n))]
    rms = math.sqrt(sum(r * r for r in residu) / len(residu))
    if rms < RMS_MIN_SOURCE:
        raise ValueError("Surface trop lisse : aucun grain exploitable à transférer")
    gain = min(GAIN_GRAIN, RMS_MAX / rms)
    g2 = []                                 # gradient² (différences centrées, rebouclées)
    for y in range(n):
        for x in range(n):
            gx = (L[y * n + (x + 1) % n] - L[y * n + (x - 1) % n]) / 2
            gy = (L[(y + 1) % n * n + x] - L[(y - 1) % n * n + x]) / 2
            g2.append(gx * gx + gy * gy)
    poids = []                              # gradient dilaté 3×3 : le résiduel « sonne » autour d'un bord
    for y in range(n):
        for x in range(n):
            fort = max(g2[(y + dy) % n * n + (x + dx) % n] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            poids.append(1.0 / (1.0 + fort / (KAPPA_BORD * KAPPA_BORD)) ** 2)
    m = 2 * n
    grain = [0.0] * (m * m)
    for y in range(m):
        sy = y if y < n else m - 1 - y
        for x in range(m):
            sx = x if x < n else m - 1 - x
            v = gain * residu[sy * n + sx] * poids[(y // 2) * n + x // 2]
            grain[y * m + x] = max(-CRETE_MAX, min(CRETE_MAX, v))
    for y in range(n):                      # moyenne nulle par bloc 2×2 : lumière intacte
        for x in range(n):
            i = 2 * y * m + 2 * x
            moyenne = (grain[i] + grain[i + 1] + grain[i + m] + grain[i + m + 1]) / 4
            for j in (i, i + 1, i + m, i + m + 1):
                grain[j] -= moyenne
    rms_grain = math.sqrt(sum(g * g for g in grain) / len(grain))
    if rms_grain < RMS_MIN_GRAIN:
        raise ValueError("Grain transféré trop faible : amélioration nulle")
    # Le recentrage des blocs peut relever leur crête. Un facteur commun
    # préserve la moyenne nulle de chaque bloc et borne le grain livré.
    crete = max(abs(g) for g in grain)
    facteur = min(1.0, CRETE_MAX / crete, RMS_MAX / rms_grain)
    if facteur < 1.0:
        grain = [g * facteur for g in grain]
    return grain, {"rms_source": rms, "gain": gain, "rms_grain": rms_grain * facteur,
                   "crete": crete * facteur}


def ameliorer_pixels(R, G, B, n=COTE_SOURCE):
    """Renvoie les trois plans 2n×2n flottants (0-255) et les statistiques du grain."""
    grain, stats = calculer_grain(R, G, B, n)
    plans = []
    for canal in (R, G, B):
        grand = agrandir([float(v) for v in canal], n)
        plans.append([min(255.0, max(0.0, a + b)) for a, b in zip(grand, grain)])
    return plans, stats


def chaine_mipmaps(plans, cote):
    """Niveaux BC1 (octets) de `cote` jusqu'à 1×1."""
    niveaux, courant = [], plans
    while True:
        niveaux.append(encoder_bc1(courant, cote, cote))
        if cote == 1:
            return niveaux
        courant = [reduire(c, cote) for c in courant]
        cote //= 2


# --------------------------------------------------------------------------- RenderWare

def lire_raster(data):
    """Analyse un raster D3D8 BC1 opaque ; lève ValueError sinon."""
    if len(data) < 88:
        raise ValueError("Raster D3D8 trop court")
    plateforme = unpack_from("<I", data)[0]
    fmt, alpha, w, h, profondeur, niveaux, rtype, compression = unpack_from("<IIHHBBBB", data, 72)
    if plateforme != 8:
        raise ValueError("Plateforme de texture différente de D3D8")
    if alpha != 0 or compression != 1:
        raise ValueError("La texture n'est pas du BC1 opaque")
    pos, mips = 88, []
    for k in range(niveaux):
        if pos + 4 > len(data):
            raise ValueError("Niveau de mipmap tronqué")
        n = unpack_from("<I", data, pos)[0]
        attendu = ((max(1, w >> k) + 3) // 4) * ((max(1, h >> k) + 3) // 4) * 8
        if n != attendu or pos + 4 + n > len(data):
            raise ValueError("Longueur BC1 incohérente")
        mips.append(data[pos + 4:pos + 4 + n])
        pos += 4 + n
    if pos != len(data):
        raise ValueError("Données inattendues après les mipmaps")
    return {"fmt": fmt, "alpha": alpha, "w": w, "h": h, "profondeur": profondeur,
            "niveaux": niveaux, "rtype": rtype, "compression": compression, "mips": mips}


def _cible(parts, materiau):
    trouves = [t for t in textures.natives(parts) if t[3] == materiau]
    if len(trouves) != 1:
        raise ValueError(f"Matériau {materiau} : {len(trouves)} occurrence(s) au lieu d'une")
    return trouves[0]


def decoder_materiau(blob, materiau=MATERIAU_BETON):
    """Liste [(côté, (R, V, B)), ...] de tous les niveaux du matériau dans le TXD."""
    _, parts = textures.dictionary(bytes(blob))
    raster = lire_raster(_cible(parts, materiau)[4])
    return [(max(1, raster["w"] >> k), decoder_bc1(m, max(1, raster["w"] >> k), max(1, raster["h"] >> k)))
            for k, m in enumerate(raster["mips"])]


def _cle(nom_txd):
    return str(nom_txd).replace("\\", "/").rsplit("/", 1)[-1].lower()


def _ecarts(source, niveau):
    """(écart absolu moyen maximal, décalage de moyenne maximal) entre deux jeux de trois plans."""
    ecarts = [sum(abs(a - b) for a, b in zip(s, t)) / len(s) for s, t in zip(source, niveau)]
    decalage = [abs(sum(a - b for a, b in zip(s, t)) / len(s)) for s, t in zip(source, niveau)]
    return max(ecarts), max(decalage)


def _empreinte(donnees):
    return hashlib.sha256(donnees[88:]).hexdigest()


def ameliorer_txd(nom_txd, blob, exiger_empreinte=False):
    """Renvoie le TXD amélioré (bytes) ; lève ValueError si la cible ou la texture est inattendue.

    Béton htl_ext03.txd : 128 -> 256, 9 niveaux. Crépi od_hotels1.txd : 64 -> 128, 8 niveaux.
    Le niveau 1 (taille d'origine) reprend l'original BC1 octet pour octet. Avec
    `exiger_empreinte=True`, l'original doit avoir l'empreinte connue (ORIGINE_SHA256) quand
    elle existe pour le matériau.
    """
    cle = _cle(nom_txd)
    if cle not in MATERIAUX:
        raise ValueError(f"{nom_txd} n'est pas une cible de façade ({', '.join(TXD_CIBLES)})")
    materiau = MATERIAUX[cle]
    source_cote, cote, nb_niveaux = PROFILS[materiau]
    blob = bytes(blob)
    version, parts = textures.dictionary(blob)
    index, version_native, inner, _, data = _cible(parts, materiau)
    r = lire_raster(data)
    if (r["w"], r["h"], r["niveaux"]) != (source_cote, source_cote, 1):
        raise ValueError(f"{materiau} attendu en {source_cote}×{source_cote} à un niveau, "
                         f"trouvé {r['w']}×{r['h']} à {r['niveaux']} niveau(x) (déjà amélioré ?)")
    if exiger_empreinte and materiau in ORIGINE_SHA256 and _empreinte(data) != ORIGINE_SHA256[materiau]:
        raise ValueError(f"{materiau} : empreinte de l'original différente de celle attendue")
    source = decoder_bc1(r["mips"][0], source_cote, source_cote)
    plans, _ = ameliorer_pixels(*source, n=source_cote)
    niveaux = chaine_mipmaps(plans, cote)
    # Cohérence du niveau à la taille d'origine, puis copie de l'original bit pour bit.
    ecart, decalage = _ecarts(source, decoder_bc1(niveaux[1], source_cote, source_cote))
    if ecart > 4.0 or decalage > TOLERANCE_TEINTE:
        raise ValueError(f"Niveau {source_cote}×{source_cote} incohérent avec l'original "
                         f"(écart {ecart:.2f}, décalage {decalage:.2f})")
    niveaux[1] = r["mips"][0]
    fmt = (r["fmt"] | DRAPEAU_MIPMAP) & ~DRAPEAU_AUTO_MIPMAP
    en_tete = pack("<IIHHBBBB", fmt, r["alpha"], cote, cote, r["profondeur"],
                   len(niveaux), r["rtype"], r["compression"])
    nouveau = data[:72] + en_tete + b"".join(pack("<I", len(n)) + n for n in niveaux)
    inner[0] = (inner[0][0], inner[0][1], nouveau)
    parts[index] = (0x15, version_native, b"".join(textures.wrap(*item) for item in inner))
    resultat = textures.wrap(0x16, version, b"".join(textures.wrap(*item) for item in parts))
    verifier(blob, resultat, materiau)
    return resultat


# --------------------------------------------------------------------------- vérification et comparatif

def _couture(L, n):
    """Rapport (écart au raccord torique) / (écart moyen entre voisins) : ~1 si le tuilage est invisible."""
    raccord = sum(abs(L[y * n + n - 1] - L[y * n]) + abs(L[(n - 1) * n + y] - L[y]) for y in range(n)) / (2 * n)
    voisin = sum(abs(L[y * n + x + 1] - L[y * n + x]) + abs(L[(y + 1) * n + x] - L[y * n + x])
                 for y in range(n - 1) for x in range(n - 1)) / (2 * (n - 1) ** 2)
    return raccord / max(voisin, 1e-6)


def verifier(avant, apres, materiau=MATERIAU_BETON):
    """Contrôle avant/après ; renvoie un dictionnaire de mesures ou lève ValueError."""
    if materiau not in PROFILS:
        raise ValueError(f"Matériau inconnu : {materiau} ({', '.join(PROFILS)})")
    source_cote, cote, nb_niveaux = PROFILS[materiau]
    avant, apres = bytes(avant), bytes(apres)
    va, pa = textures.dictionary(avant)
    vb, pb = textures.dictionary(apres)
    if va != vb or [(k, v) for k, v, _ in pa] != [(k, v) for k, v, _ in pb]:
        raise ValueError("Structure du dictionnaire modifiée")
    na, nb = list(textures.natives(pa)), list(textures.natives(pb))
    if [t[3] for t in na] != [t[3] for t in nb]:
        raise ValueError("Noms ou ordre des textures modifiés")
    ia, ib = _cible(pa, materiau), _cible(pb, materiau)
    if ia[0] != ib[0]:
        raise ValueError("Position du matériau modifiée")
    for i, (a, b) in enumerate(zip(pa, pb)):
        if i != ia[0] and a != b:
            raise ValueError(f"Le contenu {i} du dictionnaire a changé")
    if [(k, v) for k, v, _ in ia[2]] != [(k, v) for k, v, _ in ib[2]] or ia[2][1:] != ib[2][1:] or ia[1] != ib[1]:
        raise ValueError("Chunks annexes de la texture modifiés")
    da, db = ia[4], ib[4]
    if da[:72] != db[:72]:
        raise ValueError("Nom, masque ou échantillonneur modifiés")
    ra, rb = lire_raster(da), lire_raster(db)
    if (ra["w"], ra["h"], ra["niveaux"]) != (source_cote, source_cote, 1):
        raise ValueError("Texture d'origine inattendue")
    if (rb["w"], rb["h"], rb["niveaux"]) != (cote, cote, nb_niveaux):
        raise ValueError(f"Dimensions ou nombre de mipmaps du résultat incorrects "
                         f"(attendu {cote}×{cote}, {nb_niveaux} niveaux)")
    if rb["mips"][1] != ra["mips"][0]:
        raise ValueError("Le niveau à la taille d'origine n'est pas l'original BC1 octet pour octet")
    if (rb["alpha"], rb["compression"], rb["profondeur"], rb["rtype"]) != (
            ra["alpha"], ra["compression"], ra["profondeur"], ra["rtype"]):
        raise ValueError("Alpha ou format modifiés")
    if not rb["fmt"] & DRAPEAU_MIPMAP or rb["fmt"] & DRAPEAU_AUTO_MIPMAP:
        raise ValueError("Drapeaux de mipmaps incorrects")
    source = decoder_bc1(ra["mips"][0], source_cote, source_cote)
    niveaux = [decoder_bc1(m, max(1, cote >> k), max(1, cote >> k)) for k, m in enumerate(rb["mips"])]
    # Lumière : la moyenne 2×2 du niveau 0 doit retrouver la source (tolérance de quantification BC1).
    ecart, decalage = _ecarts(source, [reduire(c, cote) for c in niveaux[0]])
    if ecart > TOLERANCE_LUMIERE or decalage > TOLERANCE_TEINTE:
        raise ValueError(f"Lumière ou teinte non préservées (écart {ecart:.2f}, décalage {decalage:.2f})")
    # Mipmaps : chaque niveau doit suivre la moyenne du précédent (le niveau 1 original compris).
    pire = 0.0
    for k in range(1, nb_niveaux):
        c = max(1, cote >> k)
        for fin, prec in zip(niveaux[k], [reduire(p, c * 2) for p in niveaux[k - 1]]):
            pire = max(pire, sum(abs(a - b) for a, b in zip(fin, prec)) / len(fin))
    if pire > TOLERANCE_MIPMAPS:
        raise ValueError(f"Chaîne de mipmaps incohérente (écart {pire:.2f})")
    # Détail et tuilage torique.
    Lb = luminance(*niveaux[0])
    simple = luminance(*[agrandir([float(v) for v in c], source_cote) for c in source])
    hf_apres, hf_simple = energie_hf(Lb, cote), energie_hf(simple, cote)
    couture_apres = _couture(Lb, cote)
    couture_avant = _couture(luminance(*source), source_cote)
    if couture_apres > couture_avant * 1.25 + 0.15:
        raise ValueError(f"Raccord de répétition dégradé ({couture_apres:.2f} contre {couture_avant:.2f})")
    attendue = ORIGINE_SHA256.get(materiau)
    return {"materiau": materiau, "mipmaps": nb_niveaux, "cote": cote, "cote_source": source_cote,
            "niveau_origine_identique": True,
            "empreinte_origine": None if attendue is None else _empreinte(da) == attendue,
            "ecart_lumiere_max": round(ecart, 3), "decalage_teinte_max": round(decalage, 3),
            "ecart_mipmaps_max": round(pire, 3),
            "detail_fin_avant": round(hf_simple, 3), "detail_fin_apres": round(hf_apres, 3),
            "couture_avant": round(couture_avant, 3), "couture_apres": round(couture_apres, 3),
            "autres_textures_identiques": True}


def ecrire_comparatif_ppm(avant, apres, chemin, materiau=MATERIAU_BETON):
    """Image locale PPM : avant agrandi ×2 à gauche, après à droite (2·cible × cible).

    Béton par défaut : 512×256 ; crépi : 256×128. À ne pas versionner (pixels du jeu).
    """
    if materiau not in PROFILS:
        raise ValueError(f"Matériau inconnu : {materiau} ({', '.join(PROFILS)})")
    source_cote, cote, _ = PROFILS[materiau]
    niveaux_avant = decoder_materiau(avant, materiau)
    if len(niveaux_avant) != 1 or niveaux_avant[0][0] != source_cote:
        raise ValueError(f"Le TXD « avant » n'est pas l'original {source_cote}×{source_cote} de {materiau}")
    R, G, B = niveaux_avant[0][1]
    haut = decoder_materiau(apres, materiau)[0]
    if haut[0] != cote:
        raise ValueError(f"Le TXD « après » n'est pas en {cote}×{cote}")
    haut = haut[1]
    lignes = bytearray()
    for y in range(cote):
        for x in range(cote):
            i = (y // 2) * source_cote + x // 2
            lignes += bytes((R[i], G[i], B[i]))
        for x in range(cote):
            i = y * cote + x
            lignes += bytes((int(round(haut[0][i])), int(round(haut[1][i])), int(round(haut[2][i]))))
    Path(chemin).write_bytes(f"P6\n{2 * cote} {cote}\n255\n".encode("ascii") + bytes(lignes))


USAGE = "Usage : python outils/facades.py AVANT.txd APRES.txd [COMPARATIF.ppm] [--materiau bow_abattoir_conc2|hotelpeach]"


def main(argv=None):
    """Mesures JSON avant/après ; image PPM locale facultative ; béton par défaut, `--materiau` pour le crépi."""
    args = sys.argv[1:] if argv is None else list(argv)
    materiau = MATERIAU_BETON
    if "--materiau" in args:
        i = args.index("--materiau")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        materiau = args[i + 1]
        del args[i:i + 2]
    if len(args) not in (2, 3):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        avant, apres = Path(args[0]).read_bytes(), Path(args[1]).read_bytes()
        mesures = verifier(avant, apres, materiau)
        if len(args) == 3:
            ecrire_comparatif_ppm(avant, apres, args[2], materiau)
    except (OSError, ValueError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    print(json.dumps(mesures, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
