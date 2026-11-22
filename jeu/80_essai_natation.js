// Le pilote de recette n'est appelé que dans le profil Validation, scénario « natation ».
let essaiNage=null;
function planNage(e,phase,now,p) {
    e.phase=phase;e.depuis=now;
    writeKey("essai.ini","filmNage",bootId+"-"+phase);
    if(!p)return;
    const pos=posOf(p);
    const z=phase==="plongee"||phase==="apnee"?pos.z-1.2:pos.z+1.9;
    N("SET_FIXED_CAMERA_POSITION",pos.x+5.6,pos.y+3.8,z,0,0,0);
    N("POINT_CAMERA_AT_POINT",pos.x,pos.y,pos.z+.10,2);
}
function finEssaiNage(e,ok,motif) {
    if(e.phase==="fin")return;
    if(nage)quitterNage(nage.p,clockNow());
    N("RESTORE_CAMERA_JUMPCUT");
    writeKey("essai.ini","filmNage",bootId+"-fin");
    e.phase="fin";report((ok?"FIN natation ":"ECHEC natation ")+motif);
}
function testNatation(p,libre,now) {
    if(!essaiNage){
        if(!libre)return;
        const x=-760,y=-269,z=eauxDeNage(x,y);
        essaiNage={p,phase:"entree",depuis:now,depart:now,eau:z,
            vie:N("GET_CHAR_HEALTH",p),airMin:nagePoumons,perte:false,verifie:true};
        N("SET_AREA_VISIBLE",0);N("SET_TIME_OF_DAY",12,0);N("FORCE_WEATHER_NOW",0);N("REQUEST_COLLISION",x,y);
        N("LOAD_SCENE",x,y,z+5);N("SET_CHAR_COORDINATES",p,x,y,z+4.5);N("SET_CHAR_HEADING",p,0);
        writeKey("essai.ini","filmNage",bootId+"-entree");
        report("NAGE depart mer "+z+" m, vie "+essaiNage.vie);
        return;
    }
    const e=essaiNage;
    if(e.phase==="fin")return;
    const acteurPresent=N("DOES_CHAR_EXIST",e.p);
    const mort=acteurPresent&&N("IS_CHAR_DEAD",e.p);
    if(e.phase==="apnee" && acteurPresent && !mort && N("GET_CHAR_HEALTH",e.p)<=0)return;
    if(mort || !libre || p!==e.p){
        if(e.phase==="apnee" && mort){
            const ok=e.perte&&e.airMin<=.01;
            verdict("NAGE noyade native apres air vide et perte de vie",ok);
            finEssaiNage(e,e.verifie&&ok,"surface, plongee, reprise du souffle et noyade");
        }else if(now-e.depuis>3000)finEssaiNage(e,false,"personnage indisponible pendant "+e.phase);
        return;
    }
    const c={avant:0,tourner:0,plonger:false,remonter:false,vite:false,monter:false};
    const duree=now-e.depuis;
    if(e.phase==="surface"){c.avant=.90;c.vite=true;}
    if(e.phase==="plongee"){c.avant=.35;c.plonger=duree<2100;}
    if(e.phase==="remontee")c.remonter=true;
    if(e.phase==="apnee")c.plonger=duree<2300;
    if(e.phase==="entree" && (!e.sonde || now-e.sonde>250)){e.sonde=now;const point=posOf(p);report("NAGE sonde entree pos="+JSON.stringify(point)+" eau="+N("IS_CHAR_IN_WATER",p)+" pied="+N("IS_CHAR_ON_FOOT",p)+" fond="+solDeNage(point.x,point.y,e.eau)+" sante="+N("GET_CHAR_HEALTH",p));}
    tickNage(p,libre,now,c);
    if(!nage){
        if(e.phase==="apnee" && e.perte)return;
        if(duree>6500)finEssaiNage(e,false,"contact aquatique "+e.phase+" position="+JSON.stringify(posOf(p)));
        return;
    }
    const s=nage,vie=N("GET_CHAR_HEALTH",p),pos=posOf(p);
    if(e.phase!=="entree"){
        N("SET_FIXED_CAMERA_POSITION",pos.x+3.7,pos.y+1.55,pos.z+(e.phase==="surface"||e.phase==="remontee"?.95:.30),0,0,0);
        N("POINT_CAMERA_AT_POINT",pos.x,pos.y+.11,pos.z+.05,2);
    }
    if(e.phase==="entree"){
        e.surface=pos;e.vieSurface=vie;planNage(e,"surface",now,p);return;
    }
    if(e.phase==="surface" && duree>=3000){
        const dist=Math.hypot(pos.x-e.surface.x,pos.y-e.surface.y);
        const ok=dist>4 && s.phase < -65 && s.air===nagePoumons && vie===e.vieSurface;
        verdict("NAGE surface "+dist.toFixed(2)+" m / pose "+s.phase.toFixed(0)+" deg / vie "+vie,ok);
        e.verifie=e.verifie&&ok;e.haut=pos.z;planNage(e,"plongee",now,p);return;
    }
    if(e.phase==="plongee" && duree>=4000){
        const ok=pos.z<e.haut-1.25 && s.profondeur>1.25 && s.air<nagePoumons-1;
        verdict("NAGE plongee Z="+pos.z.toFixed(2)+" air="+s.air.toFixed(2),ok);
        e.verifie=e.verifie&&ok;e.bas=pos.z;planNage(e,"remontee",now,p);return;
    }
    if(e.phase==="remontee" && duree>=4500){
        const ok=pos.z>e.bas+1.25 && s.profondeur<.05 && s.air>=nagePoumons-.05 && vie===e.vieSurface;
        verdict("NAGE remontee et souffle recupere Z="+pos.z.toFixed(2)+" air="+s.air.toFixed(2),ok);
        e.verifie=e.verifie&&ok;planNage(e,"apnee",now,p);return;
    }
    if(e.phase==="apnee"){
        e.airMin=Math.min(e.airMin,s.air);
        if(!e.perte && vie<e.vieSurface){
            e.perte=true;const ok=s.air<=.01;e.verifie=e.verifie&&ok;
            verdict("NAGE premiers degats apres epuisement air="+s.air.toFixed(2)+" vie="+vie,ok);
        }
        if(duree>48000)finEssaiNage(e,false,"echeance en apnee");
    }
}
