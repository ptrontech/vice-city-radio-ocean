# -*- coding: utf-8 -*-
"""Générateur local de détails d'architecture pour les façades de Vice City.

API unique : ``construire_decor(baie, famille, graine) -> [triangle, ...]``.

Un triangle est un tuple de trois sommets ``(x, y, z, r, g, b)`` ; x, y, z sont
des mètres, r, g, b des entiers 0..255.

Repère local DIRECT, en mètres, relatif au panneau de façade :
    x : horizontal vers la droite, dans [0, largeur]
    y : profondeur vers l'intérieur ; l'observateur est à y < 0 (devant la façade)
    z : vertical depuis le bord bas du panneau, dans [0, hauteur]
Toute géométrie reste dans y ∈ [-0.13, profondeur].

Convention de winding : sens anti-horaire vu du côté extérieur de la face
(normale = (b-a)x(c-a) sortante). Toute face tournée vers l'arrière (normale
avec composante y > 0, invisible depuis y < 0) est supprimée à la source.
Pour le mode « piece », les dix premiers triangles sont la coque du
compartiment : sol (+z), plafond (-z), embrasure gauche (+x), embrasure droite
(-x), mur arrière (-y), chacun en deux triangles.

Aucune dépendance hors bibliothèque standard, aucune lecture de fichier,
aucun aléa global : l'aléa vient d'un ``random.Random`` local, dérivé de
(mode, famille, graine).

Budgets (triangles maximum) : piece 99, retrait 45, corniche 27.
"""
from __future__ import annotations

import math
import random

__all__ = ["construire_decor", "FAMILLES", "MODES", "BUDGETS", "Y_MIN"]

FAMILLES = ("deco", "habitation", "commerce", "bureau", "industriel", "public")
BUDGETS = {"piece": 99, "retrait": 45, "corniche": 27}
MODES = tuple(BUDGETS)
Y_MIN = -0.13
_PROFONDEUR_DEFAUT = {"piece": 1.0, "retrait": 0.2, "corniche": 0.12}

# --------------------------------------------------------------------------
# Palettes (couleurs originales, propres au mod)
# --------------------------------------------------------------------------
_MURS = {
    "deco": [(232, 172, 178), (150, 208, 200), (244, 214, 170), (190, 170, 220)],
    "habitation": [(226, 208, 176), (206, 186, 150), (176, 200, 176), (214, 176, 150)],
    "commerce": [(236, 226, 196), (214, 224, 206), (240, 200, 180), (200, 214, 230)],
    "bureau": [(198, 206, 198), (220, 216, 200), (190, 198, 210)],
    "industriel": [(150, 152, 146), (170, 160, 140), (138, 146, 150)],
    "public": [(214, 206, 176), (180, 200, 184), (208, 196, 170)],
}
_SOLS = {
    "deco": [(80, 70, 78), (196, 184, 160)],
    "habitation": [(128, 92, 60), (150, 120, 84), (168, 140, 110)],
    "commerce": [(176, 160, 140), (120, 124, 128)],
    "bureau": [(96, 100, 104), (130, 110, 90)],
    "industriel": [(104, 102, 98), (122, 112, 100)],
    "public": [(150, 140, 120), (110, 120, 112)],
}
_BOIS = [(120, 80, 48), (150, 104, 62), (92, 62, 40), (170, 128, 80)]
_TISSUS = [(168, 52, 60), (48, 120, 140), (214, 170, 70), (88, 70, 130),
           (60, 130, 90), (230, 120, 140)]
_VIFS = [(200, 60, 50), (60, 110, 190), (230, 190, 60), (70, 160, 90),
         (240, 240, 230), (150, 80, 160)]
_EMAILS = [(30, 90, 70), (200, 200, 190), (160, 50, 40), (40, 50, 60)]
_PIERRES = [(222, 214, 196), (206, 196, 176), (232, 226, 214), (198, 186, 166)]
_MENUISERIES = [(236, 232, 222), (60, 88, 70), (90, 60, 40), (40, 44, 52), (150, 40, 36)]
_METAL = (70, 72, 78)
_SOMBRE = (38, 34, 36)
_ACIERS = [(110, 118, 112), (120, 100, 80), (96, 106, 120)]


# --------------------------------------------------------------------------
# Géométrie de base
# --------------------------------------------------------------------------
def _mix(a, b, t):
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(3))


def _newell(pts):
    nx = ny = nz = 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return nx, ny, nz


_LUMIERE = (-0.35, -0.75, 0.55)
_LUMIERE = tuple(v / math.sqrt(sum(w * w for w in _LUMIERE)) for v in _LUMIERE)


def _face(pts, sortant, col, lit=False):
    """Polygone convexe orienté vers `sortant` ; vide si tourné vers y > 0."""
    n = _newell(pts)
    ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if ln < 1e-12:
        return []
    if n[0] * sortant[0] + n[1] * sortant[1] + n[2] * sortant[2] < 0:
        pts = pts[::-1]
        n = (-n[0], -n[1], -n[2])
    n = (n[0] / ln, n[1] / ln, n[2] / ln)
    if n[1] > 1e-9:
        return []
    if lit:
        f = 1.0
    else:
        f = 0.58 + 0.42 * max(0.0, n[0] * _LUMIERE[0] + n[1] * _LUMIERE[1] + n[2] * _LUMIERE[2])
    rgb = tuple(int(round(min(255.0, max(0.0, v * f)))) for v in col)
    sommets = [(p[0], p[1], p[2]) + rgb for p in pts]
    return [(sommets[0], sommets[i], sommets[i + 1]) for i in range(1, len(sommets) - 1)]


