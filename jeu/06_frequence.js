// Troisième mission de la régie : « La fréquence perdue ». Milo, le technicien d'Inès, a disparu avec l'émetteur.
// Tommy suit deux ou trois indices sur Ocean Drive (cfg.collectes), rencontre Milo à pied, puis le ramène chez Inès.
// Le cœur commun gère la sphère et le blip (target/clearObjective), l'abandon (cancelJob) et le tick (tickJob).
const primeFrequence = 440;
const modeleMilo = 28;
const distanceRencontreMilo = 5;
const distanceRetourMilo = 18;
const indicesFrequence = [
    "Le barman a vu Milo charger une antenne dans un coffre, puis remonter Ocean Drive.",
    "Une affichette de reparation, ecrite de la main de Milo, donne un dernier rendez-vous sur la plage.",
    "Un vendeur de glaces confirme que Milo se cache pres du repere suivant."
];

function frequenceBloquee() {
    // ONMISSION appartient à Vice City : une mission Rockstar garde toujours la priorité.
    return typeof ONMISSION !== "undefined" && Boolean(ONMISSION);
}

function frequenceLieux() {
    // Seuls des repères complets, finis et distincts sont retenus. La rotation suit la réputation.
    const valides = [];
    for (const p of Array.isArray(cfg.collectes) ? cfg.collectes : []) {
        if (!Array.isArray(p) || p.length < 3 || !p.slice(0, 3).every(Number.isFinite)) continue;
        if (valides.some(q => q[0] === p[0] && q[1] === p[1] && q[2] === p[2])) continue;
        valides.push([p[0], p[1], p[2]]);
    }
    if (valides.length < 2) return [];
    const depart = state.missions % valides.length;
    return valides.slice(depart).concat(valides.slice(0, depart)).slice(0, 3);
}

function frequenceEligible(pos, player) {
    if (mission || frequenceBloquee() || state.missions < 1) return false;
    if (!pos || !Number.isFinite(pos.x) || !Number.isFinite(pos.y) || !Number.isFinite(pos.z)) return false;
    if (!alive(player) || N("IS_CHAR_IN_ANY_CAR", player)) return false;
    return near(pos, contact, 8);
}

function frequencyBrief(m = mission) {
    if (!m || m.kind !== "frequence") return "Milo, le technicien d'Ines, a disparu avec l'emetteur.";
    const n = m.places.length;
    if (m.step < n - 1) return "Indice " + (m.step + 1) + "/" + (n - 1) + " : " + m.clue + " Va au repere jaune.";
    if (m.step === n - 1) return "Trouve Milo a pied au repere jaune. " + m.clue;
    return "Ramene Milo a Ines, a pied ou en voiture. Garde une place libre et descendez devant la radio.";
}

function startFrequency(pos) {
    const player = N("GET_PLAYER_CHAR", 0);
    if (!frequenceEligible(pos, player)) return false;
    const places = frequenceLieux();
    if (places.length < 2) return false;
    mission = {
        kind: "frequence", step: 0, places, milo: null, model: false, paid: false, nextHint: 0,
        trajet: "a_pied", voiture: null, prochainOrdre: 0, prochaineVerification: 0,
        clue: indicesFrequence[0], stop: clockNow() + cfg.delaiSecondes * 1000
    };
    target(places[0]);
    menu = "";
    say("La frequence perdue. " + frequencyBrief(mission));
    return true;
}

function clearFrequency(m = mission) {
    // Idempotent : supprime Milo et libère le modèle demandé, sans toucher au blip ni à la sphère.
    if (!m || m.kind !== "frequence") return;
    removePed(m.milo);
    m.milo = null;
    if (m.model) {
        N("MARK_MODEL_AS_NO_LONGER_NEEDED", modeleMilo);
        m.model = false;
    }
}

function frequenceAbandon(text) {
    cancelJob(text);
}

function frequenceSpawnMilo(m) {
    if (!m.model) {
        N("REQUEST_MODEL", modeleMilo);
        m.model = true;
    }
    if (!N("HAS_MODEL_LOADED", modeleMilo)) return;
    const p = m.places[m.places.length - 1];
    const h = N("CREATE_CHAR", 4, modeleMilo, p[0] + 1.5, p[1], ground(p));
    N("MARK_MODEL_AS_NO_LONGER_NEEDED", modeleMilo);
    m.model = false;
    if (!alive(h)) {
        removePed(h);
        return;
    }
    N("SET_CHAR_HEADING", h, 95);
    N("SET_CHAR_OBJ_WAIT_ON_FOOT", h);
    m.milo = h;
}

function miloAuMemeNiveau(pos, milo, rayon) {
    return Math.abs(pos.z - milo.z) < 4.5 && Math.hypot(pos.x - milo.x, pos.y - milo.y) <= rayon;
}

function garderPlaceMilo(pos) {
    if (!mission || mission.kind !== "frequence" || mission.step !== mission.places.length) return false;
    const milo = mission.milo;
    return alive(milo) && !N("IS_CHAR_IN_ANY_CAR", milo) && miloAuMemeNiveau(pos, posOf(milo), 22);
}

