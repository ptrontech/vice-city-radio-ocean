// Sondes physiques réservées au profil Validation. Chaque lancement reprend sur la rive.
const appuisQuaiRive = [-812, -342, 11.10];
const appuisQuaiPoints = [
    ["entree d'origine", quaiEntree],
    ["raccord rive", quaiParcours[1]],
    ["travee en biais", quaiParcours[3]],
    ["jonction des deux pontons", quaiParcours[5]],
    ["plateforme", quaiParcours[6]],
    ["banc radio", quaiRendezvous]
];
const essaiQuai = {phase:"depart", index:0, depuis:0, haut:0, premier:null, solde:null, reussi:false};

function appuisQuaiReussis() { return essaiQuai.phase === "fin" && essaiQuai.reussi; }

function appuisQuaiDeplacer(player, point, hauteur) {
    const [x,y,z] = point;
    N("REQUEST_COLLISION",x,y);
    if (N("IS_CHAR_IN_ANY_CAR",player)) N("WARP_CHAR_FROM_CAR_TO_COORD",player,x,y,z+hauteur);
    else N("SET_CHAR_COORDINATES",player,x,y,z+hauteur);
}

function appuisQuaiFin(ok, raison, player) {
    const [caisse,reserve,generation] = essaiQuai.solde;
    const intact = state.caisse === caisse && state.reserve === reserve && state.generation === generation;
    verdict("quai caisse, reserve et generation intactes",intact);
    essaiQuai.reussi = verdict("quai " + raison,ok && intact);
    essaiQuai.phase = "fin";
    if (!ok && alive(player)) appuisQuaiDeplacer(player,appuisQuaiRive,0);
    report("FIN appuis quai resultat=" + (essaiQuai.reussi ? "OK" : "ECHEC"));
    return true;
}

// Le véritable menu fournit le callback du bulletin. Les autres boutons restent inertes
// pendant ce seul rendu, y compris si un nouveau contrat est ajouté en tête de liste.
function appuisQuaiBulletin(pos) {
    const afficherBouton = button;
    let relever = null;
    openMenu("quai");
    try {
        button = (libelle, action) => {
            if (libelle === "Relever le bulletin du ponton") relever = action;
            afficherBouton(libelle,() => {});
        };
        drawMenu(pos);
    } finally {
        button = afficherBouton;
        menu = "";
    }
    if (!relever) return false;
    const instant = Date.now(), ancienneEcheance = noticeUntil;
    noticeUntil = 0;
    relever();
    if (!noticeUntil) { noticeUntil = ancienneEcheance; return false; }
    report("quai bulletin au banc | " + message);
    return noticeUntil > instant && /^(Le ponton est ouvert\.|Message du port\.)/.test(message);
}

function appuisQuaiMesure(player) {
    const pos = posOf(player);
    return {...pos, sec:N("IS_CHAR_ON_FOOT",player) && !N("IS_CHAR_IN_WATER",player), lieu:quaiPlace(pos)};
}

function testAppuisQuai(player,free) {
    if (mode !== "Validation") return false;
    if (essaiQuai.phase === "fin") return true;
    if (!free || !alive(player)) {
        if (essaiQuai.phase === "depart") return false;
        // La campagne peut reprendre la main. Laisser alors le joueur à son script.
        return appuisQuaiFin(false,"essai interrompu pendant les mesures",null);
    }
    const now = clockNow();
    if (essaiQuai.phase === "depart") {
        essaiQuai.solde = [state.caisse,state.reserve,state.generation];
        report("QUAI attente sur la rive de Little Havana");
        N("LOAD_SCENE",...appuisQuaiRive);
        appuisQuaiDeplacer(player,appuisQuaiRive,0);
        essaiQuai.depuis = now;
        essaiQuai.phase = "chargement";
        return false;
    }
    if (essaiQuai.phase === "chargement") {
        const age = now - essaiQuai.depuis;
        const pos = posOf(player);
        if (!quaiReady() || !near(pos,appuisQuaiRive,4)) {
            if (age < 18000) return false;
            report("quai chargement ouvert=" + quaiReady() + " pos=" + JSON.stringify(pos));
            return appuisQuaiFin(false,"delai de chargement depasse",player);
        }
        if (age < 750) return false;
        verdict("quai charge pres de la rive",true);
        essaiQuai.phase = "depot";
    }
    const [nom,point] = appuisQuaiPoints[essaiQuai.index];
    if (essaiQuai.phase === "depot") {
        // Ce z absolu place Tommy dans l'air, sans recherche de sol ni gel du personnage.
        appuisQuaiDeplacer(player,point,1.6);
        essaiQuai.haut = posOf(player).z;
        essaiQuai.depuis = now;
        essaiQuai.phase = "chute";
        return false;
    }
    if (essaiQuai.phase === "chute") {
        if (now - essaiQuai.depuis < 1250) return false;
        essaiQuai.premier = appuisQuaiMesure(player);
        essaiQuai.depuis = now;
        essaiQuai.phase = "stabilite";
        return false;
    }
    const ecart = now - essaiQuai.depuis;
    if (ecart < 600) return false;
    const a = essaiQuai.premier, b = appuisQuaiMesure(player);
    const dernier = essaiQuai.index === appuisQuaiPoints.length-1;
    const attendu = dernier ? "quai" : "";
    const surPlanches = [a,b].every(p => p.sec && Math.abs(p.z-point[2]) <= 0.45 &&
        Math.hypot(p.x-point[0],p.y-point[1]) <= 0.85 && essaiQuai.haut-p.z >= 0.6);
    const stable = Math.abs(a.z-b.z) <= 0.10 && Math.hypot(a.x-b.x,a.y-b.y) <= 0.30;
    report("quai " + nom + " XY=" + point.slice(0,2).join(",") + " z_attendu=" + point[2] +
        " z_depot=" + essaiQuai.haut.toFixed(2) + " z1=" + a.z.toFixed(2) + " z2=" + b.z.toFixed(2) +
        " intervalle_ms=" + ecart + " declencheurs=" + (a.lieu || "aucun") + "/" + (b.lieu || "aucun"));
    const solide = verdict("appui stable " + nom,surPlanches && stable);
    const balise = verdict("declencheur " + (attendu || "absent") + " " + nom,a.lieu === attendu && b.lieu === attendu);
    if (!solide || !balise) return appuisQuaiFin(false,"echec au point " + nom,player);
    if (dernier) return appuisQuaiFin(appuisQuaiBulletin(b),"consultation du bulletin au banc",player);
    essaiQuai.index++;
    essaiQuai.phase = "depot";
    return false;
}
