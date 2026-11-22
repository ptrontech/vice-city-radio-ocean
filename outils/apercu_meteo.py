"""Aperçu local des couleurs de ciel et de mer d'Ocean Drive, sans lancer le jeu.

Usage (PowerShell) :
    python outils/apercu_meteo.py PALETTE_BASE PALETTE_ORAGE APERCU.svg

L'outil lit deux textes timecyc.dat locaux (7 sections de 24 heures, 52 champs par heure),
échantillonne la section 2 (pluie) à 2 h, 6 h et 23 h, ainsi que l’ouragan du jeu classique dont le bloc 5
porte lui aussi le libellé RAINY dans la palette d’origine, puis écrit un seul SVG autonome : pour chaque temps, un
schéma « avant » (base) et un schéma « après » (orage) avec leurs couleurs chiffrées.

C'est un aperçu des palettes, pas une capture du jeu : aucun éclairage, nuage, brouillard,
reflet ni texture n'est rendu. Le SVG ne contient que des couleurs déduites des fichiers,
jamais d'extrait ni de texture du jeu. Bibliothèque standard uniquement ; sortie déterministe.
"""
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

NB_SECTIONS = 7
NB_HEURES = 24
NB_COLONNES = 52
TAILLE_MAX = 2_000_000          # un timecyc.dat réel est bien plus petit

SECTION_PLUIE = 2
SECTION_OURAGAN = 5
HEURES = (2, 6, 23)
# L’index 5 est Hurricane dans Vice City. Le fichier PC d’origine y répète RAINY.
# Les palettes modifiées peuvent donner explicitement un nom d’orage.
_MOTS_ORAGE = re.compile(r"STORM|THUNDER|LIGHTNING|HURRICANE|ORAGE|TEMP[EÊ]TE", re.IGNORECASE)

# Colonnes (indices à partir de 0) utilisées par l'aperçu.
CIEL_HAUT, HORIZON, MER, OPACITE_MER = 15, 18, 48, 51
MELANGE_MER_HORIZON = 0.5       # choix du schéma : mer proche de l'horizon = 50 % horizon

_DEBUT_NOMBRE = re.compile(r"[+-]?\.?\d")

# Mise en page (pixels).
LARGEUR, MARGE, ECART = 960, 24, 32
LARGEUR_PANNEAU = (LARGEUR - 2 * MARGE - ECART) // 2
H_CIEL, H_MER = 90, 60
HAUT_ENTETE, HAUT_RANGEE, LIGNE_LEGENDE = 84, 290, 20
FOND, ENCRE, TRAIT = "#f5f5f2", "#1a1a1a", "#555555"


# --------------------------------------------------------------------------- lecture

def _nom_section(ligne):
    nom = " ".join("".join(c for c in ligne.strip("/ \t") if c.isprintable()).split())
    return nom[:40]


def lire_palette(texte, etiquette="palette"):
    """Renvoie (noms des 7 sections, données[section][heure] = 52 flottants) ou lève ValueError."""
    if not isinstance(texte, str):
        raise TypeError("La palette doit être un texte")
    noms, donnees = [], []
    for numero, ligne in enumerate(texte.splitlines(), 1):
        if ligne.startswith("////"):
            if len(noms) >= NB_SECTIONS:
                raise ValueError(f"{etiquette}, ligne {numero} : plus de {NB_SECTIONS} sections")
            noms.append(_nom_section(ligne))
            donnees.append([])
            continue
        jetons = ligne.partition("//")[0].split()
        if not jetons or not _DEBUT_NOMBRE.match(jetons[0]):
            continue
        if not donnees:
            raise ValueError(f"{etiquette}, ligne {numero} : des valeurs précèdent le premier en-tête de section")
        if len(donnees[-1]) >= NB_HEURES:
            raise ValueError(f"{etiquette}, ligne {numero} : plus de {NB_HEURES} heures dans la section {len(noms) - 1}")
        if len(jetons) != NB_COLONNES:
            raise ValueError(f"{etiquette}, ligne {numero} : {len(jetons)} colonnes au lieu de {NB_COLONNES}")
        try:
            valeurs = [float(j) for j in jetons]
        except ValueError:
            raise ValueError(f"{etiquette}, ligne {numero} : valeur non numérique") from None
        if not all(math.isfinite(x) for x in valeurs):
            raise ValueError(f"{etiquette}, ligne {numero} : valeur non finie")
        donnees[-1].append(valeurs)
    if len(noms) != NB_SECTIONS or any(len(s) != NB_HEURES for s in donnees):
        raise ValueError(f"{etiquette} : structure inattendue ({len(noms)} sections, heures par section "
                         f"{[len(s) for s in donnees]}, attendu {NB_SECTIONS} × {NB_HEURES})")
    return noms, donnees


