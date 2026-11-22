"""Pose les façades d’Ocean Drive sur la voirie d’atelier et permet de les retirer."""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from struct import pack_into
from tempfile import gettempdir

from facades import TXD_CIBLES, ameliorer_txd
from maillage_rw import appliquer_relief
import relief_majestic
import ancrage_majestic
from marquise_majestic import prolonger_marquise
from enseigne_majestic import construire_enseigne
from palmier_majestic import EFFETS_PALMIER
import vitrages_majestic as vitrages
import textures


# Sortie de textures.construire pour l’édition commerciale PC 1.0 reconnue.
VOIRIE = {
    "gta3.img": "99c022fe8dae9f39f596057751fd3e803d194a8882d6f029d1f79793798aac8e",
    "gta3.dir": "701e78baac57058da11561401d7d5037d78b83105699345c902afd67e92140a3",
    "generic.txd": "d89128361e02a64059b0f283c4c562925dc1e7f6e303be82b48f3f14ef083a02",
}
# Profils générés depuis les originaux reconnus. Une migration n’accepte que ces paires.
HISTORIQUE = {
    "dcee8fb90dc427e258d9cb33c21fffe511278fd16bea5ec50d0ecc3f94cbaad8":
        "627ef9bfcce39862022a0202f71c813212c655cb5c89b946567818d6bd5fa4f0",
    "1f5f2faf16b0b45563ee37698fe7fda77305fc5cbd65c28294fd8b2348574581":
        "f384be9a3f3fb94b2e80e5cca07ceb3b59bfdf3ba9ae7cfb4fdd714d281cccc5",
    "a01dae9d405da1f0a51e071fc40908c311835610a9b362a4f1ae85b35aff96bd":
        "f384be9a3f3fb94b2e80e5cca07ceb3b59bfdf3ba9ae7cfb4fdd714d281cccc5",
    "cdd3ee56ffaa66aafa189d56a414b310b19c8026d7ae4f10e497e7f1edb69a3d":
        "2e543d03ff571b9e9fb1e7ba533c34fd0019a928ccc39c4658d4afc25883f746",
    "465f24831d27c649385e29022a12c0ee54b12af142afd43ccfa44187bc841dfc":
        "5a072849da21d300ad88164bc328954771ca4a2f6489fc74e57ad2907f8cc87e",
    "361d726a1315ec219cd2c3993dc24ea5c280df87effc481267c963cce3f2ea37":
        "8acf620c68b09c03aa325fca03e55de89185fa87dfd5701477ee19a8defb9bb0",
    "6ea086b9f735424124c2436bcf4d286092502965739ea6eeb8894d6aa08284e4":
        "a598dd9e25487a3e0addd77064dfa5034f4c6d742756e660edd6a0d63830f66e",
    "8bfaff1ab6c52a7c260925517d41ad24c13afd8d7c80cefd987ead105454490a":
        "d8b3d3cbbb5973a188f4f7e6271fe9d5e27f5ef080d0016a3883327a35499fbd",
}
TAILLE_VOIRIE = 327_487_488 + 641_024
MODELES = {"od_majestic2c_dy.dff": False, "od_majestic2c_nt.dff": True}
ENTREES = set(TXD_CIBLES) | set(MODELES) | set(EFFETS_PALMIER)


