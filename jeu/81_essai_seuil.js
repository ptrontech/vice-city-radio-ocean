// Le profil Validation inspecte les collisions du Majestic et fait marcher un civil du perron au comptoir.
const solLocalSeuil=.06;
const directionSeuil=[.987604921,-.156960251];
const departTemoinSeuil=[278.006,-988.845,10.12];
const arriveeTemoinSeuil=[272.495,-987.969,10.93];
const essaiSeuil={phase:"attente",temoin:null,depuis:0,dernier:null,dernierTemps:0,
    marche:0,maxPas:0,saut:false,franchi:null,echantillons:0,dernierJournal:0,marcheOK:false,
    enFace:false,contourne:false,passageFerme:false,minDistance:null};

function localSeuil(p){
    const dx=p.x-275.031377,dy=p.y+987.298706;
    return [dx*directionSeuil[0]+dy*directionSeuil[1],
        -dx*directionSeuil[1]+dy*directionSeuil[0],p.z-10.870894];
}
function positionSeuil(p){return p.map(n=>n.toFixed(2)).join(",");}
function ecrireSeuil(cle,texte){writeKey("essai.ini",cle,bootId+"-"+texte);}
function phaseSeuil(nom,t){
    essaiSeuil.phase=nom;essaiSeuil.depuis=t;ecrireSeuil("testSeuil",nom);
}
function occupeSeuil(x,y,z,rayon){
    const m=mondeHallVolume([x,y,z]);
    return !!N("IS_AREA_OCCUPIED",m[0]-rayon,m[1]-rayon,m[2]-.035,
        m[0]+rayon,m[1]+rayon,m[2]+.035,true,false,false,true,false);
}
function sondesSeuil(){
    // Vice City PC expose l'occupation d'une boîte et le rayon vertical du sol.
    // Le vecteur de cellules n'est jamais interprété comme un rayon horizontal exact.
    const colonnes=[["passage",0,-1.05],["battant",-.035,.80],["vitre",.74,3.30],
        ["comptoir",-3.035,1.02],["arriere",-5.95,-1.90],["muret",3.55,-5.00]];
    const hauteurs=[.22,.42,.75,1.08,1.61,2.15,2.85];
    const diagnostics={};
    for(const [nom,x,y] of colonnes){
        const profils=[];
        for(const h of hauteurs){
            // Cinq boîtes de 12 cm, réparties le long de la normale de façade.
            profils.push([-.24,-.12,0,.12,.24].map(dx=>occupeSeuil(x+dx,y,h,.06)?"1":"0").join(""));
        }
        const point=mondeHallVolume([x,y,0]);
        const sols=hauteurs.map(h=>Number(N("GET_GROUND_Z_FOR_3D_COORD",point[0],point[1],point[2]+h)));
        diagnostics[nom]=profils;
        report("SEUIL sondes "+nom+" zlocal="+hauteurs.join(",")+" boites="+profils.join("/")+" sol_monde="+positionSeuil(sols));
        ecrireSeuil("boitesSeuil_"+nom,profils.join("/"));
        ecrireSeuil("solSeuil_"+nom,positionSeuil(sols));
    }
    const distinct=diagnostics.passage.some((v,i)=>v!==diagnostics.battant[i] || v!==diagnostics.muret[i]);
    ecrireSeuil("sondesSeuil",distinct?"contraste":"volumes-indifferencies");
}
function objectifSeuil(point){
    N("SET_CHAR_OBJ_GOTO_COORD_ON_FOOT",essaiSeuil.temoin,point[0],point[1]);
}
function nettoyerSeuil(){
    if(essaiSeuil.temoin!==null){removePed(essaiSeuil.temoin);essaiSeuil.temoin=null;}
    N("MARK_MODEL_AS_NO_LONGER_NEEDED",21);
    N("RESTORE_CAMERA_JUMPCUT");
}
function finSeuil(t,detail){
    if(!essaiSeuil.marcheOK){
        ecrireSeuil("marcheSeuil","echec-"+detail);
        verdict("SEUIL marche native "+detail,false);
    }
    ecrireSeuil("finSeuil",(essaiSeuil.marcheOK?"franchi":"echec")+"-"+detail);
    if(essaiSeuil.minDistance!==null)ecrireSeuil("distanceComptoirSeuil",essaiSeuil.minDistance.toFixed(2)+"m");
    report("SEUIL fin "+detail+" marche="+essaiSeuil.marche.toFixed(2)+" m echantillons="+essaiSeuil.echantillons+" plusGrandPas="+essaiSeuil.maxPas.toFixed(3));
    nettoyerSeuil();phaseSeuil("fin",t);
}
function journalSeuil(monde,local,t){
    const e=essaiSeuil,old=e.dernier;
    if(old){
        const delta=Math.hypot(local[0]-old[0],local[1]-old[1]);
        if(e.phase==="marche"){
            e.marche+=delta;e.maxPas=Math.max(delta,e.maxPas);
            if(delta>Math.max(.90,.0038*(t-e.dernierTemps)))e.saut=true;
            if(!e.franchi && old[0]>0 && local[0]<=0){
                const f=old[0]/(old[0]-local[0]);
                e.franchi=[old[1]+f*(local[1]-old[1]),old[2]+f*(local[2]-old[2])];
                report("SEUIL croisement au plan y_z locaux="+positionSeuil(e.franchi));
                ecrireSeuil("croisementSeuil",positionSeuil(e.franchi));
            }
        }else if(e.phase==="battant"){
            if(Math.abs(local[0])<1.05 && local[1]>.08 && local[1]<2.05)e.enFace=true;
            if(old[0]<0 && local[0]>=0){
                const f=-old[0]/(local[0]-old[0]), y=old[1]+f*(local[1]-old[1]);
                if(y>.05 && y<2.08)e.passageFerme=true;
                else e.contourne=true;
            }
        }
    }
    e.dernier=local;e.dernierTemps=t;e.echantillons++;
    if(t-e.dernierJournal>=700){
        report("SEUIL trajet "+e.phase+" monde="+positionSeuil([monde.x,monde.y,monde.z])+" local="+positionSeuil(local));
        e.dernierJournal=t;
    }
}
function testSeuil(p,free){
    const e=essaiSeuil,t=Date.now();
    if(e.phase==="fin"){testVolumes(p,free);return;}
    if(!free){if(e.phase!=="attente")finSeuil(t,"joueur-indisponible");return;}
    if(e.phase==="attente"){
        N("SET_AREA_VISIBLE",0);
        N("REQUEST_COLLISION",275.031,-987.299);
        N("REQUEST_MODEL",21);
        N("LOAD_SCENE",275.031,-987.299,12);
        // Unique placement de Tommy sur le perron, à l'écart du trajet du témoin.
        const perron=mondeHallVolume([2.35,.68,solLocalSeuil+.35]);
        N("SET_CHAR_COORDINATES",p,...perron);
        N("SET_CHAR_HEADING",p,99);
        N("SET_FIXED_CAMERA_POSITION",278.990,-989.467,12.601,0,0,0);
        N("POINT_CAMERA_AT_POINT",272.55,-987.74,12.03,2);
        phaseSeuil("chargement",t);return;
    }
    if(e.phase==="chargement"){
        if(t-e.depuis>18000){finSeuil(t,"chargement");return;}
        if(t-e.depuis<1400 || !N("HAS_MODEL_LOADED",21) || N("IS_CHAR_WAITING_FOR_WORLD_COLLISION",p))return;
        sondesSeuil();
        e.temoin=N("CREATE_CHAR",5,21,departTemoinSeuil[0],departTemoinSeuil[1],departTemoinSeuil[2]+.36);
        if(!alive(e.temoin)){finSeuil(t,"creation-temoin");return;}
        N("SET_CHAR_HEED_THREATS",e.temoin,false);
        N("SET_CHAR_HEADING",e.temoin,99);
        phaseSeuil("perron",t);return;
    }
    if(!alive(e.temoin) || N("IS_CHAR_IN_ANY_CAR",e.temoin)){finSeuil(t,"temoin-indisponible");return;}
    const point=posOf(e.temoin),local=localSeuil(point);
    if(e.phase==="perron"){
        if(t-e.depuis<1100)return;
        if(N("IS_CHAR_WAITING_FOR_WORLD_COLLISION",e.temoin)){
            if(t-e.depuis>9000)finSeuil(t,"collision-non-chargee");
            return;
        }
        if(local[0]<1.0){finSeuil(t,"depart-hors-perron");return;}
        e.dernier=local;e.dernierTemps=t;e.echantillons=0;
        ecrireSeuil("departSeuil",positionSeuil([point.x,point.y,point.z]));
        objectifSeuil(arriveeTemoinSeuil);
        phaseSeuil("marche",t);return;
    }
    if(t-e.dernierTemps<65)return;
    journalSeuil(point,local,t);
    if(e.phase==="marche"){
        const d=Math.hypot(point.x-arriveeTemoinSeuil[0],point.y-arriveeTemoinSeuil[1]);
        e.minDistance=e.minDistance===null?d:Math.min(e.minDistance,d);
        const dansHall=local[0]<-1.53 && d<1.02;
        if(dansHall){
            e.marcheOK=e.franchi!==null && e.franchi[0]>-1.83 && e.franchi[0]<-.33 &&
                e.franchi[1]>-.08 && e.franchi[1]<1.82 && e.marche>3.6 && e.echantillons>=12 && !e.saut;
            if(!e.marcheOK){finSeuil(t,"trajectoire-invalide");return;}
            ecrireSeuil("marcheSeuil","franchi-"+e.marche.toFixed(2)+"m");
            verdict("SEUIL temoin du perron devant le comptoir sans repositionnement, "+e.marche.toFixed(2)+" m",true);
            objectifSeuil(mondeHallVolume([-1.01,1.05,solLocalSeuil]));
            phaseSeuil("approche-battant",t);return;
        }
        if(t-e.depuis>18000)finSeuil(t,"marche-bloquee-distance-"+d.toFixed(2));
        return;
    }
    if(e.phase==="approche-battant"){
        if(Math.hypot(local[0]+1.01,local[1]-1.05)<.83 && local[0]<-.10){
            objectifSeuil(mondeHallVolume([1.72,1.05,solLocalSeuil]));
            phaseSeuil("battant",t);return;
        }
        if(t-e.depuis>9000){ecrireSeuil("controleSeuil","approche-incomplete");finSeuil(t,"controle-indetermine");}
        return;
    }
    if(e.phase==="battant" && (t-e.depuis>=6500 || e.passageFerme || e.contourne)){
        const resultat=e.passageFerme?"traverse-battant":e.contourne?"contourne-par-passage":
            e.enFace && local[0]<.08?"arrete-devant-battant":"indetermine";
        ecrireSeuil("controleSeuil",resultat);
        report("SEUIL contre-epreuve battant nord "+resultat+" local="+positionSeuil(local));
        finSeuil(t,resultat);
    }
}
