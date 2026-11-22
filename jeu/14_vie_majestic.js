// Les parcours utilisent le repère du seuil et le sol du hall de plain-pied.
function mondeMajestic(p) {
    const [x,y,z] = p;
    return [275.031377 + .987604921*x + .156960251*y,
            -987.298706 - .156960251*x + .987604921*y, 10.870894 + z];
}

const personnelMajestic = [
    {
        role:"reception", modele:21, type:5,
        parcours:[[-5.06,-.88,4300,278], [-5.06,1.35,3400,270], [-5.06,2.40,4700,262]]
    },
    {
        role:"voyageur", modele:82, type:4,
        parcours:[[3.18,-1.06,800,99], [-2.4,-1.06,4300,98], [-1.48,2.20,0,0],
                  [-1.39,4.68,0,0], [-3.20,5.72,4600,172], [-1.39,4.68,0,0],
                  [-1.48,2.20,0,0], [-2.40,-1.06,0,0]]
    },
    {
        role:"cliente", modele:35, type:5,
        parcours:[[-8.35,7.52,2800,272],[-5.64,7.52,3800,311],[-6.75,7.00,2100,175]]
    }
];
const habitantsMajestic = personnelMajestic.map(() => ({
    acteur:null, demande:false, etape:0, attend:true, echeance:0, reessai:0
}));
const centreMajestic = mondeMajestic([-3.3,2,1]);
let ouvertMajestic = false;

function retirerHabitant(i, maintenant, retarder) {
    const spec=personnelMajestic[i], etat=habitantsMajestic[i];
    if(etat.acteur!==null && N("DOES_CHAR_EXIST",etat.acteur)){
        if(retarder) N("MARK_CHAR_AS_NO_LONGER_NEEDED",etat.acteur);
        else removePed(etat.acteur);
    }
    if(etat.demande) N("MARK_MODEL_AS_NO_LONGER_NEEDED",spec.modele);
    Object.assign(etat,{acteur:null,demande:false,etape:0,attend:true,echeance:0,
        reessai:retarder?maintenant+60000:0});
}

function fermerMajestic() {
    if(!ouvertMajestic) return;
    for(let i=0;i<habitantsMajestic.length;i++) retirerHabitant(i,0,false);
    ouvertMajestic=false;
}

function pauseHabitant(etat, etape, maintenant) {
    N("SET_CHAR_OBJ_WAIT_ON_FOOT",etat.acteur);
    if(etape[2]) N("SET_CHAR_HEADING",etat.acteur,etape[3]);
    etat.attend=true;
    etat.echeance=maintenant+etape[2];
}

function marcherHabitant(etat,spec,maintenant) {
    const etape=spec.parcours[etat.etape];
    const [x,y]=mondeMajestic([etape[0],etape[1],.06]);
    N("SET_CHAR_OBJ_GOTO_COORD_ON_FOOT",etat.acteur,x,y);
    etat.attend=false;
    etat.echeance=maintenant+8000;
}

function vieMajestic(position,maintenant) {
    if(cfg.facadesOcean===false || !near(position,centreMajestic,ouvertMajestic?88:62)){
        fermerMajestic();
        return;
    }
    ouvertMajestic=true;
    for(let i=0;i<personnelMajestic.length;i++){
        const spec=personnelMajestic[i],etat=habitantsMajestic[i];
        if(etat.acteur!==null && !alive(etat.acteur)){
            retirerHabitant(i,maintenant,true);
            continue;
        }
        if(etat.acteur===null){
            if(maintenant<etat.reessai) continue;
            if(!etat.demande){
                N("REQUEST_MODEL",spec.modele);
                etat.demande=true;
            }
            if(!N("HAS_MODEL_LOADED",spec.modele)) continue;
            const debut=spec.parcours[0];
            const lieu=mondeMajestic([debut[0],debut[1],.42]);
            // La première marche du perron se trouve sous le sol continu du hall.
            if(spec.role==="voyageur") lieu[2]=10.48;
            const h=N("CREATE_CHAR",spec.type,spec.modele,...lieu);
            if(alive(h)){
                etat.acteur=h;
                N("SET_CHAR_HEED_THREATS",h,false);
                pauseHabitant(etat,debut,maintenant);
            }else etat.reessai=maintenant+4000;
            N("MARK_MODEL_AS_NO_LONGER_NEEDED",spec.modele);
            etat.demande=false;
            continue;
        }
        if(etat.attend){
            if(maintenant<etat.echeance) continue;
            etat.etape=(etat.etape+1)%spec.parcours.length;
            marcherHabitant(etat,spec,maintenant);
            continue;
        }
        const pt=spec.parcours[etat.etape], cible=mondeMajestic([pt[0],pt[1],.06]);
        const pos=posOf(etat.acteur);
        if(Math.hypot(pos.x-cible[0],pos.y-cible[1])<=.68){
            pauseHabitant(etat,pt,maintenant);
        }else if(maintenant>=etat.echeance){
            // Un joueur peut bloquer le passage. Seul l'objectif de marche est renouvelé.
            marcherHabitant(etat,spec,maintenant);
        }
    }
}
