#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

// Champ de vélocité 2D (RG float) exposé globalement par WaterRippleController.
TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);

// DEBUG — visualisation brute du flow field (velocity field).
// Gris neutre (0.5, 0.5) = pas de vélocité.
// Rouge > 0.5 = vélocité +X, Rouge < 0.5 = vélocité -X.
// Vert  > 0.5 = vélocité +Y, Vert  < 0.5 = vélocité -Y.
// Fond blanc = vitesse nulle, toujours opaque.
half4 ComputeWaterSurface(float2 uv)
{
    float2 vel = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).rg;

    // Remap [-1..1] → [0..1] pour visualisation
    float2 vis = vel * 0.5 + 0.5;

    // Canaux : R=vel.x, G=vel.y, B=magnitude
    float speed = length(vel);
    return half4(vis.x, vis.y, saturate(speed), 1.0);
}

#endif
