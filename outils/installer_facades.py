"""Installe les modèles de la ville et ses voitures sur la copie personnelle de Vice City."""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from struct import pack_into
from tempfile import TemporaryDirectory, gettempdir

from facades import TXD_CIBLES, ameliorer_txd
from maillage_rw import appliquer_relief, lire_surface
import relief_majestic
import ancrage_majestic
from marquise_majestic import prolonger_marquise
from enseigne_majestic import construire_enseigne
from palmier_majestic import EFFETS_PALMIER
import matieres_volume as matieres
import volume_rw
from chambres_majestic import construire_chambres
from hall_majestic import construire_hall
from collision_hall_majestic import EFFETS_SEUIL
from affiche_ocean_drive import EFFETS_AFFICHE
from voitures_1986 import EFFETS_VOITURES
import facades_ville
import textures


# Sortie de textures.construire pour l’édition commerciale PC 1.0 reconnue.
VOIRIE = {
    "gta3.img": "99c022fe8dae9f39f596057751fd3e803d194a8882d6f029d1f79793798aac8e",
    "gta3.dir": "701e78baac57058da11561401d7d5037d78b83105699345c902afd67e92140a3",
    "generic.txd": "d89128361e02a64059b0f283c4c562925dc1e7f6e303be82b48f3f14ef083a02",
}
# Profils générés depuis les originaux reconnus. Une migration n’accepte que ces paires.
HISTORIQUE = {
    "37d9ef156ee715a114b564d5cf5dc55e8642d2021ebb1af56f7d76d815602c56":
        "1b794387a1ac5e7970845da9a7eaad442de48bf3bcb077d436248c382ab0093a",
    "e53fcfc1ecab82134bec2583e6d48e0f78327024f91c5e5b825077729ccd8ef8":
        "dd357d8e99ff72665355b67bf4c589243879ecd1bcde08e13a5ed93dad620bdf",
    "459214e44fb227c76856b8fddbe7c7724efda1d5c244f955cb13ab9a6749576a":
        "bbfdfcfaaa9c94421afdd4e73a72bcd462db2ace9fe31df13cf33b6dd6959245",
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
# Empreintes de la version contiguë validée dans le moteur (6 043 entrées).
VILLE = {
    "gta3.img": "e2048a5a749369969a56bc4e97f82e07c8c7832dded773293e2c7e449ed262f7",
    "gta3.dir": "40b08936699eb209dedae8799a58e26a33eb3251181f5fff2ae118265fd8f585",
    "generic.txd": VOIRIE["generic.txd"],
}
SECTEURS_FACADES = 27_301
TRANSACTION = ".radio-ocean-archives-en-cours"
MANIFESTE = "publication.json"
TAILLE_VOIRIE = 327_487_488 + 641_024
MODELES = {"od_majestic2c_dy.dff": False, "od_majestic2c_nt.dff": True}
EFFETS_MODELES = {**EFFETS_PALMIER, **EFFETS_SEUIL, **EFFETS_AFFICHE, **EFFETS_VOITURES}
ENTREES = set(TXD_CIBLES) | set(MODELES) | set(EFFETS_MODELES)


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


def construire_hotel(entree, nuit):
    surface = lire_surface(entree)
    panneaux = relief_majestic._preparer(surface)["panneaux"]
    ouvert = volume_rw.ouvrir_baies(entree, panneaux["hotelwindow1"])
    # Les cadres suivent les 33 ouvertures d'origine même après leur découpe.
    def architecture(_, nuit):
        return construire_architecture(surface, nuit)
    enveloppe = appliquer_relief(ouvert, nuit=nuit, constructeur=architecture)
    meubles = list(construire_hall(surface, nuit=nuit, porte_ouverte=True))
    meubles.extend(construire_chambres(surface, nuit=nuit))
    return matieres.nommer_email(volume_rw.meubler(enveloppe, meubles))


def produire_secteurs(source, index_original, plans_ville=None):
    if plans_ville is None:
        # Les entrées proviennent de la copie commerciale vérifiée. Chaque modèle est
        # construit une seule fois, au moment de son écriture dans les nouveaux secteurs.
        plans_ville = facades_ville.inventorier(source.parent, signer=False)["plans"]
    # L’affiche de l’aéroport et les modèles déjà travaillés conservent leur géométrie dédiée.
    cibles = ENTREES | set(plans_ville)
    secteurs = bytearray()
    pointeurs = {}
    noms_trouves = set()
    with (source / "gta3.img").open("rb") as image:
        for i, (debut, nombre, nom_brut) in enumerate(textures.ENTRY.iter_unpack(index_original)):
            nom = textures.name(nom_brut)
            if nom not in cibles:
                continue
            image.seek(debut * textures.SECTOR)
            entree = image.read(nombre * textures.SECTOR)
            if len(entree) != nombre * textures.SECTOR:
                raise ValueError(f"Entrée originale tronquée : {nom}")
            if nom in MODELES:
                nuit = MODELES[nom]
                ameliore = construire_hotel(entree, nuit)
            elif nom in EFFETS_MODELES:
                ameliore = EFFETS_MODELES[nom](entree)
            elif nom in TXD_CIBLES:
                ameliore = ameliorer_txd(nom, entree, exiger_empreinte=True)
                if nom == "od_hotels1.txd":
                    ameliore = matieres.ajouter_matieres(ameliore)
            else:
                ameliore = facades_ville.transformer(entree, plans_ville[nom])
            compte = (len(ameliore) + textures.SECTOR - 1) // textures.SECTOR
            pointeurs[i] = ((TAILLE_VOIRIE + len(secteurs)) // textures.SECTOR, compte)
            secteurs.extend(ameliore)
            secteurs.extend(bytes(compte * textures.SECTOR - len(ameliore)))
            noms_trouves.add(nom)
    if noms_trouves != cibles or len(pointeurs) != len(cibles):
        raise ValueError("Des entrées de façade sont absentes ou dupliquées")
    return secteurs, pointeurs


def etat(dossier):
    sommes = {}
    for nom in VOIRIE:
        fichier = dossier / nom
        if fichier.is_symlink() or (fichier.exists() and not fichier.is_file()):
            raise ValueError(f"Une entrée étrangère occupe {nom}")
        sommes[nom] = textures.digest(fichier).hexdigest() if fichier.is_file() else None
    return sommes


def reconnaitre(sommes):
    # La voirie historique est additive : les combinaisons source/voirie peuvent
    # aussi résulter d'une première installation interrompue après un des trois fichiers.
    if all(sommes[n] in (None, VOIRIE[n], textures.RETAIL[n]) for n in VOIRIE):
        return
    if sommes == VILLE:
        return
    ancien_index = HISTORIQUE.get(sommes["gta3.img"])
    if (sommes["generic.txd"] == VOIRIE["generic.txd"] and ancien_index is not None
            and sommes["gta3.dir"] in (ancien_index, VOIRIE["gta3.dir"])):
        return
    raise ValueError("Des fichiers ou secteurs étrangers sont présents dans les archives du jeu")


def compacter(voirie, prets, supplement, pointeurs):
    """Écrit chaque entrée à la suite de celle qui la précède dans le DIR commercial."""
    index = bytearray((voirie / "gta3.dir").read_bytes())
    nouveaux = memoryview(supplement)
    with (voirie / "gta3.img").open("rb") as base, (prets / "gta3.img").open("wb") as image:
        for i, (ancien, nombre, _) in enumerate(textures.ENTRY.iter_unpack(bytes(index))):
            if i in pointeurs:
                ancien, nombre = pointeurs[i]
                pos = ancien * textures.SECTOR - TAILLE_VOIRIE
                if pos < 0:
                    raise ValueError("Secteur de façade invalide")
                contenu = nouveaux[pos:pos + nombre * textures.SECTOR]
            else:
                base.seek(ancien * textures.SECTOR)
                contenu = base.read(nombre * textures.SECTOR)
            if len(contenu) != nombre * textures.SECTOR:
                raise ValueError("Entrée incomplète lors du montage de la ville")
            pack_into("<II", index, i * textures.ENTRY.size, image.tell() // textures.SECTOR, nombre)
            image.write(contenu)
    (prets / "gta3.dir").write_bytes(index)
    os.replace(voirie / "generic.txd", prets / "generic.txd")


def terminer_publication(destination):
    """Reprend la publication avant tout lancement, même si l'IMG a déjà été remplacée."""
    journal = destination / TRANSACTION
    if not journal.exists():
        return False
    if journal.is_symlink() or not (journal / MANIFESTE).is_file():
        raise ValueError("Le journal de publication des archives est illisible")
    if set(p.name for p in journal.iterdir()) - {*VOIRIE, MANIFESTE}:
        raise ValueError("Des fichiers étrangers sont présents dans le journal d’installation")
    transaction = json.loads((journal / MANIFESTE).read_text(encoding="utf-8"))
    avant, cible = transaction["avant"], transaction["cible"]
    if set(avant) != set(VOIRIE) or cible not in (VILLE, VOIRIE):
        raise ValueError("Le journal de publication des archives est incompatible")
    reconnaitre(avant)
    courant = etat(destination)
    # Contrôler toutes les paires et tous les fichiers préparés avant le premier échange.
    for nom, voulu in cible.items():
        prepare = journal / nom
        if courant[nom] not in (avant[nom], voulu):
            raise ValueError(f"Une modification étrangère est apparue dans {nom}")
        if prepare.exists():
            if prepare.is_symlink() or textures.digest(prepare).hexdigest() != voulu:
                raise ValueError(f"La copie préparée de {nom} a changé")
        elif courant[nom] != voulu:
            raise OSError(f"La copie préparée de {nom} est manquante")
    for nom, voulu in cible.items():
        if courant[nom] != voulu:
            os.replace(journal / nom, destination / nom)
    # Retirer le journal d'un seul coup : une coupure lors du nettoyage ne laisse
    # jamais un journal actif sans son manifeste.
    with TemporaryDirectory(prefix=".radio-ocean-applique-", dir=destination) as termine:
        os.replace(journal, Path(termine) / "publie")
    return True


def recuperer(jeu):
    destination = (Path(jeu) / "models").resolve()
    with exclusivite(destination):
        return terminer_publication(destination)


def composer(source, destination, actives):
    terminer_publication(destination)
    avant = etat(destination)
    reconnaitre(avant)
    cible = VILLE if actives else VOIRIE
    if avant != cible:
        # La préparation se fait sur le volume de destination. Jusqu'à la publication
        # du journal, aucun fichier utilisé par le jeu ne change.
        with TemporaryDirectory(prefix=".radio-ocean-preparation-", dir=destination) as temporaire:
            travail = Path(temporaire)
            voirie = travail / "voirie"
            textures.construire(source.parent, voirie / "generic.txd")
            prets = voirie
            if actives:
                index = (source / "gta3.dir").read_bytes()
                supplement, pointeurs = produire_secteurs(source, index)
                if len(supplement) != SECTEURS_FACADES * textures.SECTOR:
                    raise ValueError("La taille des modèles produits diffère de la version attendue")
                prets = travail / "ville"
                prets.mkdir()
                compacter(voirie, prets, supplement, pointeurs)
            if etat(prets) != cible:
                raise ValueError("Les empreintes des archives préparées diffèrent de la version attendue")
            for nom in cible:
                with (prets / nom).open("r+b") as f:
                    os.fsync(f.fileno())
            with (prets / MANIFESTE).open("w", encoding="utf-8") as f:
                json.dump({"avant": avant, "cible": cible}, f)
                f.flush()
                os.fsync(f.fileno())
            os.rename(prets, destination / TRANSACTION)
        terminer_publication(destination)
    return {"facades": bool(actives), "secteurs_facades": SECTEURS_FACADES if actives else 0,
            "sha256": cible.copy()}


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
