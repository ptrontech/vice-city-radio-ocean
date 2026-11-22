"""Rend localement les deux DFF du Majestic avec le même éclairage d'étude.

Usage : python outils/apercu_majestic.py DOSSIER_ORIGINAL DOSSIER_ATELIER COMPARATIF.png
Dépendances du comparatif uniquement : NumPy et Pillow. Aucun contenu du jeu n'est inclus.
"""
import argparse
from pathlib import Path
from struct import unpack_from

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import textures

SOLEIL = np.array((.66, -.23, .72))
SOLEIL /= np.linalg.norm(SOLEIL)


def fichier(dossier, nom):
    with (dossier / "gta3.img").open("rb") as image:
        for secteur, taille, entree in textures.ENTRY.iter_unpack((dossier / "gta3.dir").read_bytes()):
            if textures.name(entree) == nom:
                image.seek(secteur * textures.SECTOR)
                return image.read(taille * textures.SECTOR)
    raise ValueError(f"Entrée IMG absente : {nom}")


def enfants(bloc, sorte):
    return [d for t, _, d in textures.chunks(bloc) if t == sorte]


def lire_textures(bloc):
    table = {}
    for _, _, _, nom, corps in textures.natives(textures.dictionary(bloc)[1]):
        w, h = unpack_from("<HH", corps, 80)
        codec = {1: 1, 3: 2, 5: 3}.get(corps[87])
        if codec:
            longueur = unpack_from("<I", corps, 88)[0]
            image = Image.frombytes("RGBA", (w, h), corps[92:92 + longueur], "bcn", codec)
            table[nom] = np.asarray(image, dtype="float32")
    return table


def lire_modele(blob):
    racine = blob[12:12 + unpack_from("<I", blob, 4)[0]]
    liste = enfants(enfants(racine, 14)[0], 1)[0]
    cadres = []
    for i in range(unpack_from("<I", liste)[0]):
        val = unpack_from("<12fiI", liste, 4 + i * 56)
        mat = np.array(val[:9]).reshape((3, 3))
        pos = np.array(val[9:12])
        if val[12] >= 0:
            mat_parent, off = cadres[val[12]]
            mat, pos = mat @ mat_parent, pos @ mat_parent + off
        cadres.append((mat, pos))
    geometries = []
    for geo in enfants(enfants(racine, 26)[0], 15):
        st = enfants(geo, 1)[0]
        flags, nf, nv, _ = unpack_from("<4I", st)
        nb_uv = flags >> 16 & 255 or (2 if flags & 128 else int(bool(flags & 4)))
        off = 16
        couleurs = np.full((nv, 4), 255)
        if flags & 8:
            couleurs = np.frombuffer(st, dtype=np.uint8, count=nv * 4, offset=off).reshape(-1, 4)
            off += nv * 4
        uv = np.frombuffer(st, dtype="<f4", count=nv * 2, offset=off).reshape(-1, 2) if nb_uv else np.zeros((nv, 2))
        off += nb_uv * nv * 8
        faces = np.frombuffer(st, dtype="<u2", count=nf * 4, offset=off).reshape(-1, 4)
        off += nf * 8 + 24
        xyz = np.frombuffer(st, dtype="<f4", count=nv * 3, offset=off).reshape(-1, 3)
        materiaux = []
        for materiau in enfants(enfants(geo, 8)[0], 7):
            tex = enfants(materiau, 6)
            nom = textures.name(enfants(tex[0], 2)[0]) if tex else ""
            rgba = np.frombuffer(enfants(materiau, 1)[0], dtype=np.uint8, count=4, offset=4) / 255.
            materiaux.append((nom, rgba))
        geometries.append((xyz, uv, couleurs, faces, materiaux))
    objets = []
    for atom in enfants(racine, 20):
        cadre, geo = unpack_from("<II", enfants(atom, 1)[0])
        mat, pos = cadres[cadre]
        xyz, uv, couleurs, faces, noms = geometries[geo]
        objets.append((xyz @ mat + pos, uv, couleurs, faces, noms))
    return objets


def normaliser(v):
    return v / np.linalg.norm(v)


def echantillon(img, uv):
    h, w = img.shape[:2]
    x, y = uv[:, 0] * w - .5, uv[:, 1] * h - .5
    i, j = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - i)[:, None], (y - j)[:, None]
    dessus = (1 - fx) * img[j % h, i % w] + fx * img[j % h, (i + 1) % w]
    dessous = (1 - fx) * img[(j + 1) % h, i % w] + fx * img[(j + 1) % h, (i + 1) % w]
    return dessus * (1 - fy) + dessous * fy