def _bande(x0, x1, y, z0, z1, col, lit=False):
    """Quad plan, face vers l'observateur (-y)."""
    return _face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], (0, -1, 0), col, lit)


def _box(x0, x1, y0, y1, z0, z1, col, faces="ftlr", lit=False):
    """Boîte ; faces : f(avant -y) b(arrière +y) t(dessus) u(dessous) l(-x) r(+x)."""
    spec = {
        "f": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        "b": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
        "t": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        "u": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
        "l": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
        "r": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
    }
    tris = []
    for k in faces:
        pts, out = spec[k]
        tris += _face(pts, out, col, lit)
    return tris


def _prisme(cx, cy, z0, z1, r0, r1, n, col, haut=True, lit=False, phase=0.3):
    """Tronc de pyramide régulier à n pans (rayon r0 en bas, r1 en haut)."""
    a = [phase + 2.0 * math.pi * k / n for k in range(n)]
    bas = [(cx + r0 * math.cos(t), cy + r0 * math.sin(t), z0) for t in a]
    hau = [(cx + r1 * math.cos(t), cy + r1 * math.sin(t), z1) for t in a]
    tris = []
    for k in range(n):
        j = (k + 1) % n
        m = a[k] + math.pi / n
        tris += _face([bas[k], bas[j], hau[j], hau[k]], (math.cos(m), math.sin(m), 0.0), col, lit)
    if haut:
        tris += _face(hau, (0, 0, 1), col, lit)
    return tris


# --------------------------------------------------------------------------
# Contexte : dimensions, couleurs, aléa local
# --------------------------------------------------------------------------
class _Ctx:
    def __init__(self, baie, famille, graine):
        self.mode = baie["mode"]
        self.famille = famille
        self.L = float(baie["largeur"])
        self.H = float(baie["hauteur"])
        self.P = float(baie.get("profondeur", _PROFONDEUR_DEFAUT[self.mode]))
        self.nuit = bool(baie.get("nuit", False))
        self.vitrine = bool(baie.get("vitrine", False))
        t = baie.get("teinte")
        self.teinte = tuple(float(v) for v in t[:3]) if t else None
        self.rng = random.Random("|".join(("vc-decor-v1", self.mode, famille, str(int(graine)))))
        if self.mode == "piece":
            self.amb = (1.0, 0.9, 0.72) if self.nuit else (0.84, 0.87, 0.9)
        else:
            self.amb = (0.62, 0.66, 0.8) if self.nuit else (1.0, 1.0, 1.0)
        self.lueur = (255, 214, 140) if self.nuit else (240, 232, 205)
        self.zone = (0.0, self.L)  # emprise x du mobilier posé contre le mur arrière
        self.avant = self.P  # y du bord avant de ce mobilier

    def u(self, a, b):
        return self.rng.uniform(a, b)

    def pick(self, seq):
        return seq[self.rng.randrange(len(seq))]

    def ton(self, col):
        return tuple(col[i] * self.amb[i] for i in range(3))

    def melange(self, col, t):
        return _mix(col, self.teinte, t) if self.teinte else tuple(col)

    def span(self, w, marge=0.12):
        hi = self.L - marge - w
        return self.u(marge, hi) if hi > marge else (self.L - w) / 2.0

    def pierre(self):
        base = self.pick(_PIERRES)
        if self.teinte:
            base = _mix(_mix(self.teinte, (236, 230, 216), 0.45), base, 0.3)
        return self.ton(base)


# --------------------------------------------------------------------------
# Mode « piece » : compartiment visible derrière l'ouverture
# --------------------------------------------------------------------------
def _coque(c):
    L, H, P = c.L, c.H, c.P
    mur = c.melange(c.pick(_MURS[c.famille]), 0.25)
    sol = c.pick(_SOLS[c.famille])
    plafond = _mix(mur, (245, 240, 228), 0.55)
    lateral = _mix(mur, (0, 0, 0), 0.08)
    c.mur = mur
    t = _face([(0, 0, 0), (L, 0, 0), (L, P, 0), (0, P, 0)], (0, 0, 1), c.ton(sol))
    t += _face([(0, 0, H), (L, 0, H), (L, P, H), (0, P, H)], (0, 0, -1), c.ton(plafond))
    t += _face([(0, 0, 0), (0, P, 0), (0, P, H), (0, 0, H)], (1, 0, 0), c.ton(lateral))
    t += _face([(L, 0, 0), (L, P, 0), (L, P, H), (L, 0, H)], (-1, 0, 0), c.ton(lateral))
    t += _face([(0, P, 0), (L, P, 0), (L, P, H), (0, P, H)], (0, -1, 0), c.ton(mur))
    return t


def _seuil(c):
    pierre = c.ton(c.pick(_PIERRES))
    if c.vitrine:  # pas de saillie au sol devant une vitrine
        return [_box(0, c.L, 0.0, 0.12, 0, 0.04, pierre, "ft")]
    return [_box(0, c.L, -0.06, 0.12, 0, 0.05, pierre, "ftlru")]


def _lambris(c):
    h = min(0.9, 0.4 * c.H)
    return [_bande(0, c.L, c.P - 0.01, 0, h, c.ton(_mix(c.mur, (60, 40, 30), 0.3)))]


