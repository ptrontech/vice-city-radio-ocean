// Pose graphique du nageur pour Vice City classique. Interfaces publiques CLEO Redux et Plugin-SDK.
#include <algorithm>
#include <cmath>
#include <chrono>
#include "cleo_redux_sdk.h"
#include "CPools.h"
#include "CPed.h"
#include "CPlayerPed.h"
#include "CAnimManager.h"
#include "common.h"
#include "Events.h"

namespace {
using Horloge = std::chrono::steady_clock;
CPed* nageur = nullptr;
float inclinaison = 0.0f;
Horloge::time_point dernierePose;
RwFrame* cadreActif = nullptr;
RwMatrix cadreOriginal;

void avantDessin(CPed* ped) {
    if (!ped || ped != nageur || !ped->m_pRwClump || cadreActif ||
        Horloge::now() - dernierePose > std::chrono::milliseconds(350)) return;
    RwFrame* cadre = static_cast<RwFrame*>(rwObjectGetParent(ped->m_pRwClump));
    if (!cadre) return;
    RwMatrix* m = RwFrameGetMatrix(cadre);
    cadreOriginal = *m;
    cadreActif = cadre;
    const float a = inclinaison * 0.01745329252f;
    const float s = std::sin(a), c = std::cos(a);
    const auto front = m->up, haut = m->at;
    m->up = {front.x*c+haut.x*s, front.y*c+haut.y*s, front.z*c+haut.z*s};
    m->at = {haut.x*c-front.x*s, haut.y*c-front.y*s, haut.z*c-front.z*s};
    RwMatrixUpdate(m);
    RwFrameUpdateObjects(cadre);
    ped->UpdateRpHAnim();
}
void apresDessin(CPed* ped) {
    if (!cadreActif || !ped || ped != nageur) return;
    *RwFrameGetMatrix(cadreActif) = cadreOriginal;
    RwFrameUpdateObjects(cadreActif);
    cadreActif = nullptr;
}
CPed* joueur(int handle) {
    CPed* p = CPools::GetPed(handle);
    return p && p == FindPlayerPed() ? p : nullptr;
}
HandlerResult etat(Context ctx) {
    CPed* p = joueur(static_cast<int>(GetIntParam(ctx)));
    SetIntParam(ctx, p ? static_cast<int>(p->m_nPedFlags.bDrownsInWater) : -1);
    return HandlerResult::CONTINUE;
}
HandlerResult posture(Context ctx) {
    CPed* p = joueur(static_cast<int>(GetIntParam(ctx)));
    const float angle = GetFloatParam(ctx);
    const float cadence = GetFloatParam(ctx);
    if (!p || !p->m_pRwClump) return HandlerResult::CONTINUE;
    if (!(cadence > 0.0f)) {
        if (nageur == p) {
            auto* anim = RpAnimBlendClumpGetAssociation(p->m_pRwClump, ANIM_MAN_DROWN);
            if (anim) anim->m_fBlendDelta = -8.0f;
            nageur = nullptr;
        }
        return HandlerResult::CONTINUE;
    }
    if (!std::isfinite(angle) || !std::isfinite(cadence)) return HandlerResult::CONTINUE;
    const bool nouvelle = nageur != p;
    nageur = p;
    inclinaison = std::clamp(angle, -112.0f, 0.0f);
    dernierePose = Horloge::now();
    auto* anim = RpAnimBlendClumpGetAssociation(p->m_pRwClump, ANIM_MAN_DROWN);
    if (nouvelle || !anim || anim->m_fBlendDelta < 0.0f)
        anim = CAnimManager::BlendAnimation(p->m_pRwClump, ANIM_GROUP_MAN, ANIM_MAN_DROWN, 7.0f);
    if (anim) {
        anim->m_fSpeed = std::clamp(cadence, .5f, 2.0f);
        anim->m_nFlags |= ANIMATION_LOOPED;
    }
    return HandlerResult::CONTINUE;
}
HandlerResult position(Context ctx) {
    CPed* p = joueur(static_cast<int>(GetIntParam(ctx)));
    const float x = GetFloatParam(ctx), y = GetFloatParam(ctx), z = GetFloatParam(ctx);
    if (!p || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) return HandlerResult::CONTINUE;
    const auto ancien = p->GetPosition();
    const float dx=x-ancien.x, dy=y-ancien.y, dz=z-ancien.z;
    if (dx*dx+dy*dy > 1.5f*1.5f || std::abs(dz)>2.25f) return HandlerResult::CONTINUE;
    // Le mouvement du nageur est local ; la téléportation de mission n'est pas utilisée en continu.
    p->SetPosition(x,y,z);
    p->m_vecMoveSpeed.x=0; p->m_vecMoveSpeed.y=0; p->m_vecMoveSpeed.z=0;
    p->RemoveAndAdd();
    p->m_placement.UpdateRW();
    p->UpdateRwFrame();
    return HandlerResult::CONTINUE;
}
void reinitialiser() { nageur=nullptr;cadreActif=nullptr; }
struct Natation {
    Natation() {
        if (GetHostId() != HostId::VC) return;
        RegisterCommand("RADIO_NAGE_ETAT", etat);
        RegisterCommand("RADIO_NAGE_POSITION", position);
        RegisterCommand("RADIO_NAGE_POSTURE", posture);
        OnRuntimeInit(reinitialiser);
        plugin::Events::pedRenderEvent.before += avantDessin;
        plugin::Events::pedRenderEvent.after += apresDessin;
    }
} natation;
}