def _lire_fichier(chemin, etiquette):
    p = Path(chemin)
    try:
        if not p.is_file():
            raise ValueError(f"{etiquette} : fichier introuvable ({chemin})")
        if p.stat().st_size > TAILLE_MAX:
            raise ValueError(f"{etiquette} : fichier trop volumineux pour un timecyc.dat ({chemin})")
        return p.read_bytes().decode("latin-1")
    except OSError as e:
        raise ValueError(f"{etiquette} : lecture impossible ({e.strerror or e})") from None


# --------------------------------------------------------------------------- couleurs

def _octet(x):
    return min(255, max(0, int(round(x))))


def _rgb(v, debut):
    return tuple(_octet(x) for x in v[debut:debut + 3])


def _hex(c):
    return "#%02X%02X%02X" % c


def _melange(a, b, poids):
    return tuple(_octet(x + (y - x) * poids) for x, y in zip(a, b))


def echantillon(v):
    """Couleurs retenues pour une heure : ciel haut, horizon, mer (RGB) et opacité de l'eau."""
    return {"haut": _rgb(v, CIEL_HAUT), "horizon": _rgb(v, HORIZON),
            "mer": _rgb(v, MER), "opacite": _octet(v[OPACITE_MER])}


# --------------------------------------------------------------------------- dessin

def _attr(texte):
    return escape(texte, {'"': "&quot;"})


def _panneau(x, y, numero, legende, ech, defs, corps):
    """Dessine un schéma ciel + mer et ses trois lignes de valeurs."""
    h, hor, mer = ech["haut"], ech["horizon"], ech["mer"]
    proche = _melange(hor, mer, MELANGE_MER_HORIZON)
    defs.append(f'<linearGradient id="ciel{numero}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{_hex(h)}"/><stop offset="1" stop-color="{_hex(hor)}"/></linearGradient>')
    defs.append(f'<linearGradient id="mer{numero}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{_hex(proche)}"/><stop offset="1" stop-color="{_hex(mer)}"/></linearGradient>')
    resume = (f"{legende} : ciel du haut {_hex(h)} vers l'horizon {_hex(hor)}, mer {_hex(mer)}, "
              f"opacité de l'eau {ech['opacite']} sur 255")
    corps.append(f'<text x="{x}" y="{y - 8}" font-size="14" font-weight="bold">{escape(legende)}</text>')
    corps.append(f'<g role="img" aria-label="{_attr(resume)}"><title>{escape(resume)}</title>'
                 f'<rect x="{x}" y="{y}" width="{LARGEUR_PANNEAU}" height="{H_CIEL}" fill="url(#ciel{numero})"/>'
                 f'<rect x="{x}" y="{y + H_CIEL}" width="{LARGEUR_PANNEAU}" height="{H_MER}" fill="url(#mer{numero})"/>'
                 f'<rect x="{x}" y="{y}" width="{LARGEUR_PANNEAU}" height="{H_CIEL + H_MER}" '
                 f'fill="none" stroke="{TRAIT}" stroke-width="1"/></g>')
    lignes = (("Ciel haut", h, ""), ("Horizon", hor, ""),
              ("Mer", mer, f", opacité {ech['opacite']}/255"))
    for i, (nom, couleur, suite) in enumerate(lignes):
        ty = y + H_CIEL + H_MER + 22 + 20 * i
        corps.append(f'<rect x="{x}" y="{ty - 11}" width="12" height="12" fill="{_hex(couleur)}" '
                     f'stroke="{TRAIT}" stroke-width="1" aria-hidden="true"/>')
        corps.append(f'<text x="{x + 20}" y="{ty}" font-size="13">{escape(nom)} : '
                     f'{couleur[0]} {couleur[1]} {couleur[2]} ({_hex(couleur)}){escape(suite)}</text>')


def _comparer_noms(noms_base, noms_orage):
    ecarts = [i for i, (a, b) in enumerate(zip(noms_base, noms_orage)) if a.casefold() != b.casefold()]
    if ecarts:
        raise ValueError("Les deux palettes n'ont pas les mêmes en-têtes aux sections "
                         + ", ".join(map(str, ecarts))
                         + " : ce ne sont probablement pas deux versions du même fichier")


def _sections(noms):
    choix = [SECTION_PLUIE]
    note = None
    if noms[SECTION_OURAGAN].casefold() == 'rainy' or _MOTS_ORAGE.search(noms[SECTION_OURAGAN]):
        choix.append(SECTION_OURAGAN)
    else:
        nom = noms[SECTION_OURAGAN] or "sans nom"
        note = f"Section {SECTION_OURAGAN} (« {nom} ») : en-tête sans nom d'orage, section non affichée."
    return choix, note


def _etiquette(noms, s):
    if s == SECTION_OURAGAN and noms[s].casefold() == "rainy":
        return f"Section {s} · Ouragan ({noms[s]})"
    return f"Section {s} · {noms[s]}" if noms[s] else f"Section {s} · sans nom"