@contextmanager
def exclusivite(dossier):
    # Un verrou par copie. Le système le libère aussi si l’installation s’interrompt.
    cle = sha256(os.fsencode(os.path.normcase(str(dossier)))).hexdigest()
    with (Path(gettempdir()) / f"gta-vc-facades-{cle}.lck").open("a+b") as verrou:
        if os.name == "nt":
            import msvcrt
            verrou.seek(0)
            msvcrt.locking(verrou.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(verrou, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                verrou.seek(0)
                msvcrt.locking(verrou.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(verrou, fcntl.LOCK_UN)


def copier_voirie(image, sortie=None):
    controle = sha256()
    reste = TAILLE_VOIRIE
    with image.open("rb") as fichier:
        while reste:
            bloc = fichier.read(min(1024 * 1024, reste))
            if not bloc:
                raise ValueError("Archive de voirie tronquée")
            controle.update(bloc)
            if sortie is not None:
                sortie.write(bloc)
            reste -= len(bloc)
    if controle.hexdigest() != VOIRIE["gta3.img"]:
        raise ValueError("Une autre modification touche les secteurs de voirie")
    return controle


def construire_architecture(surface, nuit=False):
    panneaux = relief_majestic._preparer(surface)["panneaux"]["hotelwindow1"]
    avancees = ancrage_majestic.avancees(surface, panneaux)
    volumes = []
    for element in relief_majestic.construire_elements(surface, nuit=nuit):
        nom = element["nom"]
        if nom.startswith("fenetre:"):
            indice = int(nom.split(":")[1])
            volumes.extend(ancrage_majestic.sortir_encadrement(face, panneaux[indice], avancees[indice])
                           for face in element["triangles"])
        elif not nom.startswith("corniche:"):
            volumes.extend(element["triangles"])
    volumes.extend(ancrage_majestic.corniches_ancrees(surface, nuit=nuit))
    volumes.extend(prolonger_marquise(surface, nuit=nuit))
    volumes.extend(construire_enseigne(nuit=nuit))
    # Le modèle combine le prééclairage avec l’éclairage extérieur du moteur.
    # Conserver de la marge pour le métal et l’émail sous le soleil de 14 heures.
    coefficients = (.90, .89, .86) if nuit else (.68, .66, .67)
    return [tuple((*v[:3], *(round(c*k) for c, k in zip(v[3:], coefficients))) for v in face)
            for face in volumes]


def produire_secteurs(source, index_original):
    secteurs = bytearray()
    pointeurs = {}
    noms_trouves = set()
    with (source / "gta3.img").open("rb") as image:
        for i, (debut, nombre, nom_brut) in enumerate(textures.ENTRY.iter_unpack(index_original)):
            nom = textures.name(nom_brut)
            if nom not in ENTREES:
                continue
            image.seek(debut * textures.SECTOR)
            entree = image.read(nombre * textures.SECTOR)
            if len(entree) != nombre * textures.SECTOR:
                raise ValueError(f"Entrée originale tronquée : {nom}")
            if nom in MODELES:
                nuit = MODELES[nom]
                depli = vitrages.preparer_uv(entree)
                relief = appliquer_relief(depli, nuit=nuit, constructeur=construire_architecture)
                ameliore = vitrages.nommer_vitrages(relief, nuit)
            elif nom in EFFETS_PALMIER:
                ameliore = EFFETS_PALMIER[nom](entree)
            else:
                ameliore = ameliorer_txd(nom, entree, exiger_empreinte=True)
                if nom == "od_hotels1.txd":
                    ameliore = vitrages.ajouter_vitrages(ameliore)
            compte = (len(ameliore) + textures.SECTOR - 1) // textures.SECTOR
            pointeurs[i] = ((TAILLE_VOIRIE + len(secteurs)) // textures.SECTOR, compte)
            secteurs.extend(ameliore)
            secteurs.extend(bytes(compte * textures.SECTOR - len(ameliore)))
            noms_trouves.add(nom)
    if noms_trouves != ENTREES or len(pointeurs) != len(ENTREES):
        raise ValueError("Des entrées de façade sont absentes ou dupliquées")
    return secteurs, pointeurs


def composer(source, destination, actives):
    existant = {
        nom: textures.digest(destination / nom).hexdigest()
        for nom in VOIRIE if (destination / nom).is_file()
    }
    if all(somme in (VOIRIE[nom], textures.RETAIL[nom]) for nom, somme in existant.items()):
        textures.construire(source.parent, destination / "generic.txd")
        if not actives:
            return {"facades": False, "secteurs_facades": 0, "sha256": VOIRIE.copy()}
    else:
        if existant.get("generic.txd") != VOIRIE["generic.txd"]:
            raise ValueError("Le dictionnaire de voirie diffère de la version d’atelier")
        for nom in ("gta3.img", "generic.txd"):
            if textures.digest(source / nom).hexdigest() != textures.RETAIL[nom]:
                raise ValueError(f"Version de l’original non reconnue : {nom}")

    ancien_index = HISTORIQUE.get(existant.get("gta3.img"))
    migrer = ancien_index is not None and existant.get("gta3.dir") in (ancien_index, VOIRIE["gta3.dir"])
    index_original = (source / "gta3.dir").read_bytes()
    if sha256(index_original).hexdigest() != textures.RETAIL["gta3.dir"]:
        raise ValueError("Index de la copie originale incompatible")
    supplement, pointeurs = produire_secteurs(source, index_original)
    image = destination / "gta3.img"
    repertoire = destination / "gta3.dir"
    courant = repertoire.read_bytes()
    index_voirie = bytearray(courant)
    for i in pointeurs:
        position = i * textures.ENTRY.size
        index_voirie[position:position + 8] = index_original[position:position + 8]
    if sha256(index_voirie).hexdigest() != VOIRIE["gta3.dir"]:
        raise ValueError("Une autre modification existe dans l’index du jeu")

    index_facades = bytearray(index_voirie)
    for i, (secteur, quantite) in pointeurs.items():
        pack_into("<II", index_facades, i * textures.ENTRY.size, secteur, quantite)
    if courant != index_voirie and courant != index_facades and not migrer:
        raise ValueError("Une autre modification utilise les entrées des façades")

    entier = copier_voirie(image)
    entier.update(supplement)
    with image.open("rb") as fichier:
        fichier.seek(TAILLE_VOIRIE)
        actuel = fichier.read(len(supplement) + 1)
    if actuel and actuel != supplement and not migrer:
        raise ValueError("Des secteurs étrangers suivent l’archive de voirie")
    # Un jeu d’éléments graphiques connu peut aussi être la configuration
    # demandée. Dans ce cas, ne réécrire ni l’archive ni les dates des fichiers.
    if actuel == supplement:
        migrer = False
    cible_img = entier.hexdigest() if actives else VOIRIE["gta3.img"]
    cible_dir = index_facades if actives else index_voirie

    def ecrire_image(sortie):
        copier_voirie(image, sortie)
        if actives:
            sortie.write(supplement)

    def basculer_index(cible):
        nonlocal courant
        if courant != cible:
            textures.replace(repertoire, sha256(cible).hexdigest(), lambda f: f.write(cible))
            courant = cible

    # Au retrait ou pendant une migration, le vieil index doit cesser de
    # référencer les anciens ajouts avant le remplacement de ces secteurs.
    if not actives or migrer:
        basculer_index(index_voirie)
    if migrer or bool(actuel) != bool(actives):
        textures.replace(image, cible_img, ecrire_image)
    if actives:
        basculer_index(index_facades)
    return {
        "facades": bool(actives),
        "secteurs_facades": len(supplement) // textures.SECTOR if actives else 0,
        "sha256": {
            "gta3.img": cible_img,
            "gta3.dir": sha256(cible_dir).hexdigest(),
            "generic.txd": VOIRIE["generic.txd"],
        },
    }


def installer(origine, jeu, actives=True):
    source = (Path(origine) / "models").resolve()
    destination = (Path(jeu) / "models").resolve()
    if destination == source:
        raise ValueError("La copie du jeu doit être distincte de l’original")
    destination.mkdir(parents=True, exist_ok=True)
    with exclusivite(destination):
        return composer(source, destination, actives)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origine", type=Path)
    parser.add_argument("jeu", type=Path)
    parser.add_argument("--voirie-seule", action="store_true", help="Retirer les façades et garder la voirie")
    args = parser.parse_args()
    print(json.dumps(installer(args.origine, args.jeu, not args.voirie_seule), indent=2))
