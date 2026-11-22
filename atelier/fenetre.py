"""Fenêtre principale de « GTA Vice City, amélioration ».

Trois panneaux arrondis (Codex noir, Claude orange, Kimi bleu), un bloc
commun « Moi » (violet) en bas. Fenêtre blanche, redimensionnable.
"""
from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

import agents
import claude_cli
import codex_cli
import kimi_cli
import stockage as stockage_mod
from nouvelles import VeilleNouvelles, dossier_du_projet
from tache import TacheAnnulee, TacheProcessus

COULEUR_FOND = "#ffffff"
COULEUR_MOI = "#7c3aed"
COULEUR_TEXTE = "#111827"
COULEUR_DISCRET = "#6b7280"
COULEUR_TRES_DISCRET = "#9ca3af"
COULEUR_ERREUR = "#dc2626"
RAYON = 18
CONNECTEURS = {"codex": codex_cli, "claude": claude_cli, "kimi": kimi_cli}


def police(taille: int, gras: bool = False, italique: bool = False):
    style = "normal"
    if gras and italique:
        style = "bold italic"
    elif gras:
        style = "bold"
    elif italique:
        style = "italic"
    return ("Segoe UI", taille, style)


def heure_locale(date=None):
    if date:
        try:
            return datetime.fromisoformat(date).astimezone().strftime("%H:%M")
        except (TypeError,ValueError):
            pass
    return datetime.now().strftime("%H:%M")


def _rectangle_arrondi(cnv: tk.Canvas, x1, y1, x2, y2, r, **kw):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cnv.create_polygon(points, smooth=True, **kw)