def ecran_triangle(p, largeur, hauteur):
    lo = np.maximum(0, np.floor(p.min(0)).astype(int))
    hi = np.minimum([largeur - 1, hauteur - 1], np.ceil(p.max(0)).astype(int))
    if np.any(lo > hi):
        return None
    a, b = p[1] - p[0], p[2] - p[0]
    det = a[0] * b[1] - a[1] * b[0]
    if abs(det) < 1e-7:
        return None
    gy, gx = np.mgrid[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
    x, y = gx + .5 - p[0, 0], gy + .5 - p[0, 1]
    v = (x * b[1] - y * b[0]) / det
    w = (a[0] * y - a[1] * x) / det
    u = 1 - v - w
    dedans = (u >= 0) & (v >= 0) & (w >= 0)
    if not np.any(dedans):
        return None
    return gy[dedans], gx[dedans], np.column_stack((u[dedans], v[dedans], w[dedans]))


class Ombres:
    def __init__(self, objets, resolution=1152):
        axe = normaliser(np.cross([0, 0, 1], SOLEIL))
        self.base = np.array((axe, np.cross(SOLEIL, axe), SOLEIL)).T
        ensemble = np.concatenate([xyz @ self.base for xyz, *_ in objets])
        self.min = ensemble[:, :2].min(0) - 2.8
        self.echelle = (resolution - 1) / (ensemble[:, :2].max(0) + 2.8 - self.min)
        self.carte = np.full((resolution, resolution), -np.inf)
        for xyz, _, _, faces, _ in objets:
            lum = xyz @ self.base
            p = (lum[:, :2] - self.min) * self.echelle
            for b, a, _, c in faces:
                ind = [a, b, c]
                projection = ecran_triangle(p[ind], resolution, resolution)
                if projection is None:
                    continue
                y, x, bary = projection
                self.carte[y, x] = np.maximum(self.carte[y, x], bary @ lum[ind, 2])

    def visibilite(self, xyz, normale=(0., 0., 1.)):
        lum = xyz @ self.base
        pixel = (lum[:, :2] - self.min) * self.echelle
        coord = np.floor(pixel).astype(int)
        resultat = np.ones(len(lum))
        n = self.carte.shape[0]
        dedans = np.all((coord >= 2) & (coord < n - 2), axis=1)
        if np.any(dedans):
            x, y = coord[dedans].T
            hauteur = lum[dedans, 2] + .025
            n_lumiere = np.asarray(normale) @ self.base
            pente = -n_lumiere[:2] / n_lumiere[2] if abs(n_lumiere[2]) > .04 else np.zeros(2)
            pente = np.clip(pente, -8, 8) / self.echelle
            # Chaque échantillon PCF est pris au centre d'un pixel voisin.
            # Reprojeter le plan récepteur à ce point évite qu’il s’ombrage lui-même.
            subpixel = coord[dedans] + .5 - pixel[dedans]
            base = hauteur + subpixel @ pente
            resultat[dedans] = sum((base + i*pente[0] + j*pente[1] >= self.carte[y+j, x+i]).astype(float)
                                   for i, j in ((0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))) / 5.
        return resultat


def rendre(objets, rasters, ombres, dimensions, oeil, cible, angle):
    largeur, hauteur = dimensions
    oeil, cible = np.array(oeil), np.array(cible)
    avant = normaliser(cible - oeil)
    droit = normaliser(np.cross(avant, [0, 0, 1]))
    haut = np.cross(droit, avant)
    focale = hauteur / (2 * np.tan(np.radians(angle / 2)))
    gy, gx = np.mgrid[:hauteur, :largeur]
    rayons = avant + ((gx + .5 - largeur / 2) / focale)[:, :, None] * droit - ((gy + .5 - hauteur / 2) / focale)[:, :, None] * haut
    plan_sol = min(xyz[:, 2].min() for xyz, *_ in objets) - .03
    sol = np.divide(plan_sol - oeil[2], rayons[:, :, 2], out=np.full((hauteur, largeur), np.inf),
                    where=rayons[:, :, 2] < -.0001)
    visible = (sol > 0) & (sol < 180)
    f = gy[:, :, None] / hauteur
    couleur = np.asarray([204, 222, 225]) * (1 - f) + np.asarray([240, 234, 218]) * f
    if np.any(visible):
        monde_sol = oeil + sol[visible, None] * rayons[visible]
        lumiere_sol = .65 + .35 * ombres.visibilite(monde_sol)
        nuance_sol = np.asarray([211, 205, 192]) * lumiere_sol[:, None]
        brume = np.clip((sol[visible] - 58) / 110, 0, 1)
        couleur[visible] = nuance_sol * (1 - brume[:, None]) + couleur[visible] * brume[:, None]
    zbuffer = np.where(visible, sol, np.inf)
    unie = np.ones((1, 1, 4)) * 255
    for xyz, uv, couleurs, faces, mats in objets:
        rel = xyz - oeil
        z = rel @ avant
        ecran = np.column_stack((largeur / 2 + focale * (rel @ droit) / z, hauteur / 2 - focale * (rel @ haut) / z))
        for b, a, index, c in faces:
            ind = [a, b, c]
            if np.min(z[ind]) < .2:
                continue
            projection = ecran_triangle(ecran[ind], largeur, hauteur)
            if projection is None:
                continue
            y, x, bary = projection
            poids = bary / z[ind]
            profondeur = 1 / poids.sum(1)
            ok = profondeur < zbuffer[y, x]
            if not np.any(ok):
                continue
            poids = poids[ok] * profondeur[ok, None]
            y, x = y[ok], x[ok]
            nom, mat = mats[index]
            if nom and nom not in rasters:
                raise ValueError(f"Texture de bâtiment manquante : {nom}")
            teinte = echantillon(rasters.get(nom, unie), poids @ uv[ind]) * mat
            prelight = poids @ couleurs[ind] / 255
            normal = np.cross(xyz[b] - xyz[a], xyz[c] - xyz[a])
            # Orienter la lumière des matériaux à double face vers le côté observé.
            if normal @ (oeil - xyz[a]) < 0:
                normal *= -1
            incidence = max(0., normaliser(normal) @ SOLEIL)
            monde = poids @ xyz[ind]
            soleil = ombres.visibilite(monde, normaliser(normal)) if incidence > .001 else np.zeros(len(monde))
            eclairement = .61 + .39 * incidence * soleil
            teinte[:, :3] *= ((.28 + .72 * prelight[:, :3]) * eclairement[:, None])
            solide = teinte[:, 3] * prelight[:, 3] > 110
            couleur[y[solide], x[solide]] = teinte[solide, :3]
            zbuffer[y[solide], x[solide]] = profondeur[ok][solide]
    return Image.fromarray(np.round(couleur).clip(0, 255).astype(np.uint8))


def police(gras, taille):
    for nom in (("segoeuib.ttf" if gras else "segoeui.ttf"), ("DejaVuSans-Bold.ttf" if gras else "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            continue
    return ImageFont.load_default()


def comparer(origine, jeu, sortie, nuit=False):
    variante = "nt" if nuit else "dy"
    original, travaille = Path(origine) / "models", Path(jeu) / "models"
    planche = Image.new("RGB", (1428, 1075), "#f7f5ee")
    dessin = ImageDraw.Draw(planche)
    texte = lambda xy, t, taille, gras=False: dessin.text(xy, t, font=police(gras, taille), fill="#233a3c")
    texte((28, 14), "Le Majestic sur Ocean Drive", 37, True)
    texte((30, 72), f"Modèle du jeu de {'nuit' if nuit else 'jour'}   /   Même caméra et même soleil de studio pour chaque paire", 18)
    for x, dossier, titre in [(28, original, "Original PC"), (722, travaille, "Façade en relief")]:
        texte((x, 115), titre, 22, True)
        objets = lire_modele(fichier(dossier, f"od_majestic2c_{variante}.dff"))
        rasters = lire_textures(fichier(dossier, "od_hotels1.txd"))
        if nuit:
            # Les douze dictionnaires locaux qui contiennent « black » ont la même
            # image opaque 32 × 32. Le modèle nocturne la référence sur quatre faces.
            rasters["black"] = lire_textures(fichier(dossier, "hotelroomint.txd"))["black"]
        ombres = Ombres(objets)
        for y, size, oeil, cible, fov in [
            (154, (677, 453), (46., 36., -.3), (0., 0., -.4), 38.),
            (665, (677, 337), (24.5, 22.5, -12.65), (5., 6., -7.1), 46.),
        ]:
            # Suréchantillonnage identique dans les deux colonnes pour lisser les nez des corniches.
            facteur = 1.4
            grand = (int(size[0] * facteur), int(size[1] * facteur))
            img = rendre(objets, rasters, ombres, grand, oeil, cible, fov)
            planche.paste(img.resize(size, Image.Resampling.LANCZOS), (x, y))
    texte((29, 619), "À hauteur de rue", 23, True)
    texte((29, 1024), "Rendu local du maillage et des matériaux de Vice City. Les ombres de cette planche proviennent de la géométrie.", 18)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    planche.save(sortie)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origine", type=Path)
    parser.add_argument("jeu", type=Path)
    parser.add_argument("sortie", type=Path)
    parser.add_argument("--nuit", action="store_true")
    args = parser.parse_args()
    comparer(args.origine, args.jeu, args.sortie, args.nuit)
