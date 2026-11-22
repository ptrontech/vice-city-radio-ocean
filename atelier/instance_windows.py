"""Réactive l'atelier déjà ouvert dans cette session Windows."""
import ctypes
import os
from ctypes import wintypes


class FenetreUnique:
    def __init__(self):
        self.deja_ouverte = False
        self.handle = None
        if os.name != "nt":
            return
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
        self.kernel.CreateEventW.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.SetEvent.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        ctypes.set_last_error(0)
        self.handle = self.kernel.CreateEventW(None, False, False, r"Local\RadioOcean.AtelierDesIA.v1")
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            self.deja_ouverte = True
            self.kernel.SetEvent(self.handle)
            self.fermer()

    def suivre(self, fenetre):
        """Le double-clic suivant remet cette même fenêtre au premier plan."""
        if not self.handle:
            return

        def relever():
            if not self.handle:
                return
            if self.kernel.WaitForSingleObject(self.handle, 0) == 0:
                fenetre.deiconify()
                fenetre.lift()
                fenetre.focus_force()
            fenetre.after(180, relever)

        def nettoyage(event):
            if event.widget is fenetre:
                self.fermer()

        fenetre.bind("<Destroy>", nettoyage, add="+")
        fenetre.after(180, relever)

    def fermer(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