def _poutres(c):
    pierre = c.ton(_mix(c.mur, (90, 70, 50), 0.4))
    n = 2 if c.P > 1.4 else 1
    return [_box(0, c.L, c.P * (k + 1) / (n + 1) - 0.06, c.P * (k + 1) / (n + 1) + 0.06,
                 c.H - 0.16, c.H, pierre, "fu") for k in range(n)]


def _rideaux(c):
    L, H = c.L, c.H
    cw = min(0.55, 0.2 * L)
    nf = 2 if cw < 0.32 else 3
    col = c.ton(c.pick(_TISSUS))
    ztop = H - 0.07
    zb = 0.04 if c.rng.random() < 0.6 else c.u(0.3, 0.5) * H
    amp = c.u(0.05, 0.08)
    y = 0.04

    def drape(x0, x1):
        pts = []
        for i in range(2 * nf + 1):
            pts.append((x0 + (x1 - x0) * i / (2 * nf), y + (amp if i % 2 else 0.0),
                        zb + c.u(0.0, 0.03) * H))
        t = []
        for a, b in zip(pts, pts[1:]):
            t += _face([(a[0], a[1], ztop), (b[0], b[1], ztop), (b[0], b[1], b[2]), (a[0], a[1], a[2])],
                       (0, -1, 0), col)
        return t

    tringle = _box(0.02, L - 0.02, 0.0, 0.06, ztop + 0.01, ztop + 0.04, c.ton(_METAL), "ft")
    gauche = drape(0.03, 0.03 + cw)
    droit = drape(L - 0.03 - cw, L - 0.03)
    if L < 1.2:
        return [tringle + (gauche if c.rng.random() < 0.5 else droit)]
    return [tringle + gauche, droit]


def _persiennes(c):
    L, H = c.L, c.H
    x0, x1 = 0.03, L - 0.03
    if L > 2.2 and c.rng.random() < 0.5:
        x1 = x0 + (L - 0.06) * c.u(0.45, 0.6)
    zt = H - 0.05
    zb = zt - (H - 0.1) * c.u(0.4, 0.8)
    n = max(3, min(9, int((zt - zb) / 0.1)))
    pas = (zt - zb) / n
    col = c.ton(c.pick(_MENUISERIES))
    t = _box(x0, x0 + 0.03, -0.04, 0.05, zb - 0.02, zt, c.ton(_METAL), "f")
    t += _box(x1 - 0.03, x1, -0.04, 0.05, zb - 0.02, zt, c.ton(_METAL), "f")
    for i in range(n):
        z = zt - pas * i
        t += _face([(x0, -0.03, z), (x1, -0.03, z), (x1, 0.04, z - 0.045), (x0, 0.04, z - 0.045)],
                   (0, -1, -1), col)
    return [t]


def _rideau_fer(c):
    L, H = c.L, c.H
    zb = H * (1.0 - c.u(0.45, 0.8))
    ztop = H - 0.2
    if ztop - zb < 0.2:
        return []
    n = max(4, min(10, int((ztop - zb) / 0.1)))
    col = c.ton(c.pick(_ACIERS))
    pts = [(ztop - (ztop - zb) * i / n, 0.03 + (0.04 if i % 2 else 0.0)) for i in range(n + 1)]
    ondes = []
    for (za, ya), (zc, yc) in zip(pts, pts[1:]):
        ondes += _face([(0.02, ya, za), (L - 0.02, ya, za), (L - 0.02, yc, zc), (0.02, yc, zc)],
                       (0, -1, 0), col)
    coffre = _box(0, L, -0.07, 0.10, H - 0.2, H, col, "fulr")
    lisse = _box(0.02, L - 0.02, 0.0, 0.08, zb - 0.05, zb, c.ton(_METAL), "fu")
    return [coffre, ondes, lisse]


def _objet(c, x, y, z, h, w, genre, col):
    if genre == 0:
        return _box(x - w / 2, x + w / 2, y - w * 0.4, y + w * 0.4, z, z + h, col, "ftlr")
    if genre == 1:
        return _prisme(x, y, z, z + h * 0.7, w / 2, w / 2, 5, col)
    return _prisme(x, y, z, z + h, w / 2, w * 0.2, 5, col)


def _etageres(c):
    L, H, P = c.L, c.H, c.P
    d = min(0.34, 0.3 * P)
    larg = min(L - 0.2, c.u(1.2, 2.6))
    if larg < 0.5:
        return []
    xa = c.span(larg, 0.1)
    xb = xa + larg
    n = max(1, min(3, int((H - 0.4) / 0.55)))
    pas = (H - 0.6) / n
    zs = [0.3 + i * pas for i in range(n)]
    ztop = min(H - 0.08, zs[-1] + 0.4)
    y0, y1 = P - d - 0.03, P - 0.03
    bois = c.ton(c.pick(_BOIS))
    chunks = [_box(xa, xa + 0.03, y0, y1, 0, ztop, bois, "fl")
              + _box(xb - 0.03, xb, y0, y1, 0, ztop, bois, "fr")]
    for i, z in enumerate(zs):
        t = _box(xa + 0.03, xb - 0.03, y0, y1, z, z + 0.03, bois, "ftu")
        lib = (zs[i + 1] if i < n - 1 else H - 0.08) - (z + 0.03) - 0.04
        k = c.rng.randint(2, 3)
        fente = (larg - 0.06) / k
        if lib >= 0.08:
            for j in range(k):
                w = min(0.14, fente * 0.6)
                x = xa + 0.03 + fente * (j + 0.5) + c.u(-0.1, 0.1) * fente
                yy = (y0 + y1) / 2 + c.u(-0.05, 0.05) * d
                t += _objet(c, x, yy, z + 0.03, min(0.28, lib) * c.u(0.6, 1.0), w,
                            c.rng.randrange(3), c.ton(c.pick(_VIFS)))
        chunks.append(t)
    c.zone, c.avant = (xa, xb), y0
    return chunks


