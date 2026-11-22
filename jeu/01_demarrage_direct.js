// Signale au lanceur la prise de contrôle ; le passage demandé concerne seulement la première cinématique.
const idDemarrage=N("READ_STRING_FROM_INI_FILE",sessionFile,"atelier","jeton")||"";
const chercherIntro=N("READ_STRING_FROM_INI_FILE",sessionFile,"atelier","introAuto")==="1";
const repriseSauvegardee=N("READ_STRING_FROM_INI_FILE",sessionFile,"atelier","nouvellePartie")==="0";
const origineChronoIntro=Date.now();
let moteurSignale=false, sceneSignalee=false, passeeSignalee=false, jeuSignale=false;
function signalerDemarrage(player,free) {
    if(!idDemarrage || jeuSignale)return;
    if(!moteurSignale) {
        N("WRITE_STRING_TO_INI_FILE",idDemarrage,sessionFile,"atelier","moteur");
        moteurSignale=true;
    }
    if(sceneSignalee && !passeeSignalee && N("WAS_CUTSCENE_SKIPPED")) {
        passeeSignalee=true;
        log("Radio Ocean | cinematique passee, confirmation du moteur");
    }
    if(free && !N("GET_FADING_STATUS")) {
        N("WRITE_STRING_TO_INI_FILE",idDemarrage,sessionFile,"atelier","jouable");
        jeuSignale=true;
        const pos=posOf(player);
        log("Radio Ocean | Tommy jouable, profil "+mode+" | position "+[pos.x,pos.y,pos.z].map(v=>v.toFixed(2)).join(", "));
        return;
    }
    if(!chercherIntro || sceneSignalee || Date.now()-origineChronoIntro>12000 || !ONMISSION || !alive(player))return;
    const pos=posOf(player);
    // Démarrage du seul scénario d'origine, au point de création de Tommy du PC 1.0.
    if(Math.hypot(pos.x-83,pos.y+849.8)>1.5 || Math.abs(pos.z-10.31)>1.5)return;
    const t=N("GET_CUTSCENE_TIME");
    if(t<200 || t>2700 || N("HAS_CUTSCENE_FINISHED"))return;
    N("WRITE_STRING_TO_INI_FILE",idDemarrage+"|"+Date.now(),sessionFile,"atelier","introduction");
    sceneSignalee=true;
    log("Radio Ocean | introduction initiale reconnue");
}