function deplacerMilo(m, pos, player) {
    const t = clockNow();
    if (t < m.prochaineVerification) return;
    m.prochaineVerification = t + 350;
    const miloEnVoiture = N("IS_CHAR_IN_ANY_CAR", m.milo);
    const voiture = N("IS_CHAR_IN_ANY_CAR", player) ? N("STORE_CAR_CHAR_IS_IN_NO_SAVE", player) : null;
    if (voiture === null && !miloEnVoiture) {
        if (m.trajet !== "a_pied") {
            N("SET_CHAR_OBJ_NO_OBJ", m.milo);
            N("SET_CHAR_AS_LEADER", m.milo, player);
        }
        m.trajet = "a_pied";
        m.voiture = null;
        return;
    }
    if (voiture !== null && miloEnVoiture && N("IS_CHAR_IN_CAR", m.milo, voiture)) {
        m.trajet = "a_bord";
        m.voiture = voiture;
        return;
    }
    if (miloEnVoiture) {
        if (m.trajet !== "descente" || t >= m.prochainOrdre) {
            N("SET_CHAR_OBJ_LEAVE_ANY_CAR", m.milo);
            m.trajet = "descente";
            m.prochainOrdre = t + 3200;
        }
        return;
    }
    if (voiture === null || (voiture === m.voiture && t < m.prochainOrdre)) return;
    m.voiture = voiture;
    m.prochainOrdre = t + 1200;
    if (Math.abs(N("GET_CAR_SPEED", voiture)) > 2.5 || !miloAuMemeNiveau(pos, posOf(m.milo), 22) || !seatAvailable(voiture)) return;
    N("SET_CHAR_OBJ_ENTER_CAR_AS_PASSENGER", m.milo, voiture);
    m.trajet = "embarquement";
    m.prochainOrdre = t + 3200;
}

function frequenceRegler(m) {
    if (m.paid) return;
    const ok = change(s => {
        s.missions++;
        s.caisse += primeFrequence;
        s.xp += s.equipe;
        s.reserve += (s.local ? cfg.revenu : 0) + revenuEquipe(s) + propertyIncome(s);
    });
    if (!ok) return;
    m.paid = true;
    // Milo redevient un piéton ordinaire : il ne doit pas être supprimé par le nettoyage de la mission.
    const milo = m.milo;
    m.milo = null;
    if (alive(milo)) {
        N("SET_CHAR_OBJ_NO_OBJ", milo);
        N("MARK_CHAR_AS_NO_LONGER_NEEDED", milo);
    }
    clearFrequency(m);
    cancelJob("");
    say("Frequence retrouvee. +" + primeFrequence + " $ et un point de reputation. Reputation " + state.missions + ".");
}

function tickFrequency(pos, player) {
    const m = mission;
    if (!m || m.kind !== "frequence" || m.paid) return;
    if (frequenceBloquee()) { frequenceAbandon(""); return; }
    if (clockNow() > m.stop) { frequenceAbandon("Delai expire. Milo reste introuvable pour le moment."); return; }
    if (m.milo !== null && !alive(m.milo)) { frequenceAbandon("Milo n'a pas survecu. La radio perd la trace de la frequence."); return; }
    const n = m.places.length;
    if (m.step < n - 1) {
        if (!near(pos, m.places[m.step], 5)) return;
        m.step++;
        m.clue = indicesFrequence[Math.min(m.step, indicesFrequence.length - 1)];
        target(m.places[m.step]);
        say(frequencyBrief(m));
        return;
    }
    if (m.step === n - 1) {
        const lieu = m.places[n - 1];
        if (m.milo === null) {
            if (near(pos, lieu, 78)) frequenceSpawnMilo(m);
            return;
        }
        if (N("IS_CHAR_IN_ANY_CAR", player)) return;
        const milo = N("GET_CHAR_COORDINATES", m.milo);
        if (!near(pos, lieu, 6) || !miloAuMemeNiveau(pos, milo, distanceRencontreMilo)) return;
        m.step = n;
        N("SET_CHAR_OBJ_NO_OBJ", m.milo);
        N("SET_CHAR_AS_LEADER", m.milo, player);
        target(contact);
        say("Milo : l'emetteur est sauf. Ramene-moi chez Ines. " + frequencyBrief(m));
        return;
    }
    deplacerMilo(m, pos, player);
    if (!near(pos, contact, 5) || N("IS_CHAR_IN_ANY_CAR", player) || N("IS_CHAR_IN_ANY_CAR", m.milo)) return;
    const milo = posOf(m.milo);
    if (!miloAuMemeNiveau(pos, milo, distanceRetourMilo)) {
        const t = clockNow();
        if (t >= m.nextHint) { m.nextHint = t + 4000; say("Milo est reste en arriere. Attends-le devant Ines."); }
        return;
    }
    frequenceRegler(m);
}