def _canape(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(1.3, 1.9), L - 0.3) if L >= 1.4 else L * 0.8
    d = min(0.7, 0.45 * P)
    hs, hd = min(0.42, 0.4 * H), min(0.85, 0.7 * H)
    x0 = c.span(w)
    y1 = P - 0.04
    y0 = y1 - d
    tissu = c.ton(c.pick(_TISSUS))
    fonce = _mix(tissu, (0, 0, 0), 0.15)
    c.zone, c.avant = (x0, x0 + w), y0
    return [_box(x0, x0 + w, y0, y1, 0.08, hs, tissu, "ftlr"),
            _box(x0, x0 + w, y1 - 0.18, y1, hs, hd, fonce, "ftlr"),
            _box(x0, x0 + 0.12, y0, y1, hs, hs + 0.18, fonce, "ftl")
            + _box(x0 + w - 0.12, x0 + w, y0, y1, hs, hs + 0.18, fonce, "ftr")]


def _table_basse(c):
    L, H, P = c.L, c.H, c.P
    w = min(0.9, 0.45 * L)
    d = min(0.45, 0.3 * P)
    h = min(0.38, 0.45 * H)
    y1 = c.avant - 0.12
    y0 = y1 - d
    if y0 < 0.12 or w < 0.3:
        return []
    a, b = c.zone
    x0 = min(max((a + b) / 2 - w / 2, 0.1), L - 0.1 - w)
    bois = c.ton(c.pick(_BOIS))
    t = _box(x0, x0 + w, y0, y1, h - 0.04, h, bois, "ftlru")
    t += _box(x0 + 0.02, x0 + 0.05, y0 + 0.03, y1 - 0.03, 0, h - 0.04, bois, "fl")
    t += _box(x0 + w - 0.05, x0 + w - 0.02, y0 + 0.03, y1 - 0.03, 0, h - 0.04, bois, "fr")
    bol = _prisme(x0 + w * c.u(0.3, 0.7), (y0 + y1) / 2, h, h + 0.07, 0.06, 0.09, 5,
                  c.ton(c.pick(_VIFS)), haut=False)
    return [t, bol]


def _secretaire(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(0.8, 1.1), L - 0.3)
    if w < 0.4:
        return []
    s = min(1.0, (H - 0.12) / 1.35)
    d = min(0.5, 0.4 * P)
    x0 = c.span(w)
    x1 = x0 + w
    y1 = P - 0.04
    y0 = y1 - d
    pente = min(0.25, 0.5 * d)
    h1, h2, h3 = 0.72 * s, 0.95 * s, 1.32 * s
    bois = c.ton(c.pick(_BOIS))
    sombre = c.ton(_SOMBRE)
    c.zone, c.avant = (x0, x1), y0
    corps = _box(x0, x1, y0, y1, 0, h1, bois, "flr")
    for k in range(2):
        z = (0.1 + 0.28 * k) * s
        corps += _bande(x0 + 0.04, x1 - 0.04, y0 - 0.004, z, z + 0.015, sombre)
    corps += _face([(x0, y0, h1), (x1, y0, h1), (x1, y0 + pente, h2), (x0, y0 + pente, h2)],
                   (0, -1, 0.5), c.ton(_mix(bois, (255, 235, 200), 0.15)))
    corps += _face([(x0, y0, h1), (x0, y0 + pente, h1), (x0, y0 + pente, h2)], (-1, 0, 0), bois)
    corps += _face([(x1, y0, h1), (x1, y0 + pente, h1), (x1, y0 + pente, h2)], (1, 0, 0), bois)
    haut = _box(x0 + 0.04, x1 - 0.04, y0 + pente, y1, h2, h3, bois, "ftlr")
    for k in range(2):
        xm = x0 + w * (0.3 + 0.4 * k)
        haut += _bande(xm - 0.1, xm + 0.1, y0 + pente - 0.004, h2 + 0.08 * s, h3 - 0.1 * s, sombre)
    return [corps, haut]


def _bureau(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(1.2, 1.6), L - 0.3)
    if w < 0.4:
        return []
    d = min(0.6, 0.4 * P)
    h = min(0.76, 0.6 * H)
    x0 = c.span(w)
    y1 = P - 0.05
    y0 = y1 - d
    bois = c.ton(c.pick(_BOIS))
    cw = min(0.4, 0.4 * w)
    c.zone, c.avant = (x0, x0 + w), y0
    t = _box(x0, x0 + w, y0, y1, h - 0.04, h, bois, "ftlru")
    t += _box(x0 + 0.02, x0 + 0.02 + cw, y0 + 0.02, y1 - 0.02, 0, h - 0.04, bois, "flr")
    for k in range(2):
        z = 0.08 + k * (h - 0.2) / 2
        t += _bande(x0 + 0.05, x0 + cw - 0.01, y0 + 0.016, z, z + 0.02 * (1 + k), c.ton(_SOMBRE))
    t += _box(x0 + w - 0.06, x0 + w - 0.03, y0 + 0.03, y1 - 0.03, 0, h - 0.04, c.ton(_METAL), "fr")
    xl = x0 + w * c.u(0.5, 0.8)
    lampe = _box(xl - 0.01, xl + 0.01, y1 - 0.2, y1 - 0.18, h, h + 0.2, c.ton(_METAL), "fl")
    lampe += _prisme(xl, y1 - 0.19, h + 0.2, h + 0.3, 0.08, 0.03, 5, c.ton(c.pick(_EMAILS)), haut=False)
    lampe += _face([(xl - 0.02, y1 - 0.21, h + 0.2), (xl + 0.02, y1 - 0.21, h + 0.2),
                    (xl + 0.02, y1 - 0.17, h + 0.2), (xl - 0.02, y1 - 0.17, h + 0.2)],
                   (0, 0, -1), c.lueur, True)
    papiers = _box(x0 + 0.1, x0 + 0.1 + 0.25, y0 + 0.12, y0 + 0.4, h, h + 0.015,
                   (236, 232, 220), "ft")
    return [t, lampe, papiers]


