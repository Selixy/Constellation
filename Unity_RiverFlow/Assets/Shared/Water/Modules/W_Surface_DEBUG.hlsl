#ifndef W_SURFACE_DEBUG_INCLUDED
#define W_SURFACE_DEBUG_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);

// ── Diagnostic : Visualisation directe du flow map ──────────────────────────
// Affiche les vecteurs comme couleurs [R=composante X, G=composante Y]
half4 ComputeWaterSurface_DEBUG(float2 uv)
{
    float2 vel   = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).rg;
    float  speed = length(vel);
    
    // ── Afficher directement le vecteur (valeurs [ -2 .. 2 ] → [0 .. 1]) ──────
    // Rouge = composante X, Vert = composante Y, Alpha = magnitude
    float3 velViz = float3(
        vel.x * 0.25 + 0.5,   // -2..2 → 0..1 (rouge=droite, dark=gauche)
        vel.y * 0.25 + 0.5,   // -2..2 → 0..1 (vert=up, dark=down)
        speed * 0.5           // Magnitude en blue
    );
    float alpha = saturate(speed * 0.8);
    
    return half4(velViz, alpha);
}

// ── Version colorée : test de direction ──────────────────────────────────
// Affiche différentes couleurs selon la région du flux
half4 ComputeWaterSurface_DEBUG_FLOW(float2 uv)
{
    float2 vel   = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).rg;
    float  speed = length(vel);
    
    half3 color = half3(0, 0, 0);
    
    // Quadrants : (+X,+Y), (-X,+Y), (-X,-Y), (+X,-Y)
    if (vel.x > 0.1 && vel.y > 0.1)  color = half3(1, 1, 0);   // Jaune (droite-up)
    if (vel.x < -0.1 && vel.y > 0.1) color = half3(1, 0, 1);  // Magenta (gauche-up)
    if (vel.x < -0.1 && vel.y < -0.1) color = half3(0, 1, 1); // Cyan (gauche-down)
    if (vel.x > 0.1 && vel.y < -0.1)  color = half3(1, 0, 0); // Rouge (droite-down)
    
    // Noir si trop faible
    if (speed < 0.05) color = half3(0, 0, 0);
    
    half alpha = saturate(speed);
    return half4(color, alpha);
}

#endif