class PanneauArrondi(tk.Frame):
    """Cadre à coins arrondis tracé sur un Canvas ; self.interieur à remplir."""

    def __init__(self, parent, couleur: str, epaisseur: int = 3):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.couleur = couleur
        self.epaisseur = epaisseur
        self.canvas = tk.Canvas(self, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.interieur = tk.Frame(self.canvas, bg=COULEUR_FOND, highlightthickness=0, bd=0)
        self.fenetre = self.canvas.create_window(0, 0, window=self.interieur, anchor="nw")
        self.canvas.bind("<Configure>", self._ajuster)

    def _ajuster(self, event=None):
        self.canvas.delete("cadre")
        e = self.epaisseur
        largeur = max(self.canvas.winfo_width(), 60)
        hauteur = max(self.canvas.winfo_height(), 60)
        _rectangle_arrondi(
            self.canvas, e, e, largeur - e, hauteur - e, RAYON,
            fill=COULEUR_FOND, outline=self.couleur, width=e, tags="cadre",
        )
        marge = e + 8
        self.canvas.coords(self.fenetre, marge, marge)
        self.canvas.itemconfigure(
            self.fenetre,
            width=max(largeur - 2 * marge, 20),
            height=max(hauteur - 2 * marge, 20),
        )
        self.canvas.tag_lower("cadre")


class PanneauAgent(tk.Frame):
    def __init__(self, parent, application: "Application", info: agents.AgentInfo):
        super().__init__(parent, bg=COULEUR_FOND, highlightthickness=0, bd=0)
        self.app = application
        self.info = info
        self._reponse_en_cours: list[str] = []
        self._tete_posee = False
        self._derniere_activite = ""

        cadre = PanneauArrondi(self, info.couleur)
        cadre.pack(fill="both", expand=True)
        interieur = cadre.interieur
        interieur.grid_columnconfigure(0, weight=1)
        interieur.grid_rowconfigure(1, weight=1)

        entete = tk.Frame(interieur, bg=COULEUR_FOND)
        entete.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(
            entete, text=info.nom, fg=info.couleur, bg=COULEUR_FOND, font=police(13, gras=True)
        ).pack(side="left")
        self.point = tk.Label(entete, text="●", fg=COULEUR_TRES_DISCRET, bg=COULEUR_FOND, font=police(11))
        self.point.pack(side="left", padx=(10, 3))
        self.etat = tk.Label(entete, text="détection…", fg=COULEUR_DISCRET, bg=COULEUR_FOND, font=police(9))
        self.etat.pack(side="left")
        self.bouton_annuler = tk.Button(
            entete, text="Annuler", font=police(9), relief="groove",
            command=lambda: application.annuler(info.cle),
        )
        self.bouton_annuler.pack(side="right")
        self.bouton_annuler.configure(state="disabled")

        self.onglets = ttk.Notebook(interieur)
        self.onglets.grid(row=1,column=0,sticky="nsew")
        milieu = tk.Frame(self.onglets, bg=COULEUR_FOND)
        self.onglets.add(milieu,text="Discussion")
        milieu.grid_columnconfigure(0, weight=1)
        milieu.grid_rowconfigure(0, weight=1)
        self.journal = tk.Text(
            milieu, wrap="word", state="disabled", bg=COULEUR_FOND, fg=COULEUR_TEXTE,
            font=police(10), relief="flat", bd=0, highlightthickness=0,
            spacing3=6, cursor="arrow",
        )
        self.journal.grid(row=0, column=0, sticky="nsew")
        barre = tk.Scrollbar(milieu, command=self.journal.yview)
        barre.grid(row=0, column=1, sticky="ns")
        self.journal.configure(yscrollcommand=barre.set)
        self.journal.tag_configure("entete_moi", foreground=COULEUR_MOI, font=police(10, gras=True))
        self.journal.tag_configure("entete_agent", foreground=info.couleur, font=police(10, gras=True))
        self.journal.tag_configure("systeme", foreground=COULEUR_DISCRET, font=police(9, italique=True))
        self.journal.tag_configure("erreur", foreground=COULEUR_ERREUR, font=police(9))
        self.journal.tag_configure("nouvelle", foreground=COULEUR_MOI, font=police(9, italique=True))

        for widget in (self, cadre, cadre.canvas, entete, milieu, self.journal):
            widget.bind("<MouseWheel>", self._molette)

        chantier = tk.Frame(self.onglets,bg=COULEUR_FOND)
        self.onglets.add(chantier,text="Journal GTA")
        self.journal_projet = tk.Text(chantier,wrap="word",state="disabled",bg=COULEUR_FOND,
                                       fg=COULEUR_TEXTE,font=police(10),relief="flat",padx=7,pady=5)
        defiler = ttk.Scrollbar(chantier,command=self.journal_projet.yview)
        defiler.pack(side="right",fill="y")
        self.journal_projet.pack(side="left",fill="both",expand=True)
        self.journal_projet.configure(yscrollcommand=defiler.set)
        self.journal_projet.tag_configure("moment",foreground=info.couleur,font=police(9,gras=True),spacing1=7)
        self.journal_projet.tag_configure("article",spacing3=7)
        self.onglets.select(milieu)

        pied = tk.Frame(interieur, bg=COULEUR_FOND)
        pied.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        pied.grid_columnconfigure(0,weight=1)
        self.cli = tk.Label(pied, text="", width=1, anchor="w", fg=COULEUR_DISCRET, bg=COULEUR_FOND, font=police(8))
        self.cli.grid(row=0,column=0,sticky="ew")
        self.derniere = tk.Label(pied, text="", fg=COULEUR_DISCRET, bg=COULEUR_FOND, font=police(8))
        self.derniere.grid(row=0,column=2,sticky="e")
        tk.Button(
            pied, text="Nouveau fil", font=police(8), relief="groove",
            command=self.nouveau_fil,
        ).grid(row=0,column=1,padx=(4, 4))

    # ---- journal ---------------------------------------------------------
    def _molette(self, event):
        self.journal.yview_scroll(int(-event.delta / 120) * 3, "units")
        return "break"

    def ecrire(self, tag: str, texte: str) -> None:
        self.journal.configure(state="normal")
        self.journal.insert("end", texte, tag)
        self.journal.see("end")
        self.journal.configure(state="disabled")

    def note(self, texte: str) -> None:
        for ligne in texte.splitlines() or [""]:
            self.ecrire("systeme", f"· {ligne}\n")

    def erreur_affichee(self, texte: str) -> None:
        self.ecrire("erreur", f"✗ {texte}\n")

    def afficher_moi(self, texte: str, date=None) -> None:
        self.onglets.select(0)
        heure = heure_locale(date)
        self.ecrire("entete_moi", f"\n[{heure}] Moi ›\n")
        self.ecrire("corps", texte.rstrip() + "\n")

    def debut_reponse(self, date=None) -> None:
        heure = heure_locale(date)
        self.ecrire("entete_agent", f"\n[{heure}] {self.info.nom} ›\n")
        self._tete_posee = True
        self._reponse_en_cours = []

    def morceau(self, texte: str) -> None:
        if not self._tete_posee:
            self.debut_reponse()
        self._reponse_en_cours.append(texte)
        self.ecrire("corps", texte)

    def activite(self, libelle: str | None) -> None:
        libelle = libelle or "outil"
        if self._derniere_activite == libelle:
            return
        self._derniere_activite = libelle
        self.ecrire("systeme", f"· activité : {libelle}\n")

    def nouvelle(self, nouvelle: dict) -> None:
        titre = nouvelle["titre"].capitalize() or "Nouvelle du projet"
        date = heure_locale(nouvelle["horodatage"]) if nouvelle["horodatage"] else ""
        vue = self.journal_projet
        en_tete = vue.yview()[0] < 0.005
        if not en_tete:
            vue.mark_set("lecture",vue.index("@0,0"))
            vue.mark_gravity("lecture","right")
        vue.configure(state="normal")
        vue.insert("1.0",nouvelle["texte"].rstrip()+"\n","article")
        vue.insert("1.0",f"{date}   {titre}\n","moment")
        vue.configure(state="disabled")
        if en_tete:
            vue.yview_moveto(0)
        else:
            vue.yview("lecture")

    def texte_reponse(self) -> str:
        return "".join(self._reponse_en_cours).strip()

    def fin_reponse(self) -> None:
        self._tete_posee = False
        self._derniere_activite = ""

    # ---- état ------------------------------------------------------------
    def mettre_a_jour_entete(self) -> None:
        info = self.info
        self.point.configure(fg=agents.COULEURS_ETAT[info.etat])
        etat = agents.LIBELLES_ETAT[info.etat]
        if info.etat == agents.Etat.PRET:
            etat = "Réponse reçue" if info.detail == "Réponse reçue" else "CLI disponible"
        self.etat.configure(text=etat)
        if info.exe:
            nom_exe = Path(info.exe).name
            fil = self.app.stockage.session(info.cle)
            fil_txt = " · fil actif" if fil else ""
            version = (info.version or nom_exe).replace("codex-cli ","").replace(" (Claude Code)","")
            self.cli.configure(text=f"{version}{fil_txt}")
        else:
            self.cli.configure(text="aucun exécutable trouvé")

    def nouveau_fil(self) -> None:
        if self.info.etat == agents.Etat.EN_COURS:
            self.note("Impossible pendant une réponse en cours.")
            return
        self.app.stockage.oublier_session(self.info.cle)
        self.app.stockage.enregistrer()
        self.note("Nouveau fil : la prochaine demande démarrera une session vierge.")
        self.mettre_a_jour_entete()


class BlocMoi(tk.Frame):
    def __init__(self, parent, application: "Application"):
        super().__init__(parent, bg=COULEUR_FOND, highlightthickness=0, bd=0)
        self.app = application

        cadre = PanneauArrondi(self, COULEUR_MOI)
        cadre.pack(fill="both", expand=True)
        interieur = cadre.interieur
        interieur.grid_columnconfigure(0, weight=1)
        interieur.grid_rowconfigure(2, weight=1)

        entete = tk.Frame(interieur, bg=COULEUR_FOND)
        entete.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        tk.Label(
            entete, text="Moi", fg=COULEUR_MOI, bg=COULEUR_FOND, font=police(13, gras=True)
        ).pack(side="left")
        tk.Label(
            entete,
            text="Entrée : envoyer · Maj+Entrée : nouvelle ligne · Échap : effacer",
            fg=COULEUR_DISCRET, bg=COULEUR_FOND, font=police(8),
        ).pack(side="right")

        reglages = tk.Frame(interieur, bg=COULEUR_FOND)
        reglages.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        tk.Label(reglages, text="Destinataires :", fg=COULEUR_TEXTE, bg=COULEUR_FOND, font=police(10)).pack(side="left")
        for cle, info in agents.AGENTS.items():
            tk.Checkbutton(
                reglages, text=info.nom, variable=application.cibles[cle], command=application.synchroniser_cibles,
                bg=COULEUR_FOND, activebackground=COULEUR_FOND, fg=info.couleur,
                selectcolor=COULEUR_FOND, activeforeground=info.couleur,
                font=police(10, gras=True), highlightthickness=0, bd=0, padx=8,
            ).pack(side="left")
        tk.Checkbutton(
            reglages, text="Tous", variable=application.tous, command=application.choisir_tous,
            bg=COULEUR_FOND, activebackground=COULEUR_FOND, fg=COULEUR_TEXTE,
            selectcolor=COULEUR_FOND, font=police(10, gras=True),
            highlightthickness=0, bd=0, padx=8,
        ).pack(side="left")
        tk.Button(
            reglages, text="Effacer", font=police(10), relief="groove",
            command=self.effacer,
        ).pack(side="right")
        tk.Button(
            reglages, text="Envoyer", font=police(10, gras=True),
            bg=COULEUR_MOI, fg="white", activebackground="#6d28d9",
            activeforeground="white", relief="flat", padx=14, cursor="hand2",
            command=application.envoyer,
        ).pack(side="right", padx=(0, 6))

        self.saisie = tk.Text(
            interieur, height=4, wrap="word", font=police(11), relief="solid", bd=1,
            fg=COULEUR_TEXTE, highlightthickness=2, highlightbackground="#c4b5fd",
            highlightcolor=COULEUR_MOI,
        )
        self.saisie.grid(row=2, column=0, sticky="nsew")
        self.saisie.bind("<Return>", application.envoyer_si_pas_maj)
        self.saisie.bind("<Escape>", lambda _e: self.effacer())

        statut = tk.Frame(interieur, bg=COULEUR_FOND)
        statut.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self.message = tk.Label(statut, text="", fg=COULEUR_DISCRET, bg=COULEUR_FOND, font=police(8))
        self.message.pack(side="left")
        tk.Button(
            statut, text="Dossier des nouvelles…", font=police(8), relief="groove",
            command=self.choisir_dossier_nouvelles,
        ).pack(side="right")

    def effacer(self):
        self.saisie.delete("1.0", "end")
        return "break"

    def choisir_dossier_nouvelles(self):
        dossier = filedialog.askdirectory(title="Dossier surveillé (nouvelles.jsonl)")
        if dossier:
            self.app.veille.activer(dossier)
            self.app.mettre_a_jour_statut(f"Dossier des nouvelles : {dossier}")


class Application(tk.Tk):
    def __init__(self, dossier_nouvelles: str | None = None):
        super().__init__()
        self.title("Atelier des IA – Vice City")
        if os.name == "nt":
            self.iconbitmap(str(Path(__file__).with_name("atelier.ico")))
        self.configure(bg=COULEUR_FOND)
        self.geometry("1240x820")
        self.minsize(1020, 700)

        self.stockage = stockage_mod.Stockage(agents.DOSSIER_DONNEES / "atelier.json")
        self.stockage.charger()
        self.taches: dict[str, TacheProcessus] = {}
        self._vu_erreur: dict[str, str] = {}
        self.veille = VeilleNouvelles(dossier_nouvelles or dossier_du_projet())
        self._fils_presence: list[threading.Thread] = []

        self.cibles = {cle: tk.BooleanVar(value=cle == "codex") for cle in agents.AGENTS}
        self.tous = tk.BooleanVar(value=False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=4)
        self.grid_rowconfigure(1, weight=1, minsize=205)

        haut = tk.Frame(self, bg=COULEUR_FOND, highlightthickness=0, bd=0)
        haut.grid(row=0, column=0, sticky="nsew", padx=14, pady=(14, 7))
        for colonne in range(3):
            haut.grid_columnconfigure(colonne, weight=1)
        haut.grid_rowconfigure(0, weight=1)
        self.panneaux: dict[str, PanneauAgent] = {}
        marges = ((0, 7), (7, 7), (7, 0))
        for colonne, cle in enumerate(("codex", "claude", "kimi")):
            panneau = PanneauAgent(haut, self, agents.AGENTS[cle])
            panneau.grid(row=0, column=colonne, sticky="nsew", padx=marges[colonne])
            self.panneaux[cle] = panneau

        self.moi = BlocMoi(self, self)
        self.moi.grid(row=1, column=0, sticky="nsew", padx=14, pady=(7, 14))

        self.protocol("WM_DELETE_WINDOW", self.fermer)
        self.restaurer_historique()
        self.mettre_a_jour_statut()
        for panneau in self.panneaux.values():
            panneau.mettre_a_jour_entete()
        self._sonder_presence()
        self._charger_nouvelles(au_demarrage=True)
        self.after(2000, self._boucle_nouvelles)

    # ---- présence locale des CLI (hors-ligne) ------------------------------
    def _sonder_presence(self) -> None:
        def travail():
            agents.resoudre_executables()
            for cle in agents.AGENTS:
                info = agents.AGENTS[cle]
                agents.sonder_version(info)
                try:
                    self.after(0, lambda c=cle: self.panneaux[c].mettre_a_jour_entete())
                except RuntimeError:
                    return
        fil = threading.Thread(target=travail, daemon=True)
        self._fils_presence.append(fil)
        fil.start()

    # ---- historique --------------------------------------------------------
    def restaurer_historique(self) -> None:
        for cle, panneau in self.panneaux.items():
            for message in self.stockage.messages(cle):
                auteur = message.get("auteur")
                texte = str(message.get("texte", ""))
                if message.get("nouvelle"):
                    continue
                if auteur == "moi":
                    panneau.afficher_moi(texte,message.get("date"))
                elif auteur == "agent":
                    panneau.debut_reponse(message.get("date"))
                    panneau.morceau(texte)
                    panneau.fin_reponse()
                else:
                    panneau.note(texte)
            panneau.fin_reponse()

    # ---- envoi -------------------------------------------------------------
    def choisir_tous(self):
        for cible in self.cibles.values():
            cible.set(self.tous.get())

    def synchroniser_cibles(self):
        self.tous.set(all(cible.get() for cible in self.cibles.values()))

    def envoyer_si_pas_maj(self, event):
        if event.state & 0x0001:
            return None
        self.envoyer()
        return "break"

    def envoyer(self) -> None:
        texte = self.moi.saisie.get("1.0", "end").strip()
        if not texte:
            self.mettre_a_jour_statut("Rien à envoyer : saisissez d'abord un message.")
            return
        cibles = list(agents.AGENTS) if self.tous.get() else [c for c, v in self.cibles.items() if v.get()]
        if not cibles:
            self.mettre_a_jour_statut("Choisissez au moins un destinataire (cases à cocher).")
            return
        if any(agents.AGENTS[c].exe and agents.AGENTS[c].etat != agents.Etat.EN_COURS for c in cibles):
            self.moi.saisie.delete("1.0", "end")
        for cle in cibles:
            info = agents.AGENTS[cle]
            panneau = self.panneaux[cle]
            if info.etat == agents.Etat.EN_COURS:
                panneau.note("Message non envoyé : cet agent est déjà en cours de réponse.")
                continue
            if not info.exe:
                info.etat = agents.Etat.ABSENT
                info.detail = "exécutable introuvable"
                panneau.note("Message non envoyé : CLI introuvable sur ce PC.")
                panneau.mettre_a_jour_entete()
                continue
            panneau.afficher_moi(texte)
            self.stockage.ajouter_message(cle, "moi", texte)
            self._demarrer_tache(cle, texte)
        self.stockage.enregistrer()
        self.mettre_a_jour_statut()

    def _demarrer_tache(self, cle: str, message: str) -> None:
        info = agents.AGENTS[cle]
        connecteur = CONNECTEURS[cle]
        panneau = self.panneaux[cle]
        reprise = self.stockage.session(cle)
        try:
            tache = TacheProcessus(
                connecteur.construire_commande(info.exe, message, reprise),
                cwd=agents.dossier_conversation(cle),
            )
            tache.demarrer()
        except Exception as exc:
            info.etat = agents.Etat.ERREUR
            info.detail = f"lancement impossible ({type(exc).__name__})"
            panneau.erreur_affichee(f"Lancement impossible : {exc}")
            panneau.mettre_a_jour_entete()
            return
        self.taches[cle] = tache
        self._vu_erreur[cle] = ""
        info.etat = agents.Etat.EN_COURS
        info.detail = "réponse en cours" + (" (reprise du fil local)" if reprise else " (nouveau fil)")
        panneau.mettre_a_jour_entete()
        panneau.bouton_annuler.configure(state="normal")
        panneau.debut_reponse()
        ctx = agents.nouveau_contexte()

        def travail():
            code = None
            try:
                for ligne in tache.lignes():
                    for action in connecteur.traiter_ligne(ligne, ctx):
                        self.after(0, lambda a=action, c=cle: self._appliquer(c, a))
                code = tache.attendre()
                if cle == "kimi" and code == 0 and not ctx.get("session"):
                    ctx["session"] = reprise or kimi_cli.derniere_session(info.exe,tache.cwd)
            except TacheAnnulee:
                self.after(0, lambda c=cle: self._sur_annulation(c))
                return
            except Exception as exc:
                self.after(0, lambda e=exc, c=cle: self._sur_panne(c, e))
                return
            self.after(0, lambda c=cle, co=code, cx=ctx: self._terminer(c, co, cx))

        threading.Thread(target=travail, daemon=True).start()

    def _appliquer(self, cle: str, action: tuple) -> None:
        type_action, valeur = action
        panneau = self.panneaux[cle]
        if type_action == "texte":
            panneau.morceau(str(valeur))
        elif type_action == "session":
            self.stockage.fixer_session(cle, str(valeur))
        elif type_action == "activite":
            panneau.activite(str(valeur) if valeur else None)
        elif type_action == "erreur":
            self._vu_erreur[cle] = str(valeur)
            panneau.erreur_affichee(agents.classer_erreur(valeur)[1])
        elif type_action == "brut":
            panneau.note(str(valeur)[:200])
        elif type_action == "fin_tour":
            panneau.fin_reponse()

    def _terminer(self, cle: str, code: int | None, ctx: dict) -> None:
        info = agents.AGENTS[cle]
        panneau = self.panneaux[cle]
        tache = self.taches.pop(cle, None)
        reponse = panneau.texte_reponse()
        panneau.fin_reponse()
        if ctx.get("session"):
            self.stockage.fixer_session(cle, ctx["session"])

        texte_erreur = ""
        if tache is not None:
            err = tache.stderr_texte().strip()
            if code not in (0, None):
                texte_erreur = err or f"le processus s'est terminé avec le code {code}"
            elif err and not reponse:
                texte_erreur = err

        texte_erreur = self._vu_erreur.get(cle) or texte_erreur
        if texte_erreur:
            etat, message = agents.classer_erreur(texte_erreur)
            info.etat = etat
            info.detail = message
            if reponse:
                panneau.note(message)
            else:
                panneau.erreur_affichee(message)
        elif not reponse:
            info.etat = agents.Etat.ERREUR
            info.detail = "Aucune réponse reçue"
            panneau.erreur_affichee(info.detail)
        else:
            info.etat = agents.Etat.PRET
            info.detail = "Réponse reçue"
            maintenant = datetime.now().strftime("%H:%M")
            panneau.derniere.configure(text=f"Réponse {maintenant}")
            if reponse:
                self.stockage.ajouter_message(cle, "agent", reponse)
        if ctx.get("bruts") and not reponse:
            panneau.note("Sortie reçue mais non reconnue : aucune réponse affichée.")
        panneau.bouton_annuler.configure(state="disabled")
        panneau.mettre_a_jour_entete()
        self.stockage.enregistrer()

    def _sur_annulation(self, cle: str) -> None:
        self.taches.pop(cle, None)
        info = agents.AGENTS[cle]
        panneau = self.panneaux[cle]
        info.etat = agents.Etat.PRET
        info.detail = (f"CLI présent — {info.version}" if info.version else "CLI présent")
        panneau.note("Envoi annulé.")
        panneau.fin_reponse()
        panneau.bouton_annuler.configure(state="disabled")
        panneau.mettre_a_jour_entete()

    def _sur_panne(self, cle: str, exc: Exception) -> None:
        self.taches.pop(cle, None)
        info = agents.AGENTS[cle]
        panneau = self.panneaux[cle]
        etat, message = agents.classer_erreur(f"{type(exc).__name__} : {exc}")
        info.etat = etat
        info.detail = message
        panneau.erreur_affichee(message)
        panneau.fin_reponse()
        panneau.bouton_annuler.configure(state="disabled")
        panneau.mettre_a_jour_entete()

    def annuler(self, cle: str) -> None:
        tache = self.taches.get(cle)
        if tache is not None:
            tache.annuler()

    # ---- nouvelles locales ---------------------------------------------------
    def _charger_nouvelles(self,au_demarrage=False) -> None:
        avec_nouvelles = set()
        nouvelles = self.veille.lire_nouveau()
        for nouvelle in nouvelles:
            cibles = [nouvelle["source"]] if nouvelle["source"] in self.panneaux else list(self.panneaux)
            for cle in cibles:
                self.panneaux[cle].nouvelle(nouvelle)
                avec_nouvelles.add(cle)
        if au_demarrage:
            for cle in avec_nouvelles:
                if not self.stockage.messages(cle):
                    self.panneaux[cle].onglets.select(1)

    def _boucle_nouvelles(self) -> None:
        self._charger_nouvelles()
        self.after(2000, self._boucle_nouvelles)

    # ---- statut / fermeture ----------------------------------------------------
    def mettre_a_jour_statut(self, message: str = "") -> None:
        if self.veille.actif:
            nouvelles = "Journal GTA en direct"
        else:
            nouvelles = "Choisissez un dossier pour suivre les nouvelles du projet."
        self.moi.message.configure(text=message or nouvelles)

    def fermer(self) -> None:
        for tache in list(self.taches.values()):
            tache.annuler()
        self.stockage.enregistrer()
        self.destroy()