def _cote(c, w):
    """Abscisse d'un meuble de largeur w du côté libre de la zone, ou None."""
    a, b = c.zone
    g, d = a - 0.1, c.L - b - 0.1
    gauche, droite = g >= w, d >= w
    if not (gauche or droite):
        return None
    if gauche and (not droite or c.rng.random() < 0.5):
        return 0.1 + c.u(0.0, g - w)
    return b + 0.1 + c.u(0.0, d - w) if droite else None


def _classeur(c):
    w = 0.45
    x0 = _cote(c, w)
    if x0 is None:
        return []
    d = min(0.5, 0.35 * c.P)
    h = min(1.3, 0.65 * c.H)
    y1 = c.P - 0.05
    y0 = y1 - d
    col = c.ton(c.pick(_EMAILS))
    t = _box(x0, x0 + w, y0, y1, 0, h, col, "ftlr")
    for k in range(3):
        z = 0.06 + k * (h - 0.12) / 3
        t += _bande(x0 + 0.04, x0 + w - 0.04, y0 - 0.004, z, z + (h - 0.12) / 3 - 0.03,
                    c.ton(_mix(col, (0, 0, 0), 0.25)))
    return [t]


def _etabli(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(1.4, 2.2), L - 0.3)
    if w < 0.5:
        return []
    d = min(0.6, 0.45 * P)
    h = min(0.9, 0.7 * H)
    x0 = c.span(w)
    y1 = P - 0.05
    y0 = y1 - d
    bois = c.ton(c.pick(_BOIS))
    metal = c.ton(_METAL)
    c.zone, c.avant = (x0, x0 + w), y0
    t = _box(x0, x0 + w, y0, y1, h - 0.05, h, bois, "ftlru")
    t += _box(x0 + 0.02, x0 + 0.07, y0 + 0.03, y1 - 0.03, 0, h - 0.05, metal, "fl")
    t += _box(x0 + w - 0.07, x0 + w - 0.02, y0 + 0.03, y1 - 0.03, 0, h - 0.05, metal, "fr")
    etagere = _box(x0 + 0.07, x0 + w - 0.07, y0 + 0.04, y1 - 0.02, 0.2, 0.23, bois, "ft")
    xe = x0 + w * c.u(0.1, 0.25)
    etau = _box(xe, xe + 0.14, y0 + 0.08, y0 + 0.24, h, h + 0.12, metal, "ftlr")
    xb = x0 + w * c.u(0.5, 0.8)
    bidon = _box(xb, xb + 0.2, y0 + 0.1, y0 + 0.28, h, h + 0.3, c.ton(c.pick(_EMAILS)), "ftlr")
    bidon += _prisme(xb + 0.1, y0 + 0.19, h + 0.3, h + 0.36, 0.035, 0.03, 5, metal)
    zp = h + 0.25
    panneau = []
    if zp + 0.3 < H - 0.05:
        zt = min(H - 0.1, h + 0.85)
        panneau = _bande(x0, x0 + w, P - 0.01, zp, zt, c.ton(_mix(c.mur, (60, 60, 56), 0.5)))
        for k in range(3):
            xo = x0 + w * (0.15 + 0.3 * k)
            panneau += _bande(xo, xo + 0.03, P - 0.02, zp + 0.08, zt - 0.08, metal)
    return [t, etau, etagere, panneau, bidon]


def _banc(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(1.2, 1.8), L - 0.3)
    if w < 0.4:
        return []
    h = min(0.45, 0.45 * H)
    d = min(0.4, 0.3 * P)
    x0 = c.span(w)
    y1 = P - 0.08
    y0 = y1 - d
    bois = c.ton(c.pick(_BOIS))
    c.zone, c.avant = (x0, x0 + w), y0
    t = _box(x0, x0 + w, y0, y1, h - 0.05, h, bois, "ftlru")
    t += _box(x0, x0 + w, y1 - 0.04, y1, h, min(h + 0.4, H - 0.2), bois, "ftlr")
    t += _box(x0 + 0.04, x0 + 0.08, y0 + 0.03, y1 - 0.03, 0, h - 0.05, c.ton(_METAL), "fl")
    t += _box(x0 + w - 0.08, x0 + w - 0.04, y0 + 0.03, y1 - 0.03, 0, h - 0.05, c.ton(_METAL), "fr")
    return [t]


