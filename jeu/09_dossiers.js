// Série de reportages de fiction. Les rendez-vous et le carnet appartiennent au mod.
const dossiersVice = [
    {id:"kodra", bit:1, groupe:"Maison Kodra", origine:"mafia albanaise", nom:"Drita Kodra",
        lieu:"Downtown", point:[-560,610,12], modele:67, type:5, prime:280,
        parole:"Drita retourne une vieille photo. Sur les enseignes on lit encore le nom de mon pere. A la radio, lis aussi les noms des gens qui travaillent ici."},
    {id:"volna", bit:2, groupe:"Cercle Volna", origine:"mafia russe", nom:"Viktor Orlov",
        lieu:"Vice Point", point:[392,842,12], modele:56, type:4, prime:280,
        parole:"Viktor baisse le son d'un transistor. Les dockers reconnaissent le lacet de mon bateau au bruit des amarres. Tu veux leur histoire ? Enregistre le port a six heures."},
    {id:"faroles", bit:4, groupe:"Los Faroles", origine:"mafia portoricaine", nom:"Marisol Vega",
        lieu:"Little Havana", point:[-944,-535,12], modele:21, type:5, prime:280,
        parole:"Marisol pose une vieille affiche sur la table. Avant que les journaux parlent de nous, on jouait ici tous les vendredis. Mets un morceau de ce groupe dans ton emission."},
    {id:"mangle", bit:8, groupe:"Cartel del Mangle", origine:"cartel mexicain", nom:"Emilio Rios",
        lieu:"Viceport", point:[-802,-1002,12], modele:15, type:4, prime:280,
        parole:"Emilio retourne le disque et montre une dedicace. Tout le monde regarde les grandes villas. Ecoute plutot ce que les quais racontent quand les grues se taisent."},
    {id:"medellin", bit:16, groupe:"Cartel de Medellin", origine:"cartel colombien", nom:"Pablo Escobar",
        lieu:"Nouveau quai de Little Havana", modele:52, type:4, prime:800,
        parole:"Dans cette fiction, Pablo Escobar rejoint Tommy au bout du ponton. Tu as deja quatre voix sur ta bande. Laisse tourner le micro. Ce que disent les autres de moi fait aussi partie de l'histoire."}
];
function dossierDisponible(d){
    return state.missions>=1 && !(state.dossiers&d.bit) && (d.bit!==16 || (state.dossiers&15)===15);
}
function finDossier(m){
    if(!m || m.kind!=="dossier")return;
    removePed(m.acteur);m.acteur=null;
    if(m.modeleDemande){N("MARK_MODEL_AS_NO_LONGER_NEEDED",m.fiche.modele);m.modeleDemande=false;}
}
function lieuDossier(d){
    if(d.bit===16)return quaiRendezvous.slice();
    const p=N("GET_CLOSEST_CHAR_NODE",...d.point);
    if(!p || ![p.nodeX,p.nodeY,p.nodeZ].every(Number.isFinite) ||
        Math.hypot(p.nodeX-d.point[0],p.nodeY-d.point[1])>135)return null;
    return [p.nodeX,p.nodeY,p.nodeZ+1];
}
function commencerDossier(id,pos){
    const fiche=dossiersVice.find(d=>d.id===id), joueur=N("GET_PLAYER_CHAR",0);
    if(!fiche || mission || ONMISSION || !dossierDisponible(fiche) || !near(pos,contact,8) || N("IS_CHAR_IN_ANY_CAR",joueur))return false;
    const point=lieuDossier(fiche);
    if(!point){say("Le rendez-vous est indisponible. Reviens voir Ines.");return false;}
    mission={kind:"dossier",fiche,point,step:0,acteur:null,modeleDemande:false,stop:clockNow()+12*60*1000};
    target(point);menu="";say(briefDossier(mission));return true;
}
function briefDossier(m){
    return m.step===0?"Les voix de Vice. Retrouve "+m.fiche.nom+" a pied. Quartier "+m.fiche.lieu+".":"Rapporte a Ines la bande de "+m.fiche.nom+", sur Ocean Drive.";
}
function tickDossier(pos){
    const m=mission;
    if(!m || m.kind!=="dossier" || m.step!==0)return;
    if(m.acteur!==null){
        if(!alive(m.acteur)){cancelJob("Le rendez-vous a tourne court. Ines pourra le reprogrammer.");return;}
        if(!near(pos,m.point,110))finDossier(m);
        return;
    }
    if(!near(pos,m.point,72) || (m.fiche.bit===16 && !quaiReady()))return;
    if(!m.modeleDemande){N("REQUEST_MODEL",m.fiche.modele);m.modeleDemande=true;}
    if(!N("HAS_MODEL_LOADED",m.fiche.modele))return;
    const z=m.fiche.bit===16?m.point[2]:ground(m.point);
    const acteur=N("CREATE_CHAR",m.fiche.type,m.fiche.modele,m.point[0],m.point[1],z);
    N("MARK_MODEL_AS_NO_LONGER_NEEDED",m.fiche.modele);m.modeleDemande=false;
    if(!alive(acteur)){removePed(acteur);return;}
    N("SET_CHAR_HEADING",acteur,m.fiche.bit===16?195:110);
    N("SET_CHAR_OBJ_WAIT_ON_FOOT",acteur);
    m.acteur=acteur;
}
function temoinProche(pos){
    const m=mission;
    if(!m || m.kind!=="dossier" || m.step!==0 || !alive(m.acteur))return false;
    const q=posOf(m.acteur);
    return Math.abs(pos.z-q.z)<2.8 && Math.hypot(pos.x-q.x,pos.y-q.y)<5.5 &&
        !N("IS_CHAR_IN_ANY_CAR",N("GET_PLAYER_CHAR",0));
}
function enregistrerTemoin(pos){
    if(ONMISSION || !temoinProche(pos))return false;
    const m=mission;
    finDossier(m);m.step=1;target(contact);menu="";
    say("Bande de "+m.fiche.nom+" enregistree. Rapporte-la a Ines.");return true;
}
function remettreDossier(pos){
    const m=mission;
    if(!m || m.kind!=="dossier" || m.step!==1 || ONMISSION || !near(pos,contact,6) ||
        N("IS_CHAR_IN_ANY_CAR",N("GET_PLAYER_CHAR",0)) || !dossierDisponible(m.fiche))return false;
    const d=m.fiche;
    if(!change(s=>{
        s.dossiers|=d.bit;s.missions++;s.caisse+=d.prime;s.xp+=s.equipe;
        s.reserve+=(s.local?cfg.revenu:0)+revenuEquipe(s)+propertyIncome(s);
    }))return false;
    cancelJob("");menu="";say("A l'antenne. "+d.groupe+" entre au carnet. +"+d.prime+" $.");
    return true;
}
function menuDossiers(pos){
    if(menu==="temoin"){
        if(!temoinProche(pos)){menu="";return;}
        ImGui.TextWrapped(mission.fiche.nom+"  |  "+mission.fiche.groupe);
        ImGui.TextWrapped(mission.fiche.parole);
        button("Enregistrer le temoignage",()=>enregistrerTemoin(pos));return;
    }
    ImGui.TextWrapped("Les voix de Vice. Quatre groupes se disputent la ville de 1986. Ines veut leurs voix sur bande. Le cinquieme rendez-vous se gagne en diffusant les quatre premiers.");
    if(!state.missions)ImGui.TextWrapped("Livre une premiere cassette a Ines pour ouvrir ce carnet.");
    for(const d of dossiersVice){
        ImGui.Separator();
        const termine=(state.dossiers&d.bit)!==0;
        ImGui.TextWrapped(d.groupe+" ("+d.origine+") | "+d.lieu+(termine?" | Diffuse":""));
        if(termine)ImGui.TextWrapped("Archive de "+d.nom+". "+d.parole);
        else if(!mission && dossierDisponible(d) && near(pos,contact,8))
            button("Rencontrer "+d.nom+"  +"+d.prime+" $",()=>commencerDossier(d.id,pos));
        else if(d.bit===16 && (state.dossiers&15)!==15)ImGui.TextWrapped("Pablo Escobar attend la diffusion des quatre temoignages.");
    }
    if(!near(pos,contact,8))ImGui.TextWrapped("Pour prendre un rendez-vous, retourne chez Ines sur Ocean Drive.");
}
