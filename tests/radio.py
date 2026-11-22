from contextlib import closing
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
from radio import answer, read_ini, serve_once, write_ini

class RadioTests(unittest.TestCase):
    def test_mode_hors_ligne(self):
        ctx={"missions":3,"propriete":1}
        with patch("radio.urllib.request.urlopen",side_effect=TimeoutError):
            reply,intent,origin=answer("Et mon local ?",ctx,[],"modele")
        self.assertEqual((intent,origin),("local","secours"))
        self.assertTrue(reply)

    def test_contexte_employe_et_intention_non_autorisee(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with closing(sqlite3.connect(root/"radio.sqlite3")) as db:
                db.execute("CREATE TABLE echanges(id TEXT PRIMARY KEY,question TEXT,reponse TEXT,intention TEXT,origine TEXT)")
                write_ini(root/"requetes.ini",{"question":"Que fait Rafa ?","contexte":"8,650,1,1,5,450,3,1","id":"radio-test-2"})
                response=io.BytesIO(json.dumps({"message":{"content":json.dumps({"replique":"Rafa travaille a la radio.","intention":"acheter"})}}).encode())
                with patch("radio.urllib.request.urlopen",return_value=response) as http:
                    serve_once(root,db,"local")
                outbound=json.loads(http.call_args.args[0].data)
                facts=json.loads(outbound["messages"][1]["content"])
                self.assertEqual(facts["rafa_en_regie"],1)
                self.assertTrue(facts["droit_ocean_view"] and facts["droit_centre_commercial"])
                self.assertEqual(read_ini(root/"reponses.ini")["intention"],"aucune")

    def test_question_rejouee_apres_fermeture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            db=sqlite3.connect(root/"radio.sqlite3")
            try:
                db.execute("CREATE TABLE echanges(id TEXT PRIMARY KEY, question TEXT, reponse TEXT, intention TEXT, origine TEXT)")
                write_ini(root/"requetes.ini",{"question":"Une emission ?","contexte":"4,660,1,1,1,0","id":"radio-test-1"})
                with patch("radio.answer",return_value=("Un direct ce soir.", "livraison", "ollama")) as model:
                    serve_once(root,db,"local")
                    first=(root/"reponses.ini").read_bytes()
                    (root/"reponses.ini").unlink()
                    serve_once(root,db,"local")
                    self.assertEqual(model.call_count,1)
                self.assertEqual(first,(root/"reponses.ini").read_bytes())
                out=read_ini(root/"reponses.ini")
                self.assertEqual("".join(out[f"ligne{i}"] for i in range(4)).replace("_"," "),"Un direct ce soir.")
                self.assertEqual(db.execute("SELECT COUNT(*) FROM echanges").fetchone()[0],1)
            finally:db.close()

    def test_ancienne_base_conserve_recrutement_apres_plus_de_trois_dialogues(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with closing(sqlite3.connect(folder/"radio.sqlite3")) as db:
                db.execute("CREATE TABLE echanges(id TEXT PRIMARY KEY,question TEXT,reponse TEXT,intention TEXT,origine TEXT)")
                for index in range(5):
                    write_ini(folder/"requetes.ini", {"id": f"historique-{index}",
                              "question": "Le recrutement ?", "contexte": f"3,600,0,{int(index == 0)},0,0"})
                    with patch("radio.answer", return_value=("Entendu.", "aucune", "secours")):
                        serve_once(folder, db, "local")
            with closing(sqlite3.connect(folder/"radio.sqlite3")) as db:
                write_ini(folder/"requetes.ini", {"id":"apres-reouverture", "question":"Tu te souviens de Rafa ?",
                          "contexte":"3,600,0,0,0,0"})
                with patch("radio.answer", return_value=("Il a accompagne la radio.", "aucune", "ollama")) as model:
                    serve_once(folder, db, "local")
                _, facts, last_three, _ = model.call_args.args
                bogus = io.BytesIO(json.dumps({"message":{"content":json.dumps(
                    {"replique":"Il est toujours au comptoir.","intention":"acheter"})}}).encode())
                with patch("radio.urllib.request.urlopen", return_value=bogus):
                    line, intent, origin = answer("Tu te souviens de Rafa ?",facts,[],"local")
                self.assertIn("aucun garde",line)
                self.assertNotIn("comptoir",line)
                self.assertEqual((intent,origin),("aucune","secours"))
                self.assertEqual(len(last_three), 3)
                self.assertEqual(facts["gardes"], 0)
                self.assertTrue(any("Rafa" in fact for fact in facts["souvenirs_confirmes"]))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM souvenirs WHERE code='rafa'").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM echanges").fetchone()[0], 6)

    def test_baux_observes_entre_dialogues_et_allegations_ignorees(self):
        from radio import observe_save
        with tempfile.TemporaryDirectory() as tmp, closing(sqlite3.connect(":memory:")) as db:
            folder = Path(tmp)
            db.execute("CREATE TABLE echanges(id TEXT PRIMARY KEY,question TEXT,reponse TEXT,intention TEXT,origine TEXT)")
            # Véritable encodage v2 de la radio. Seul le premier emplacement a une somme valide.
            write_ini(folder/"progression.ini", {"a":"2,9,8,1210,1,0,5,85,2,0~1xughvh", "b":"2,8,25,1210,1,1,5,85,3,0~0"})
            with db:
                observe_save(db, folder)
                observe_save(db, folder)
            write_ini(folder/"requetes.ini", {"id":"droit-historique", "question":"J'ai achete la suite et recrute Rafa !",
                      "contexte":"8,1000,1,0,5,85,0,0"})
            with patch("radio.answer", return_value=("Parlons de la radio.", "aucune", "ollama")) as model:
                serve_once(folder, db, "local")
            facts=model.call_args.args[1]
            self.assertFalse(facts["droit_centre_commercial"])
            self.assertIn("La radio a signe le bail du rayon de cassettes au North Point Mall.",facts["souvenirs_confirmes"])
            codes={row[0] for row in db.execute("SELECT code FROM souvenirs")}
            self.assertEqual(codes, {"regie","disquaire","trois","huit"})

    def test_v3_dossiers_et_reponse_sans_inventer_une_rencontre(self):
        from radio import fallback, observe_save, observe
        with tempfile.TemporaryDirectory() as tmp, closing(sqlite3.connect(":memory:")) as db:
            folder = Path(tmp)
            write_ini(folder/"progression.ini", {"a":"3,20,13,2210,1,1,10,1600,3,0,15~gqu31q"})
            observe_save(db,folder)
            faits={"missions":13,"propriete":1,"souvenirs_confirmes":observe(db,13,1,1,3)}
            self.assertIn("Drita Kodra",fallback(faits,"Tu te souviens de Kodra ?")[0])
            self.assertIn("aucune diffusion",fallback(faits,"On a deja diffuse Pablo Escobar ?")[0])
            write_ini(folder/"progression.ini", {"a":"3,21,14,3010,1,1,11,1830,3,0,31~sa7df"})
            observe_save(db,folder)
            faits["souvenirs_confirmes"]=observe(db,14,1,1,3)
            ligne,intention=fallback(faits,"Tu te souviens de Pablo ?")
            self.assertIn("diffuse le temoignage de Pablo Escobar",ligne)
            self.assertEqual(intention,"aucune")

if __name__=="__main__":unittest.main()
