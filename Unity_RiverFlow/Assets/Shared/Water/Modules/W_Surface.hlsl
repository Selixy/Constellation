#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);
float4 _WaterFlowMap_TexelSize;  
float4 _WaterPlaneSize;          

half4 ComputeWaterSurface(float2 uv)
{
    // ── DEBUG : visualisation brute des canaux de la texture ──────────────────
    // R = prev_height (rouge si positif)
    // G = 0 actuellement (vert = rien)
    // B = curr_height  (bleu si positif, valeurs négatives = invisible)
    float4 raw = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv);

    // curr_height peut être négatif (creux) ou positif (crête)
    // On mappe : positif → blanc, négatif → rouge, zéro → noir
    float h = raw.z; // hauteur courante
    float pos = max( h, 0.0) * 0.5; // crêtes en blanc/vert
    float neg = max(-h, 0.0) * 0.5; // creux en rouge
    return half4(pos + neg, pos, pos, 1.0); // opaque pour debug
}

#endif
