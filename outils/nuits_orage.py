"""Profil visuel optionnel « Nuits d'orage » pour la palette météo de Vice City PC classique.

Le profil refroidit et assombrit les nuits de pluie et d’ouragan, avec une transition
au crépuscule et à l’aube. La palette de Vice City contient six météos de 24 heures
et un dernier bloc de 24 couleurs spéciales utilisées par les scènes et les intérieurs.
Le jeu identifie l’ouragan par l’index 5, bien que le fichier d’origine le nomme RAINY.

Cette transformation reçoit la palette de base déjà générée. Chaque lancement la
recalcule depuis cette base pour garantir des valeurs stables après plusieurs essais.
"""
from math import isfinite
import re

ENTETES = ("SUNNY", "CLOUDY", "RAINY", "FOGGY", "EXTRASUNNY", "RAINY", "EXTRACOLOURS")
PLUIE, OURAGAN = 2, 5
SECTIONS_PLUIE = (PLUIE, OURAGAN)
NB_SECTIONS = len(ENTETES)
NB_HEURES = 24
NB_COLONNES = 52

# Poids de la nuit orageuse par heure : le midi (9 h à 16 h) reste intact et la
# variation entre deux heures voisines (23 h -> 0 h compris) ne dépasse pas 0,27.
NUIT = (1.0, 1.0, 1.0, 1.0, .95, .80, .55, .28, .10,
        0, 0, 0, 0, 0, 0, 0, 0,
        .08, .25, .50, .75, .92, 1.0, 1.0)
# Reflet chaud pâle de l'horizon aux heures de passage (soir et aube).
TEINTE = {5: .30, 6: .50, 7: .30, 18: .25, 19: .40, 20: .25}

_NOMBRE = re.compile(r"[+-]?\d+")


def _borner(nouveau, origine, limite, bas=0.0, haut=255.0, plancher=None):
    """Garde `nouveau` à ±limite de l'original, dans [bas, haut], avec un seuil de lisibilité."""
    valeur = min(max(nouveau, origine - limite), origine + limite)
    if plancher is not None:
        valeur = max(valeur, min(origine, plancher))
    return min(max(valeur, bas), haut)


def _melange(valeurs, cible, poids):
    return [v + (c - v) * poids for v, c in zip(valeurs, cible)]


def _transformer(v, nuit, teinte):
    """Retourne la liste des 52 valeurs flottantes modifiées pour une ligne pluie/orage."""
    r = list(v)

    def groupe(debut, fin, cible, force, limite, plancher=None, chaud=None):
        orig = v[debut:fin]
        nouv = _melange(orig, cible, nuit * force)
        if chaud is not None:
            nouv = _melange(nouv, chaud, teinte * .22)
        for k in range(fin - debut):
            r[debut + k] = _borner(nouv[k], orig[k], limite, plancher=plancher)

    groupe(0, 3, (46, 58, 92), .30, 30, plancher=28)          # ambiance, jamais noire
    groupe(12, 15, (88, 104, 150), .28, 30, plancher=30)      # lumière directionnelle lunaire
    groupe(15, 18, (10, 14, 38), .55, 60)                     # haut du ciel
    groupe(18, 21, (58, 52, 88), .40, 55, chaud=(176, 104, 124))  # horizon
    groupe(36, 39, (36, 40, 66), .45, 55)                     # nuages bas
    groupe(39, 42, (36, 40, 66), .45, 55)                     # dessus des nuages de type fluffy
    groupe(42, 45, (36, 40, 66), .45, 55)                     # dessous des mêmes nuages
    groupe(48, 51, (22, 64, 88), .35, 40)                     # eau RGB
    r[51] = _borner(v[51] + (190 - v[51]) * nuit * .25, v[51], 35)  # eau alpha

    # SprBght et LightOnGround sont des intensités décimales. FarClp et FogSt
    # sont des distances en unités du jeu et FogSt peut être négatif.
    r[29] = v[29] * (1 + .15 * nuit)
    r[33] = v[33] * (1 - .18 * nuit)
    r[34] = v[34] - abs(v[34]) * .30 * nuit
    r[35] = v[35] * (1 - .12 * nuit)
    return r


