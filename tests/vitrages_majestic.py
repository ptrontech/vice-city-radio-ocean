from hashlib import sha256
import os
from pathlib import Path
from struct import pack, unpack_from
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import maillage_rw as rw
import textures
import vitrages_majestic as verre


class Vitrages(unittest.TestCase):
    def test_six_chaines_completes(self):
        empreintes=set()
        for cle,w,h,_ in verre.MATERIAUX.values():
            for nuit in (False,True):
                n,b=verre.lire_niveaux(verre.ARCHIVES/(verre.nom_natif(cle,nuit)+".bc1"),w,h)
                self.assertEqual(max(w,h).bit_length(),n)
                empreintes.add(sha256(b).digest())
        self.assertEqual(6,len(empreintes))

    def test_matieres_du_quartier_preservees(self):
        v=0x0C02FFFF
        def native(nom):
            data=pack("<II",8,0x1106)+nom.encode().ljust(32,b"\0")+bytes(32)
            data+=pack("<IIHHBBBB",512,0,128,128,16,1,4,1)
            data+=pack("<I",8192)+bytes(8192)
            return textures.wrap(0x15,v,textures.wrap(1,v,data)+textures.wrap(3,v,b""))
        noms=tuple(verre.MATERIAUX)+("autrehotel",)
        contenu=textures.wrap(1,v,pack("<HH",len(noms),8))+b"".join(native(n) for n in noms)+textures.wrap(3,v,b"")
        src=textures.wrap(0x16,v,contenu)
        cible=verre.ajouter_vitrages(src)
        parts=textures.dictionary(cible)[1]
        self.assertEqual(unpack_from("<HH",rw.corps(parts,1)),(10,8))
        anc=list(textures.natives(textures.dictionary(src)[1]))
        result=list(textures.natives(parts))
        self.assertEqual([(n[3],n[4]) for n in anc],[(n[3],n[4]) for n in result[:4]])
        self.assertEqual({x[3] for x in result[4:]},{verre.nom_natif(k,n) for k,*_ in verre.MATERIAUX.values() for n in (False,True)})
        self.assertRaises(ValueError,verre.ajouter_vitrages,cible)


@unittest.skipUnless(os.environ.get("PALMIER_VC_ORIGINE"),"Copie de jeu personnelle facultative")
class VitragesJeu(unittest.TestCase):
    def test_ouvertures_jour_et_nuit(self):
        racine=Path(os.environ["PALMIER_VC_ORIGINE"])
        if racine.name.lower()!="models":
            racine=racine/"models"
        index=(racine/"gta3.dir").read_bytes()
        for nuit in (False,True):
            nom="od_majestic2c_"+("nt" if nuit else "dy")+".dff"
            s,n=next((s,n) for s,n,b in textures.ENTRY.iter_unpack(index) if textures.name(b)==nom)
            with (racine/"gta3.img").open("rb") as f:
                f.seek(s*textures.SECTOR)
                src=f.read(n*textures.SECTOR)
            nouveau=verre.nommer_vitrages(verre.preparer_uv(src),nuit)
            *_,g,m=rw.ouvrir_modele(src)
            *_,gn,mn=rw.ouvrir_modele(nouveau)
            noms=rw.noms_materiaux(m)
            noms_n=rw.noms_materiaux(mn)
            self.assertEqual(g.positions,gn.positions)
            self.assertEqual(g.faces,gn.faces)
            for b,a,id_mat,c in rw.TRI.iter_unpack(g.faces):
                original=noms[id_mat]
                if original in verre.MATERIAUX:
                    self.assertEqual(noms_n[id_mat],verre.nom_natif(verre.MATERIAUX[original][0],nuit))
                    for i in (a,b,c):
                        self.assertTrue(all(0<x<1 for x in verre.UV.unpack_from(gn.uv[0],i*8)))
                else:
                    self.assertEqual(noms_n[id_mat],original)
                    for i in (a,b,c):
                        self.assertEqual(g.uv[0][i*8:i*8+8],gn.uv[0][i*8:i*8+8])
                        self.assertEqual(g.couleurs[i*4:i*4+4],gn.couleurs[i*4:i*4+4])


if __name__=="__main__":
    unittest.main()