def _guichet(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(1.4, 2.2), L - 0.3)
    if w < 0.6:
        return []
    d = min(0.45, 0.35 * P)
    h = min(1.05, 0.55 * H)
    x0 = c.span(w)
    y1 = P - 0.1
    y0 = y1 - d
    bois = c.ton(c.pick(_BOIS))
    c.zone, c.avant = (x0, x0 + w), y0 - 0.05
    corps = _box(x0, x0 + w, y0, y1, 0, h, bois, "ftlr")
    corps += _box(x0, x0 + w, y0 - 0.05, y1, h, h + 0.04, c.ton(c.pick(_PIERRES)), "ftlru")
    verre = _box(x0 + 0.1, x0 + w - 0.1, y0 + 0.08, y0 + 0.1, h + 0.04, min(h + 0.6, H - 0.15),
                 c.ton((190, 215, 225)), "flr")
    return [corps, verre]


def _affichage(c):
    L, H, P = c.L, c.H, c.P
    w, h = min(0.9, 0.4 * L), min(0.6, 0.3 * H)
    z0 = min(H - h - 0.1, 1.2)
    if z0 < 0.1 or w < 0.3:
        return []
    x0 = c.span(w, 0.08)
    t = _bande(x0, x0 + w, P - 0.015, z0, z0 + h, c.ton(c.pick(_BOIS)))
    t += _bande(x0 + 0.03, x0 + w - 0.03, P - 0.02, z0 + 0.03, z0 + h - 0.03, c.ton((196, 160, 110)))
    for k in range(3):
        xf = x0 + 0.06 + k * (w - 0.12) / 3 + c.u(0.0, 0.03)
        zf = z0 + 0.06 + c.u(0.0, 0.5) * (h - 0.3)
        t += _bande(xf, xf + 0.17 * w / 0.9, P - 0.025, zf, zf + 0.15 * h / 0.6, c.ton((240, 236, 226)))
    return [t]


def _horloge(c):
    r = min(0.14, 0.15 * c.H)
    if r < 0.06:
        return []
    cx, cz, y = c.L * c.u(0.3, 0.7), c.H - r - 0.1, c.P - 0.02
    disque = [(cx + r * math.cos(a), y, cz + r * math.sin(a)) for a in
              [2 * math.pi * k / 6 for k in range(6)]]
    t = _face(disque, (0, -1, 0), c.ton((236, 232, 220)))
    t += _bande(cx - 0.005, cx + 0.005, y - 0.005, cz, cz + 0.8 * r, c.ton(_SOMBRE))
    t += _bande(cx, cx + 0.6 * r, y - 0.005, cz - 0.005, cz + 0.005, c.ton(_SOMBRE))
    return [t]


def _console(c):
    L, H, P = c.L, c.H, c.P
    w = min(c.u(0.9, 1.3), 0.55 * L)
    d = min(0.28, 0.3 * P)
    h = min(0.8, 0.55 * H)
    x0 = c.span(w)
    y1 = P - 0.04
    y0 = y1 - d
    bois = c.ton(c.pick(_BOIS))
    c.zone, c.avant = (x0, x0 + w), y0
    t = _box(x0, x0 + w, y0, y1, h - 0.04, h, bois, "ftlru")
    t += _box(x0 + 0.03, x0 + 0.06, y0 + 0.02, y1 - 0.02, 0, h - 0.04, bois, "fl")
    t += _box(x0 + w - 0.06, x0 + w - 0.03, y0 + 0.02, y1 - 0.02, 0, h - 0.04, bois, "fr")
    xv = x0 + w * c.u(0.25, 0.75)
    vase = _prisme(xv, (y0 + y1) / 2, h, h + 0.24, 0.06, 0.035, 6, c.ton(c.pick(_VIFS)))
    chunks = [t, vase]
    zm = h + 0.3
    if zm + 0.4 < H - 0.08:
        mx0, mx1 = x0 + 0.15 * w, x0 + 0.85 * w
        zt = min(H - 0.1, zm + 0.7)
        miroir = _bande(mx0, mx1, c.P - 0.015, zm, zt, c.ton(c.pick(_BOIS)))
        miroir += _bande(mx0 + 0.03, mx1 - 0.03, c.P - 0.02, zm + 0.03, zt - 0.03, c.ton((190, 210, 215)))
        chunks.append(miroir)
    return chunks


def _soleil(c):
    L, H, P = c.L, c.H, c.P
    R = min(0.35 * L, 0.45 * H, 0.9)
    if R < 0.2:
        return []
    cx = L * c.u(0.35, 0.65)
    zc = min(H * 0.45, H - 0.08 - R)
    if zc < 0.2:
        return []
    y = P - 0.012
    n = 6
    t = []
    for i in range(n):
        a0, a1 = math.pi * i / n, math.pi * (i + 1) / n
        col = c.ton((214, 176, 86) if i % 2 == 0 else (150, 60, 80))
        t += _face([(cx, y, zc), (cx + R * math.cos(a0), y, zc + R * math.sin(a0)),
                    (cx + R * math.cos(a1), y, zc + R * math.sin(a1))], (0, -1, 0), col)
    return [t]


def _ampoule(x, y, z, b, lum):
    return _face([(x - b, y - b, z), (x + b, y - b, z), (x + b, y + b, z), (x - b, y + b, z)],
                 (0, 0, -1), lum, True)


def _place_sol(c, marge):
    a, b = c.zone
    cotes = []
    if a >= 0.3:
        cotes.append(max(marge, a / 2))
    if c.L - b >= 0.3:
        cotes.append(c.L - max(marge, (c.L - b) / 2))
    return c.pick(cotes) if cotes else None


