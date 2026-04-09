#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);

// uv : coordonnées UV du mesh [0,1]
half4 ComputeWaterSurface(float2 uv)
{
    // Lire la vélocité de la flow map
    float2 vel = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).rg;
    
    // Magnitude du vecteur vitesse (magnitude = amplitude du ripple)
    float speed = length(vel);
    
    // Ripples = blanc simplement basé sur la vélocité
    // Au repos (speed = 0) : alpha = 0 (transparent)
    // En mouvement : alpha augmente (blanc visible)
    half3 color = half3(1.0, 1.0, 1.0);  // blanc
    half alpha = saturate(speed * 2.0);   // alpha proportionnel à la vélocité
    
    return half4(color, alpha);
}

#endif
