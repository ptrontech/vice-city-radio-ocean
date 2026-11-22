// Profil Validation. Les trois civils utilisent la même routine qu'en campagne.
const visiteMajestic={phase:"attente",debut:0,prochain:0,precedentes:[],interieur:[0,0,0],hauteurs:[null,null,null],plans:0};

function testVieMajestic(p,libre,now) {
    const e=visiteMajestic;
    if(e.phase==="fin" || !libre) return;
    if(e.phase==="attente"){
        N("SET_AREA_VISIBLE",0);
        N("SET_TIME_OF_DAY",16,30);
        N("FORCE_WEATHER_NOW",0);
        testMove(p,[284,-993,11]);
        N("REQUEST_COLLISION",275,-987);
        N("LOAD_SCENE",275,-987,12);
        N("SET_FIXED_CAMERA_POSITION",...mondeMajestic([5.5,-1.6,1.76]),0,0,0);
        N("POINT_CAMERA_AT_POINT",...mondeMajestic([-4.1,1.2,1.42]),2);
        N("DISPLAY_RADAR",false);
        e.phase="reception";e.debut=now;
    }
    if(now<e.prochain) return;
    e.prochain=now+180;
    vieMajestic(posOf(p),now);
    const ages=now-e.debut;
    for(let i=0;i<habitantsMajestic.length;i++){
        const h=habitantsMajestic[i].acteur;
        if(!alive(h))continue;
        const pos=posOf(h), dernier=e.precedentes[i];
        if(dernier){
            const d=Math.hypot(pos.x-dernier.x,pos.y-dernier.y);
            const dx=pos.x-275.031377, dy=pos.y+987.298706;
            if(d<1.4){
                if(.987604921*dx-.156960251*dy<-.30 && pos.z>11.52 && pos.z<12.65){
                    e.interieur[i]+=d;
                    e.hauteurs[i]=pos.z;
                }
            }
        }
        e.precedentes[i]=pos;
    }
    if(!e.plans && habitantsMajestic.every(h=>alive(h.acteur))){
        writeKey("essai.ini","filmVie",bootId+"-reception");
        e.plans++;
    }
    if(ages>12500 && e.phase==="reception"){
        e.phase="salon";
        N("SET_FIXED_CAMERA_POSITION",...mondeMajestic([-7.1,10.08,1.74]),0,0,0);
        N("POINT_CAMERA_AT_POINT",...mondeMajestic([-6.55,7.08,1.36]),2);
        writeKey("essai.ini","filmVie",bootId+"-salon");
    }
    if(ages>20000 && e.phase==="salon"){
        e.phase="comptoir";
        N("SET_FIXED_CAMERA_POSITION",...mondeMajestic([-.58,-1.04,1.81]),0,0,0);
        N("POINT_CAMERA_AT_POINT",...mondeMajestic([-4.67,1.04,1.40]),2);
        writeKey("essai.ini","filmVie",bootId+"-comptoir");
    }
    if(ages<28000) return;
    const actifs=habitantsMajestic.map(h=>h.acteur);
    const details=personnelMajestic.map((role,i)=>role.role+"="+e.interieur[i].toFixed(2)+"m").join(" ");
    const marche=actifs.every(alive) && e.interieur.every(d=>d>1.5);
    report("Majestic, hauteurs du personnel et des clients "+JSON.stringify(e.hauteurs));
    verdict("Majestic, trois civils en marche dans le hall "+details,marche);
    testMove(p,[248,-1275,12]);
    vieMajestic(posOf(p),now);
    const retires=actifs.every(h=>!alive(h));
    verdict("Majestic, hotel quitte et civils liberes",retires);
    writeKey("essai.ini","resultatVie",bootId+"-"+(marche && retires?"ok ":"echec ")+details);
    writeKey("essai.ini","filmVie",bootId+"-fin");
    N("RESTORE_CAMERA_JUMPCUT");N("DISPLAY_RADAR",true);N("RELEASE_WEATHER");
    e.phase="fin";
}