def construire_apercu(texte_base, texte_orage):
    """Renvoie le texte SVG de l'aperçu à partir des deux textes de palette."""
    noms, base = lire_palette(texte_base, "Palette de base")
    noms_orage, orage = lire_palette(texte_orage, "Palette orage")
    _comparer_noms(noms, noms_orage)
    choix, note = _sections(noms)

    legende = [
        "Aperçu des palettes, pas une capture du jeu : ni éclairage, ni nuages, ni brouillard, ni reflets, ni textures.",
        "Ciel : dégradé entre la couleur du haut (colonnes 16 à 18) et celle de l'horizon (colonnes 19 à 21).",
        f"Mer : dégradé d'un mélange {round(MELANGE_MER_HORIZON * 100)} % horizon / eau vers la couleur d'eau "
        "(colonnes 49 à 51) ; ce mélange est un choix du schéma.",
        "L'opacité de l'eau (colonne 52) est écrite en chiffres, elle n'est pas appliquée au dessin.",
        "Valeurs arrondies à l'entier le plus proche, bornées de 0 à 255. Temps échantillonnés : "
        + ", ".join(f"{h} h" for h in HEURES) + ".",
    ]
    if note:
        legende.append(note)

    defs, corps = [], []
    y = HAUT_ENTETE
    numero = 0
    for s in choix:
        for h in HEURES:
            corps.append(f'<text x="{MARGE}" y="{y + 4}" font-size="16" font-weight="bold">'
                         f'{escape(_etiquette(noms, s))} — {h} h</text>')
            for colonne, (nom, source) in enumerate((("Palette de base", base), ("Palette orage", orage))):
                x = MARGE + colonne * (LARGEUR_PANNEAU + ECART)
                _panneau(x, y + 40, numero, nom, echantillon(source[s][h]), defs, corps)
                numero += 1
            y += HAUT_RANGEE
    corps.append(f'<line x1="{MARGE}" y1="{y - 12}" x2="{LARGEUR - MARGE}" y2="{y - 12}" stroke="{TRAIT}" stroke-width="1"/>')
    corps.append(f'<text x="{MARGE}" y="{y + 10}" font-size="16" font-weight="bold">Légende</text>')
    for i, ligne in enumerate(legende):
        corps.append(f'<text x="{MARGE}" y="{y + 34 + LIGNE_LEGENDE * i}" font-size="13">{escape(ligne)}</text>')
    hauteur = y + 34 + LIGNE_LEGENDE * len(legende) + MARGE - 6

    titre = "Aperçu des couleurs de ciel et de mer : palette de base et palette orage"
    descr = (f"Pour chaque temps échantillonné ({', '.join(f'{h} h' for h in HEURES)}) de "
             f"{len(choix)} section(s) météo, deux schémas côte à côte : palette de base à gauche, palette orage à "
             "droite. Chaque schéma montre le dégradé du ciel, la mer et trois lignes de couleurs chiffrées. "
             "C'est un aperçu des palettes, pas une capture du jeu.")
    tete = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGEUR}" height="{hauteur}" '
        f'viewBox="0 0 {LARGEUR} {hauteur}" role="img" aria-labelledby="titre description" lang="fr" xml:lang="fr" '
        'font-family="Segoe UI, Arial, sans-serif">',
        f'<title id="titre">{escape(titre)}</title>',
        f'<desc id="description">{escape(descr)}</desc>',
        f'<defs>{"".join(defs)}</defs>',
        f'<rect width="{LARGEUR}" height="{hauteur}" fill="{FOND}"/>',
        f'<g fill="{ENCRE}">',
        f'<text x="{MARGE}" y="36" font-size="22" font-weight="bold">{escape(titre)}</text>',
        f'<text x="{MARGE}" y="60" font-size="13">Aperçu des palettes uniquement, pas une capture du jeu.</text>',
    ]
    return "\n".join(tete + corps + ["</g>", "</svg>", ""])


# --------------------------------------------------------------------------- ligne de commande

USAGE = "Usage : python outils/apercu_meteo.py PALETTE_BASE PALETTE_ORAGE APERCU.svg"


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) != 3:
        print(f"Trois arguments attendus, {len(args)} reçu(s).\n{USAGE}", file=sys.stderr)
        return 2
    base, orage, sortie = args
    try:
        if Path(sortie).suffix.lower() != ".svg":
            raise ValueError(f"Le fichier de sortie doit se terminer par .svg ({sortie})")
        chemins = {Path(sortie).resolve()}
        if {Path(base).resolve(), Path(orage).resolve()} & chemins:
            raise ValueError("Le fichier de sortie ne doit pas être l'un des deux fichiers d'entrée")
        if not Path(sortie).resolve().parent.is_dir():
            raise ValueError(f"Le dossier de sortie n'existe pas ({sortie})")
        svg = construire_apercu(_lire_fichier(base, "Palette de base"), _lire_fichier(orage, "Palette orage"))
        try:
            Path(sortie).write_text(svg, encoding="utf-8", newline="\n")
        except OSError as e:
            raise ValueError(f"Écriture impossible ({e.strerror or e})") from None
    except ValueError as e:
        print(f"Erreur : {e}\n{USAGE}", file=sys.stderr)
        return 2
    print(f"Aperçu écrit : {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
