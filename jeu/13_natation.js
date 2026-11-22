// Nage de Tommy. Les distances suivent les mètres du monde, le temps celui du moteur.
const nagePoumons=16, nageRecup=5.5, nageDegats=14;
let nage=null, nageDernierSol=0, nageAide=false, nageIgnoreJusqua=0;
function eauxDeNage(x,y) {
    const zones=cfg.eauxNatation||[];
    for(const [z,g,b,d,h] of zones)if(x>=g&&x<=d&&y>=b&&y<=h)return z;
    return null;
}
function entreeNage() {
    const axes=N("GET_POSITION_OF_ANALOGUE_STICKS",0);
    function axe(v){return Math.abs(v||0)<18?0:Math.max(-1,Math.min(1,v/128));}
    const bouton=b=>N("IS_BUTTON_PRESSED",0,b);
    return {avant:axe(-axes.leftStickY)||Number(bouton(8))-Number(bouton(9)),
        tourner:axe(axes.leftStickX)||Number(bouton(11))-Number(bouton(10)),
        plonger:bouton(18),remonter:bouton(14),vite:bouton(16),monter:bouton(15)};
}
function souffleNage(s,immerge,dt) {
    const manque=immerge?Math.max(0,dt-s.air):0;
    s.air=immerge?Math.max(0,s.air-dt):Math.min(nagePoumons,s.air+dt*nageRecup);
    s.dette+=manque*nageDegats;
    const degats=Math.floor(s.dette);
    s.dette-=degats;
    return degats;
}
function quitterNage(p,maintenant) {
    if(!nage)return;
    if(nage.p===p && N("DOES_CHAR_EXIST",p)){
        if(N("RADIO_NAGE_ETAT",p)>=0){
            N("RADIO_NAGE_POSTURE",p,0,0);
            N("SET_CHAR_DROWNS_IN_WATER",p,nage.noyade);
        }
    }
    nage=null;
    nageIgnoreJusqua=maintenant+650;
}
function solDeNage(x,y,surface) {
    const z=N("GET_GROUND_Z_FOR_3D_COORD",x,y,surface+2.15);
    return Number.isFinite(z)&&z>surface-30&&z<=surface+2.15?z:null;
}
function occupeNage(x,y,z) {
    return N("IS_AREA_OCCUPIED",x-.18,y-.18,z-.18,x+.18,y+.18,z+.30,true,true,false,true,false);
}
function hudNage(s) {
    const f=Math.max(0,Math.min(1,s.air/nagePoumons));
    ImGui.BeginFrame("RADIO_OCEAN_AIR");
    // La fenêtre du HUD ne capture aucune commande et ne demande jamais le curseur.
    ImGui.SetNextWindowPos(28,278,1);
    ImGui.SetNextWindowSize(202,83,1);
    ImGui.Begin("Souffle##RadioOcean",1,1,1,1,0);
    ImGui.Text(f<=0?"AIR  0 %  -  Remonte !":"AIR  "+Math.round(f*100)+" %");
    const barres=Math.round(f*16);
    ImGui.TextColored("["+"=".repeat(barres)+" ".repeat(16-barres)+"]",f<.22?.96:.30,f<.22?.30:.82,f<.22?.24:.92,1);
    ImGui.Text(s.profondeur>.70?"En immersion":"En surface");
    ImGui.End();ImGui.EndFrame();
}
function tickNage(p,libre,now,commandes=null) {
    if(!libre || p===null || !alive(p) || N("IS_CHAR_IN_ANY_CAR",p) || !N("IS_CHAR_ON_FOOT",p)){
        if(nage)quitterNage(nage.p,now);
        return false;
    }
    const pos=posOf(p);
    if(nage && nage.p!==p){nage=null;return false;}
    const niveau=eauxDeNage(pos.x,pos.y);
    if(!nage){
        if(now<nageIgnoreJusqua || niveau===null || pos.z>niveau+1.2 || !N("IS_CHAR_IN_WATER",p))return false;
        const fond=solDeNage(pos.x,pos.y,niveau);
        if(fond!==null && fond>niveau-.65)return false;
        nage={p,air:nagePoumons,dette:0,cap:N("GET_CHAR_HEADING",p),profondeur:0,
            noyade:!!N("RADIO_NAGE_ETAT",p),horloge:now,embarque:0,niveau,
            x:pos.x,y:pos.y,z:niveau+.04,phase:0,force:0};
        N("SET_CHAR_DROWNS_IN_WATER",p,false);
        if(!nageAide){nageAide=true;showTextBox("Nage : avance avec la direction. Accroupi pour plonger, Saut pour remonter, Sprint pour accelerer.");}
        nageDernierSol=now;
    }
    const s=nage,dt=Math.max(0,Math.min(.15,(now-s.horloge)/1000));
    s.horloge=now;
    if(niveau===null || Math.hypot(pos.x-s.x,pos.y-s.y)>5 || pos.z>s.niveau+3){
        quitterNage(p,now);return false;
    }
    const c=commandes||entreeNage();
    if(c.monter && s.profondeur<=.7)s.embarque=now+900;
    if(s.embarque>now && s.profondeur<=.7){
        souffleNage(s,false,dt);hudNage(s);
        N("RADIO_NAGE_POSTURE",p,0,0);
        // Le moteur gère l'entrée et les sièges des bateaux avec l'action Entrer du joueur.
        s.x=pos.x;s.y=pos.y;return true;
    }
    s.cap=(s.cap-c.tourner*105*dt+360)%360;
    const angle=s.cap*Math.PI/180, fx=-Math.sin(angle),fy=Math.cos(angle);
    const avance=c.avant*(c.vite?3.55:1.9)*dt;
    const x=s.x+fx*avance,y=s.y+fy*avance;
    const eau=eauxDeNage(x,y);
    const fond=solDeNage(x,y,niveau);
    if(c.avant>.15 && s.profondeur<.7){
        const lx=s.x+fx*.84,ly=s.y+fy*.84, bord=solDeNage(lx,ly,niveau);
        if(bord!==null && bord>=niveau-.50 && bord<=niveau+1.6 &&
            (c.remonter || bord<niveau+.30) && !occupeNage(lx,ly,bord+1.0)){
            quitterNage(p,now);
            N("SET_CHAR_COORDINATES",p,lx,ly,bord+.10);
            return false;
        }
    }
    const delta=(Number(c.plonger)-Number(c.remonter))*2.05*dt;
    const maxFond=fond===null?9:Math.max(0,Math.min(9,niveau-fond-.58));
    const profondeur=Math.max(0,Math.min(maxFond,s.profondeur+delta));
    const z=niveau+.04-profondeur;
    if(eau!==null && !occupeNage(x,y,z)){
        s.x=x;s.y=y;s.z=z;s.profondeur=profondeur;
    }else if(profondeur<s.profondeur&&!occupeNage(s.x,s.y,z)){
        s.z=z;s.profondeur=profondeur;
    }
    if(now-nageDernierSol>=500){
        nageDernierSol=now;
        const ici=solDeNage(s.x,s.y,s.niveau);
        if(ici!==null && ici>s.niveau+.55 && pos.z>=s.niveau+.7){quitterNage(p,now);return false;}
    }
    N("RADIO_NAGE_POSITION",p,s.x,s.y,s.z);
    N("SET_CHAR_HEADING",p,s.cap);
    // La pose oriente le modèle graphique seul, le collider du piéton reste vertical.
    const effort=Math.abs(c.avant);
    s.force+=(effort-s.force)*Math.min(1,dt*5);
    const cible=c.plonger&&s.profondeur>.2?-108:c.remonter&&s.profondeur>.3?-46:-32-48*s.force;
    s.phase+=(cible-s.phase)*Math.min(1,dt*6);
    N("RADIO_NAGE_POSTURE",p,s.phase,.65+s.force*(c.vite?1.15:.65));
    const perte=souffleNage(s,s.profondeur>.7,dt);
    if(perte>0){
        const vie=N("GET_CHAR_HEALTH",p);
        N("SET_CHAR_HEALTH",p,Math.max(0,vie-perte));
        if(vie<=perte){quitterNage(p,now);return false;}
    }
    hudNage(s);
    return true;
}