def _format(origine, valeur, colonne):
    if colonne in (29, 33, 34, 35):
        # Le moteur attend des flottants même lorsque le jeton original est entier.
        # Un seul chiffre transformerait 1 × 1,15 en 1,2, au-delà de la borne.
        nombre = f"{valeur:.6f}".rstrip("0").rstrip(".")
        return nombre + ".0" if "." in origine and "." not in nombre else nombre
    if _NOMBRE.fullmatch(origine):
        return str(int(round(valeur)))
    decimales = len(origine.partition(".")[2])
    return f"{valeur:.{max(decimales, 1)}f}"


def _ligne(ligne, numero, section, heure):
    code, separateur, commentaire = ligne.partition("//")
    spans = [m.span() for m in re.finditer(r"\S+", code)]
    if len(spans) != NB_COLONNES:
        raise ValueError(f"Format de palette inattendu, ligne {numero}, {len(spans)} colonnes")
    jetons = [code[a:b] for a, b in spans]
    try:
        v = [float(j) for j in jetons]
    except ValueError:
        raise ValueError(f"Format de palette inattendu, ligne {numero}, valeur non numérique") from None
    if not all(isfinite(x) for x in v):
        raise ValueError(f"Format de palette inattendu, ligne {numero}, valeur non finie")
    if section not in SECTIONS_PLUIE:
        return ligne
    if v[33] <= 0 or v[34] >= v[33] or min(v[29], v[35]) < 0:
        raise ValueError(f"Distance ou intensité incohérente, ligne {numero}")
    nouveau = _transformer(v, NUIT[heure], TEINTE.get(heure, 0.0))
    for i in reversed(range(len(spans))):
        if nouveau[i] == v[i]:
            continue
        valeur = _format(jetons[i], nouveau[i], i)
        if float(valeur) != v[i]:
            a, b = spans[i]
            code = code[:a] + valeur + code[b:]
    return code + separateur + commentaire


def appliquer_nuits_orage(texte_palette: str) -> str:
    """Renvoie la palette de base avec le profil « Nuits d'orage » sur la pluie (2) et l'ouragan (5)."""
    if not isinstance(texte_palette, str):
        raise TypeError("La palette doit être un texte")
    section, heure, sortie = -1, 0, []
    heures = [0] * NB_SECTIONS
    for numero, ligne in enumerate(texte_palette.splitlines(keepends=True), 1):
        if ligne.startswith("////"):
            section += 1
            heure = 0
            if section >= NB_SECTIONS:
                raise ValueError(f"Format de palette inattendu, ligne {numero}, trop de sections")
            nom = ligne.strip().lstrip("/").strip().upper()
            if nom != ENTETES[section] and not (section == OURAGAN and nom == "HURRICANE"):
                raise ValueError(f"En-tête météo inattendu à l’index {section}, ligne {numero} ({nom})")
            sortie.append(ligne)
            continue
        premier = ligne.partition("//")[0].split()
        if not premier:
            sortie.append(ligne)
            continue
        if section < 0:
            raise ValueError(f"Format de palette inattendu, ligne {numero}, données avant la première section")
        if heure >= NB_HEURES:
            raise ValueError(f"Format de palette inattendu, ligne {numero}, plus de {NB_HEURES} heures")
        sortie.append(_ligne(ligne, numero, section, heure))
        heure += 1
        heures[section] = heure
    if section != NB_SECTIONS - 1 or heures != [NB_HEURES] * NB_SECTIONS:
        raise ValueError(f"Structure de palette inattendue : {section + 1} sections, heures {heures}")
    return "".join(sortie)
