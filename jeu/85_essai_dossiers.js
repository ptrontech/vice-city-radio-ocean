// Parcours réservé à Validation. Le jeu dirige le chargement des personnages et de la collision.
let docEtape=0,docIndex=0,docDepuis=0,docAvant=null,docAjuste=false;
function docSuite(etape){docEtape=etape;docDepuis=Date.now();}
function testDossiers(p,free){
    if(!free || docEtape===99)return;
    if(docEtape===0){
        if(!testAppuisQuai(p,free))return;
        verdict("appuis du nouveau quartier avant les rencontres",appuisQuaiReussis());
        docSuite(1);return;
    }
    const pos=posOf(p),age=Date.now()-docDepuis;
    if(age>37000){
        verdict("dossier bloque index="+docIndex+" etape="+docEtape+" position="+JSON.stringify(pos),false);
        docSuite(99);return;
    }
    const d=dossiersVice[docIndex];
    switch(docEtape){
    case 1:
        if(!d){
            verdict("cinq dossiers presents dans la sauvegarde",state.dossiers===31 && readState().dossiers===31);
            report("FIN dossiers des cinq factions masque="+state.dossiers);docSuite(99);return;
        }
        if(state.dossiers&d.bit){docIndex++;return;}
        testMove(p,contact);docSuite(2);return;
    case 2:
        if(age<850 || !near(pos,contact,6))return;
        docAvant={...state};
        if(!verdict("rendez-vous propose "+d.groupe,commencerDossier(d.id,pos))){docSuite(99);return;}
        report("point de rencontre "+d.id+" "+mission.point.join(","));
        const point=mission.point;
        N("REQUEST_COLLISION",point[0],point[1]);
        N("SET_CHAR_COORDINATES",p,point[0]+1.3,point[1],point[2]+.6);
        docAjuste=false;docSuite(3);return;
    case 3:
        if(!mission || !alive(mission.acteur))return;
        if(!temoinProche(pos) && age>2300 && !docAjuste){
            const q=posOf(mission.acteur);
            N("SET_CHAR_COORDINATES",p,q.x+1.25,q.y,q.z+.15);docAjuste=true;return;
        }
        if(!temoinProche(pos))return;
        openMenu("temoin");docSuite(4);return;
    case 4:
        if(age<650)return;
        if(!verdict("temoignage enregistre de "+d.nom,enregistrerTemoin(pos) && !enregistrerTemoin(pos) && state.caisse===docAvant.caisse)){
            docSuite(99);return;
        }
        testMove(p,contact);docSuite(5);return;
    case 5:
        if(age<850 || !near(pos,contact,6))return;
        const droits=(docAvant.local?cfg.revenu:0)+propertyIncome(docAvant)+revenuEquipe(docAvant);
        if(!verdict("diffusion unique "+d.groupe,remettreDossier(pos) && !remettreDossier(pos) &&
            state.caisse===docAvant.caisse+d.prime && state.missions===docAvant.missions+1 &&
            state.reserve===docAvant.reserve+droits && state.dossiers===(docAvant.dossiers|d.bit))){
            docSuite(99);return;
        }
        docIndex++;docSuite(1);return;
    }
}