def _luminaire(c, genre):
    L, H, P = c.L, c.H, c.P
    lum = c.lueur
    x = _place_sol(c, 0.15) if genre == "sol" else None
    if genre == "sol" and x is None:
        genre = "pendule"
    if genre == "sol":
        cy = P * c.u(0.6, 0.78)
        zs = min(1.5, 0.78 * H)
        metal = c.ton(_METAL)
        pied = _box(x - 0.1, x + 0.1, cy - 0.1, cy + 0.1, 0, 0.03, metal, "ftlr")
        pied += _box(x - 0.012, x + 0.012, cy - 0.012, cy + 0.012, 0.03, zs - 0.2, metal, "flr")
        abat = _prisme(x, cy, zs - 0.2, zs, 0.13, 0.08, 6, c.ton(c.pick(_TISSUS)), haut=False)
        return [pied, abat + _ampoule(x, cy, zs - 0.2, 0.04, lum)]
    R = min(0.18, L / 5, P / 5)
    x = L * c.u(0.3, 0.7)
    cy = P * c.u(0.35, 0.6)
    zs = H * c.u(0.62, 0.8)
    cable = _bande(x - 0.006, x + 0.006, cy, zs, H, c.ton(_SOMBRE))
    if genre == "cage":
        refl = _prisme(x, cy, zs - 0.07, zs, R, R * 0.3, 6, c.ton(c.pick(_EMAILS)), haut=False)
        amp = _prisme(x, cy, zs - 0.17, zs - 0.07, R * 0.3, R * 0.3, 5, lum, True, True)
        return [cable + refl + amp]
    if genre == "lustre":
        s = min(0.22, L / 5, P / 5) / 0.22
        dore = c.ton((200, 168, 90))
        t = cable
        t += _prisme(x, cy, zs - 0.12 * s, zs, 0.2 * s, 0.12 * s, 6, dore, haut=False)
        t += _prisme(x, cy, zs, zs + 0.1 * s, 0.12 * s, 0.05 * s, 6, dore, haut=False)
        for dx in (-0.1 * s, 0.0, 0.1 * s):
            t += _ampoule(x + dx, cy, zs - 0.12 * s, 0.03 * s, lum)
        return [t]
    abat = _prisme(x, cy, zs - 0.15, zs, R, R * 0.4, 6, c.ton(c.pick(_TISSUS)), haut=False)
    return [cable + abat + _ampoule(x, cy, zs - 0.14, 0.04, lum)]


def _piece(c):
    if min(c.L, c.H) < 0.5 or c.P < 0.5:
        return []
    r, f = c.rng, c.famille
    coque = _coque(c)
    seuil = _seuil(c)
    if f == "habitation":
        meubles = _secretaire(c) if r.random() < 0.35 else _canape(c) + _table_basse(c)
        lumiere = _luminaire(c, "sol")
        traitement = _rideaux(c) if r.random() < 0.55 else _persiennes(c)
        extras = _lambris(c)
    elif f == "deco":
        meubles = _console(c)
        lumiere = _luminaire(c, "lustre")
        traitement = _rideaux(c)
        extras = _soleil(c) + _lambris(c)
    elif f == "commerce":
        meubles = _etageres(c)
        lumiere = _luminaire(c, "pendule")
        traitement = _rideau_fer(c) if r.random() < 0.35 else (_rideaux(c) if r.random() < 0.5 else [])
        extras = []
    elif f == "bureau":
        meubles = (_secretaire(c) if r.random() < 0.4 else _bureau(c)) + _classeur(c)
        lumiere = _luminaire(c, "pendule")
        traitement = _persiennes(c) if r.random() < 0.7 else _rideaux(c)
        extras = _lambris(c)
    elif f == "industriel":
        meubles = _etabli(c)
        lumiere = _luminaire(c, "cage")
        traitement = _rideau_fer(c) if r.random() < 0.3 else []
        extras = _poutres(c)
    else:  # public
        meubles = _banc(c) if r.random() < 0.5 else _guichet(c)
        lumiere = _luminaire(c, "pendule")
        traitement = _persiennes(c) if r.random() < 0.3 else []
        extras = _affichage(c) + _horloge(c) + (_poutres(c) if r.random() < 0.5 else []) + _lambris(c)
    return [coque, *seuil, *meubles, *traitement, *lumiere, *extras]


# --------------------------------------------------------------------------
# Mode « retrait » : retours, appui, meneaux, brise-soleil (la vitre est à y = P)
# --------------------------------------------------------------------------
_MENEAUX = {  # pas (m), largeur, faces, probabilité d'une traverse
    "deco": (1.5, 0.025, "flr", 0.4),
    "habitation": (1.1, 0.045, "flr", 0.7),
    "commerce": (2.0, 0.05, "flr", 0.5),
    "bureau": (1.2, 0.04, "flr", 0.3),
    "industriel": (0.6, 0.025, "f", 1.0),
    "public": (1.6, 0.06, "flr", 0.5),
}


def _brise_soleil(c):
    L, H = c.L, c.H
    if H < 1.2 or L < 0.6:
        return []
    nb = 2 if H < 2.0 else 3
    sp = min(0.28, 0.1 * H)
    zt = H - 0.12
    zs = [zt - i * sp for i in range(nb)]
    mat = c.ton(c.pick(_MENUISERIES))
    chunks = [_box(0.02, L - 0.02, -0.12, 0.0, z - 0.025, z, mat, "fu") for z in zs]
    zb = zs[-1] - 0.03
    bras = _face([(0.015, -0.12, zb), (0.015, 0.0, zb), (0.015, 0.0, H - 0.07), (0.015, -0.12, H - 0.07)],
                 (1, 0, 0), mat)
    bras += _face([(L - 0.015, -0.12, zb), (L - 0.015, 0.0, zb), (L - 0.015, 0.0, H - 0.07),
                   (L - 0.015, -0.12, H - 0.07)], (-1, 0, 0), mat)
    return [bras] + chunks


