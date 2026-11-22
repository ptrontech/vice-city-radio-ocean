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

if __name__=="__main__":unittest.main()
