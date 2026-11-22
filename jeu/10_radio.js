function plain(value,len) {
    return String(value||"").replace(/[\r\n~%|]/g," ").replace(/\s+/g," ").trim().slice(0,len);
}
function askInes(question) {
    if(pending)return;
    const clean=plain(question,150);
    if(!clean){say("Entre un message ou choisis un sujet.");return;}
    const id=bootId+"-"+(++exchange);
    writeKey("requetes.ini","question",clean);
    writeKey("requetes.ini","contexte",[state.missions,state.caisse,state.local,state.equipe,state.xp,state.reserve].join(","));
    writeKey("requetes.ini","id",id);
    pending={id,at:Date.now(),question:clean};proposal="aucune";reply="Ines ecoute la frequence...";
}
function fallback() {return state.local?"Ton local est ouvert. Chaque bande livree alimente sa caisse.":"Passe au micro. Je cherche quelqu'un pour rapporter une bande avant minuit.";}
function pollReply() {
    if(!pending)return;
    if(readKey("reponses.ini","id")===pending.id) {
        reply=plain([0,1,2,3].map(i=>readKey("reponses.ini","ligne"+i)).join("").replace(/_/g," "),224)||fallback();
        const intention=readKey("reponses.ini","intention");
        proposal=["livraison","bilan","local"].includes(intention)?intention:"aucune";
        memoryLabel=readKey("reponses.ini","origine")==="ollama"?"Ines - IA locale":"Ines - replique de secours";
        pending=null;log("Radio Ocean | dialogue "+memoryLabel);
    }else if(Date.now()-pending.at>45000){
        pending=null;proposal="aucune";reply=fallback();memoryLabel="Ines - replique de secours";
    }
}
let recentHub="", holdOpen=false, prevKey=false, lastHint=0;
function edge(id,down) {const last=held[id];held[id]=Boolean(down);return Boolean(down&&!last);}
function tickMenuKeys() {
    const journal=edge("journal",N("IS_KEY_PRESSED",cfg.toucheJournal)||N("IS_BUTTON_PRESSED",0,cfg.boutonJournal));
    const next=edge("suiv",N("IS_BUTTON_PRESSED",0,cfg.boutonSuivant));
    const prev=edge("prec",N("IS_BUTTON_PRESSED",0,cfg.boutonPrecedent));
    accept=edge("ok",N("IS_BUTTON_PRESSED",0,cfg.boutonValider));
    if(journal) {if(menu)menu="";else openMenu("journal");}
    if(menu&&focusCount && (next||prev))selected=(selected+(next?1:-1)+focusCount)%focusCount;
}
let buttonIndex=0, queued=null, captured=false;
function button(label,fn) {
    const i=buttonIndex++;
    const clicked=ImGui.Button((i===selected?">  ":"")+label+"##r"+i,325,27);
    if(clicked || (i===selected&&accept)) {
        if(mode!=="Validation")log("Radio Ocean | commande "+label);
        if(!queued)queued=fn;
    }
}
function drawMenu(pos) {
    if(!menu && !captured)return;
    if(menu && !captured && mode!=="Validation")log("Radio Ocean | menu visible "+menu);
    ImGui.BeginFrame("VC_RADIO_OCEAN");
    ImGui.SetCursorVisible(menu?1:0);captured=!!menu;
    if(menu) {
        ImGui.SetNextWindowSize(410,490,2);
        const open=ImGui.Begin("Radio Ocean | Vice City 1986",1,0,0,0,0);
        buttonIndex=0;queued=null;
        const rang=capacity(), next=cfg.reputation[rang];
        ImGui.TextWrapped((mode==="Libre"?"ESSAI LIBRE  |  ":"")+grades[rang]+"  |  "+state.caisse+" $  |  "+state.missions+" livraisons");
        ImGui.Separator();
        if(menu==="journal"){
            ImGui.TextWrapped(mission?brief():"Ines attend sur Ocean Drive, devant l'Ocean View. Contact violet sur le radar, local vert vers le News Cafe.");
            ImGui.TextWrapped(next?"Prochain recrutement a "+next+" livraisons.":"Tu as atteint le dernier grade de cette version.");
            if(near(pos,contact,10))button("Parler a Ines",()=>openMenu("contact"));
            if(near(pos,local,9))button("Visiter le local",()=>openMenu("local"));
            button("Sprint et endurance",()=>openMenu("sprint"));
            if(state.equipe)button("Ordres a l'equipe",()=>openMenu("equipe"));
            if(mission)button("Abandonner la livraison",()=>cancelJob("Course abandonnee."));
        }else if(menu==="contact"){
            ImGui.TextWrapped("Ines Vega  |  Productrice de la radio pirate d'Ocean Beach");
            ImGui.TextWrapped(mission?brief():"Le bateau apporte les bandes. Il faut les ramener au studio avant la prochaine emission.");
            if(!mission)button("Accepter la course  +"+cfg.prime+" $",()=>startJob(pos));
            button("Discuter avec Ines",()=>openMenu("radio"));
            button("Sprint et endurance",()=>openMenu("sprint"));
            if(state.equipe<capacity() && state.caisse>=cfg.prixGarde)button("Recruter "+noms[state.equipe]+"  "+cfg.prixGarde+" $",()=>recruit(pos));
            else ImGui.TextWrapped("Equipe : "+state.equipe+" / "+capacity()+". Recrutement : "+cfg.prixGarde+" $.");
            if(state.equipe)button("Ordres a l'equipe",()=>openMenu("equipe"));
        }else if(menu==="sprint"){
            drawSprintMenu();
        }else if(menu==="local"||menu==="achat"){
            ImGui.TextWrapped("Regie du News Cafe | comptoir exterieur");
            ImGui.TextWrapped("Chaque emission livree apres l'achat rapporte "+cfg.revenu+" $ a retirer ici.");
            if(state.local){
                ImGui.TextWrapped("Disponible : "+state.reserve+" $.");
                if(state.reserve)button("Retirer les recettes",()=>collect(pos));
                if(!mission)button("Transporter la journaliste  +"+cfg.primeReportage+" $",()=>startReport(pos));
            }else if(state.caisse<cfg.prixLocal)ImGui.TextWrapped("Prix : "+cfg.prixLocal+" $. Continue les courses pour financer le local.");
            else if(menu==="achat"){
                button("Confirmer l'achat  "+cfg.prixLocal+" $",()=>{if(buy(pos))openMenu("local");});
                button("Annuler",()=>openMenu("local"));
            }else button("Acheter  "+cfg.prixLocal+" $",()=>openMenu("achat"));
        }else if(menu==="equipe"){
            ImGui.TextWrapped(noms.slice(0,state.equipe).map((n,i)=>n+" ("+roles[i]+")").join(", ")+" | Experience collective "+state.xp);
            button("Suivre et proteger",()=>setOrder("suivre"));button("Attendre ici",()=>setOrder("attendre"));
            button("Rejoindre le vehicule",()=>{lastVehicle=0;setOrder("suivre");});
            if(state.equipe)button("Renvoyer "+noms[state.equipe-1],()=>openMenu("renvoi"));
        }else if(menu==="renvoi"){
            button("Confirmer la fin du contrat",()=>{dismiss();openMenu("journal");});
        }else if(menu==="radio"){
            ImGui.TextWrapped(reply||"Tu peux me parler de la radio, du quartier ou de ton equipe.");
            if(memoryLabel)ImGui.TextWrapped(memoryLabel);
            const q=ImGui.InputText("Ton message");
            if(!pending){
                button("Envoyer le message",()=>askInes(q));
                button("Du travail ce soir ?",()=>askInes("Tu as du travail pour moi ce soir ?"));
                button("Tu te souviens de mes courses ?",()=>askInes("Tu te souviens de mon travail pour la radio ?"));
                if(proposal==="livraison"&&!mission&&near(pos,contact,10))button("Accepter la course proposee",()=>startJob(pos));
                if(proposal==="bilan"||proposal==="local")button("Consulter le journal",()=>openMenu("journal"));
            }
        }
        if(message && Date.now()<noticeUntil)ImGui.TextWrapped(message);
        button("Fermer",()=>{menu="";});focusCount=buttonIndex;
        if(selected>=focusCount)selected=0;
        ImGui.End();
        if(!open)menu="";
        else if(queued)queued();
    }
    ImGui.EndFrame();
}
let nextWorld=0, ready=false, firstHint=false, lastStatus=0;
function tick() {
    const now=clockNow();
    const playing=N("IS_PLAYER_PLAYING",0);
    const player=playing?N("GET_PLAYER_CHAR",0):null;
    const free=playing && alive(player) && !ONMISSION;
    if(mode==="Validation") testTick(playing,player,free,now);
    if(benchOnly)return;
    tickSprint(player,free,now);
    if(!free){
        if(ready){quiet();if(captured){ImGui.BeginFrame("VC_RADIO_OCEAN");ImGui.SetCursorVisible(0);ImGui.EndFrame();captured=false;}log("Radio Ocean | suspendu pendant la campagne");}
        ready=false;recentHub="";return;
    }
    ready=true;const pos=posOf(player);
    if(!firstHint && mode==="Libre"){N("REQUEST_COLLISION",...contact.slice(0,2));N("SET_CHAR_COORDINATES",player,contact[0],contact[1],ground(contact));}
    if(!firstHint){showTextBox("Radio Ocean : retrouve Ines sur Ocean Drive. Journal : touche configuree dans le lanceur.");firstHint=true;}
    tickMenuKeys();
    if(now>=nextWorld||now+1500<nextWorld){
        nextWorld=now+500;population(pos,player,now);pollReply();
        const place=near(pos,contact,5)?"contact":near(pos,local,5)?"local":"";
        if(place && !recentHub && !menu && !N("IS_CHAR_IN_ANY_CAR",player) && (mode!=="Validation"||testStep===99))openMenu(place);
        if(!place && ["contact","local","achat","radio"].includes(menu))menu="";
        recentHub=place;
    }
    tickJob(pos);
    if (Date.now()<noticeUntil && !menu && lastHint!==noticeUntil) {showTextBox(message);lastHint=noticeUntil;}
    drawMenu(pos);
}