def _retrait(c):
    L, H, P = c.L, c.H, c.P
    pierre = c.pierre()
    retour = _mix(pierre, (0, 0, 0), 0.12)
    appui_h = 0.0 if c.vitrine else 0.05
    chunks = []
    t = _face([(0, 0, appui_h), (0, P, appui_h), (0, P, H), (0, 0, H)], (1, 0, 0), retour)
    t += _face([(L, 0, appui_h), (L, P, appui_h), (L, P, H), (L, 0, H)], (-1, 0, 0), retour)
    t += _face([(0, 0, H), (L, 0, H), (L, P, H), (0, P, H)], (0, 0, -1), _mix(retour, (0, 0, 0), 0.1))
    chunks.append(t)
    if c.vitrine:  # rien au sol : seulement des consoles en tête, saillie <= .12 m
        if H >= 0.9:
            cw = min(0.12, L / 8)
            chunks.append(_box(0, cw, -0.12, 0.0, H - 0.3, H - 0.07, pierre, "ful")
                          + _box(L - cw, L, -0.12, 0.0, H - 0.3, H - 0.07, pierre, "fur"))
    else:
        p = c.u(0.05, 0.1)
        chunks.append(_box(0, L, -p, P, 0, appui_h, pierre, "ftlru"))
    chunks.append(_box(0, L, -0.05, 0.0, H - 0.07, H, pierre, "fu"))

    pas, larg, faces, p_traverse = _MENEAUX[c.famille]
    mat = c.ton(c.pick(_MENUISERIES))
    zb = 2.1 if c.vitrine else appui_h
    zt = H - 0.07
    meneaux, traverse = [], []
    if zt - zb > 0.25:
        n = min(8, int(L / pas))
        xs = sorted((L * (i + 1) / (n + 1) for i in range(n)), key=lambda x: abs(x - L / 2))
        meneaux = [_box(x - larg / 2, x + larg / 2, P - 0.06, P - 0.005, zb, zt, mat, faces) for x in xs]
        if (H > 1.3 or c.vitrine) and c.rng.random() < p_traverse:
            zr = 2.1 if c.vitrine else H * 0.68
            traverse = [_box(0.0, L, P - 0.06, P - 0.005, zr, zr + 0.04, mat, "fu")]
    brise = _brise_soleil(c) if (c.famille == "bureau" or (c.famille in ("public", "industriel")
                                                           and c.rng.random() < 0.4)) else []
    return chunks + meneaux[:1] + traverse + brise + meneaux[1:]


# --------------------------------------------------------------------------
# Mode « corniche » : couronnement dans la bande haute du panneau
# --------------------------------------------------------------------------
def _corniche(c):
    L, H = c.L, c.H
    if L < 0.3:
        return []
    hb = min(0.4 * H, min(0.65, max(0.24, 0.08 * H)))
    p = min(0.12, 0.05 + 0.1 * hb)
    pierre = c.pierre()
    z0 = H - hb
    a = _box(0, L, -0.4 * p, 0.0, z0, H - 0.62 * hb, pierre, "fu")
    b = _box(0, L, -0.7 * p, 0.0, H - 0.62 * hb, H - 0.3 * hb, pierre, "fu")
    tablette = _box(0, L, -p, 0.0, H - 0.3 * hb, H, pierre, "ftulr")
    w = min(0.1, L / 8)
    chunks = [tablette, b, a]
    for k in range(2):
        lo, hi = (0.05, L / 2 - w) if k == 0 else (L / 2, L - w - 0.05)
        x = c.u(lo, hi) if hi > lo else lo
        chunks.append(_box(x, x + w, -0.62 * p, 0.0, z0, H - 0.62 * hb, c.ton(_mix(pierre, (0, 0, 0), 0.1)),
                           "fl" if c.rng.random() < 0.5 else "fr"))
    return chunks


# --------------------------------------------------------------------------
# Assemblage
# --------------------------------------------------------------------------
def _borner(v, c):
    x = min(max(round(v[0], 4), 0.0), c.L)
    y = min(max(round(v[1], 4), Y_MIN), c.P)
    z = min(max(round(v[2], 4), 0.0), c.H)
    return (x, y, z, v[3], v[4], v[5])


def _aire2(t):
    a, b, d = t
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = d[0] - a[0], d[1] - a[1], d[2] - a[2]
    return (uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2


def construire_decor(baie, famille, graine):
    """Liste de triangles ((x,y,z,r,g,b) x3) pour la baie ; voir l'en-tête du module."""
    mode = baie.get("mode")
    if mode not in BUDGETS:
        raise ValueError("mode inconnu : %r" % (mode,))
    if famille not in FAMILLES:
        raise ValueError("famille inconnue : %r" % (famille,))
    c = _Ctx(baie, famille, graine)
    chunks = {"piece": _piece, "retrait": _retrait, "corniche": _corniche}[mode](c)
    budget = BUDGETS[mode]
    retenus = []
    for chunk in chunks:  # par ordre de priorité ; un bloc trop gros est sauté
        if chunk and len(retenus) + len(chunk) <= budget:
            retenus.extend(chunk)
    sortie = []
    for tri in retenus:
        tri = tuple(_borner(v, c) for v in tri)
        if _aire2(tri) > 1e-12:
            sortie.append(tri)
    return sortie
