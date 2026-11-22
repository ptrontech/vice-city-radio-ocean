"""Reprise native de Vice City et ouverture de sa fenêtre Windows, limitée à ce processus."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import struct
import time
import uuid

NOMS_SLOTS = tuple(f"GTAVCsf{i}.b" for i in range(1, 9))
ERREURS_INIT = {0xC0000005, 0xC000041D}
if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fenetre_enum = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [fenetre_enum, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
        wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    kernel.GetPrivateProfileStringW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.LPWSTR, wintypes.DWORD, wintypes.LPCWSTR]

    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi.CreateCompatibleBitmap.restype = wintypes.HANDLE
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.PatBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi.GetPixel.restype = wintypes.DWORD
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]


def environnement_jeu(environ=None):
    # Même prise en charge de la surface 16 bits et du DPI que celle appliquée par Windows sur le PC de validation.
    # Les réglages vivent dans l'environnement du seul processus GTA lancé.
    env = (os.environ if environ is None else environ).copy()
    options = env.get("__COMPAT_LAYER", "").split()
    deja = {item.casefold() for item in options}
    if "dwm8and16bitmitigation" not in deja:
        options.append("DWM8And16BitMitigation")
    if not deja.intersection({"highdpiaware", "dpiunaware", "gdidpiscaling"}):
        options.append("HIGHDPIAWARE")
    env["__COMPAT_LAYER"] = " ".join(options)
    return env


def documents_originaux():
    # CSIDL_PERSONAL suit aussi la redirection du dossier Documents du joueur.
    if os.name != "nt":
        return None
    dest = ctypes.create_unicode_buffer(32768)
    hr = ctypes.WinDLL("shell32").SHGetFolderPathW(None, 5, None, 0, dest)
    return Path(dest.value) / "GTA Vice City User Files" if hr == 0 and dest.value else None


def sauvegarde_valide(path):
    """La sauvegarde PC contient ses blocs et la somme native sur les octets précédents."""
    try:
        if not path.is_file() or not 65536 <= path.stat().st_size <= 1048576:
            return False
        data = path.read_bytes()
    except OSError:
        return False
    head = struct.unpack_from("<I", data)[0]
    return 64 < head < len(data)-4 and sum(data[:-4]) & 0xFFFFFFFF == struct.unpack_from("<I",data,len(data)-4)[0]


def reprise(mode, dossier, automatique, slot=None):
    if slot is not None:
        if slot not in range(-1,10):
            raise ValueError("Emplacement de sauvegarde inconnu.")
        return slot
    if mode == "Validation":
        return 9
    if not automatique:
        return -1 if mode == "Campagne" else 9
    existants = [dossier / nom for nom in NOMS_SLOTS if (dossier / nom).is_file()]
    if not existants and mode == "Campagne":
        source = documents_originaux()
        if source and source.resolve() != dossier.resolve():
            # Une campagne neuve peut reprendre la partie personnelle sans modifier son original.
            for nom in NOMS_SLOTS:
                ancien, cible = source / nom, dossier / nom
                if not sauvegarde_valide(ancien):
                    continue
                tmp = dossier / (nom + "." + uuid.uuid4().hex + ".tmp")
                try:
                    shutil.copy2(ancien,tmp)
                    if not sauvegarde_valide(tmp):
                        raise OSError("La copie de la sauvegarde est incomplète.")
                    try:
                        if os.name == "nt":
                            os.rename(tmp,cible)
                        else:
                            os.link(tmp,cible)
                    except FileExistsError:
                        pass
                finally:
                    tmp.unlink(missing_ok=True)
            existants = [dossier / nom for nom in NOMS_SLOTS if (dossier / nom).is_file()]
    valides = [f for f in existants if sauvegarde_valide(f)]
    if valides:
        # Indiquer précisément le dernier emplacement valide, même si un autre fichier est abîmé.
        recent = max(valides,key=lambda f:(f.stat().st_mtime_ns,-NOMS_SLOTS.index(f.name)))
        return NOMS_SLOTS.index(recent.name)+1
    # Ne jamais transformer un profil avec fichiers illisibles en nouvelle partie silencieuse.
    return -1 if existants else 9


def signature_log(chemin):
    try:
        info=chemin.stat()
        return info.st_mtime_ns,info.st_size
    except OSError:
        return None


def echec_avant_moteur(code,moteur,chemin,avant):
    if moteur or (code & 0xFFFFFFFF) not in ERREURS_INIT:
        return False
    if signature_log(chemin)!=avant:
        try:
            if 'New event received: "init runtime"' in chemin.read_text(encoding="utf-8",errors="replace"):
                return False
        except OSError:
            pass
    return True


def valeur_session(fichier, cle):
    buf=ctypes.create_unicode_buffer(128)
    kernel.GetPrivateProfileStringW("atelier",cle,"",buf,len(buf),str(fichier))
    return buf.value


def fenetre_jeu(pid):
    hwnd_trouve = []
    @fenetre_enum
    def verifier(hwnd,_):
        owner=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value!=pid or not user32.IsWindowVisible(hwnd):
            return True
        titre=ctypes.create_unicode_buffer(160)
        user32.GetWindowTextW(hwnd,titre,len(titre))
        if titre.value.startswith("GTA: Vice City"):
            hwnd_trouve.append(hwnd)
        return True
    user32.EnumWindows(verifier,0)
    return hwnd_trouve[0] if len(hwnd_trouve)==1 else None


def presenter(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd,9)
    if user32.GetForegroundWindow()!=hwnd:
        user32.SetForegroundWindow(hwnd)
    return user32.GetForegroundWindow()==hwnd


def cible_active(hwnd, pid):
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    return owner.value == pid and user32.GetForegroundWindow() == hwnd


def avant_runtime(log, ancienne_signature):
    if signature_log(log) == ancienne_signature:
        return False
    try:
        contenu = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return 'for boot scripts at ' in contenu and '"init runtime"' not in contenu and 'host shut down' not in contenu


def ecran_noir(hwnd):
    # PrintWindow copie uniquement la zone cliente du jeu. Le fond blanc distingue une capture vide.
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)) or rect.right < 320 or rect.bottom < 200:
        return False
    dc = user32.GetDC(hwnd)
    if not dc:
        return False
    copie = bmp = ancien = None
    try:
        copie = gdi.CreateCompatibleDC(dc)
        bmp = gdi.CreateCompatibleBitmap(dc, rect.right, rect.bottom)
        if not copie or not bmp:
            return False
        ancien = gdi.SelectObject(copie, bmp)
        gdi.PatBlt(copie, 0, 0, rect.right, rect.bottom, 0x00FF0062)
        if not user32.PrintWindow(hwnd, copie, 3):
            return False
        for x in (1, 3, 5, 7, 9):
            for y in (1, 3, 5, 7, 9):
                px = gdi.GetPixel(copie, rect.right*x//10, rect.bottom*y//10)
                if max(px & 255, (px >> 8) & 255, (px >> 16) & 255) > 12:
                    return False
        return True
    finally:
        if ancien:
            gdi.SelectObject(copie, ancien)
        if bmp:
            gdi.DeleteObject(bmp)
        if copie:
            gdi.DeleteDC(copie)
        user32.ReleaseDC(hwnd, dc)


def appui_fenetre(hwnd, pid, down, up, bouton, pos, relache, duree):
    if not cible_active(hwnd, pid):
        return False
    reponse = ctypes.c_size_t()
    if not user32.SendMessageTimeoutW(hwnd, 0, 0, 0, 2, 80, ctypes.byref(reponse)):
        return False
    if not user32.PostMessageW(hwnd, down, bouton, pos):
        return False
    time.sleep(duree)
    # Un relâchement ne peut cibler que la même fenêtre et son propriétaire initial.
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    if owner.value == pid:
        user32.PostMessageW(hwnd, up, 0 if down == 0x201 else bouton, relache)
    return True


def espace_cinematique(hwnd, pid):
    return appui_fenetre(hwnd, pid, 0x100, 0x101, 0x20, 0x00390001, 0xc0390001, .12)


def passer_ecran_noir(hwnd, pid, log, avant, fichier, jeton):
    def toujours_avant():
        return cible_active(hwnd, pid) and valeur_session(fichier, "moteur") != jeton and avant_runtime(log, avant)
    rect = wintypes.RECT()
    if not toujours_avant() or not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return False, False
    centre = ((rect.bottom//2) << 16) | (rect.right//2)
    clic = appui_fenetre(hwnd, pid, 0x201, 0x202, 1, centre, centre, .06)
    if not clic:
        return False, False
    time.sleep(.25)
    espace = toujours_avant() and ecran_noir(hwnd) and espace_cinematique(hwnd, pid)
    return True, espace


def accompagner(proc, fichier, jeton, rapide, gestion_focus, noir_visible, log, avant, journal):
    debut = time.monotonic()
    activation_tentee = not gestion_focus
    commande = False
    noir_traite = not noir_visible
    moteur = False
    confirmations = 0
    prochain = 4
    while proc.poll() is None and time.monotonic()-debut < 150:
        delai = time.monotonic()-debut
        if not moteur and valeur_session(fichier, "moteur") == jeton:
            moteur = True
            journal(f"moteur initialise {delai:.1f} s")
        if valeur_session(fichier, "jouable") == jeton:
            if not activation_tentee:
                hwnd = fenetre_jeu(proc.pid)
                if hwnd:
                    journal(f"activation fenetre GTA={presenter(hwnd)} apres {delai:.1f} s")
            journal(f"Tommy jouable {delai:.1f} s")
            return True
        marque = valeur_session(fichier, "introduction").split("|") if rapide and not commande else []
        scene = len(marque) == 2 and marque[0] == jeton and marque[1].isdigit()
        verifier_noir = not noir_traite and not moteur and delai >= prochain
        a_activer = not activation_tentee and (moteur or delai >= 4)
        hwnd = fenetre_jeu(proc.pid) if a_activer or verifier_noir or scene else None
        if hwnd and a_activer:
            activation_tentee = True
            journal(f"activation fenetre GTA={presenter(hwnd)} apres {delai:.1f} s")
        if verifier_noir:
            prochain = delai+.5
            noir = hwnd and cible_active(hwnd,proc.pid) and avant_runtime(log,avant) and ecran_noir(hwnd)
            confirmations = confirmations+1 if noir else 0
            if confirmations >= 2:
                clic, espace = passer_ecran_noir(hwnd,proc.pid,log,avant,fichier,jeton)
                noir_traite = clic
                journal(f"ecran noir avant moteur a {delai:.1f} s : clic={clic} espace={espace}")
        if scene and hwnd and 0 <= time.time()*1000-int(marque[1]) <= 450 and cible_active(hwnd,proc.pid):
            commande = espace_cinematique(hwnd,proc.pid)
            if commande:
                journal("espace cible pendant la cinematique initiale")
        time.sleep(.10)
    return moteur
