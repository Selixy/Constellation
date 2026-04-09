#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);
float4 _WaterFlowMap_TexelSize;  
float4 _WaterPlaneSize;          

half4 ComputeWaterSurface(float2 uv)
{
    // On récupère la taille d'un pixel et on l'agrandit pour le rayon du blur
    float2 d = _WaterFlowMap_TexelSize.xy * 2.5; // On tape à côté pour adoucir

    // Blur 3x3 avec un filtre quasi-Gaussien (efface l'effet on/off aliasing)
    float h_C = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).z;
    float h_L = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x, 0)).z;
    float h_R = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x, 0)).z;
    float h_D = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(0, -d.y)).z;
    float h_U = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(0,  d.y)).z;

    float h_DL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x, -d.y)).z;
    float h_DR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x, -d.y)).z;
    float h_UL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x,  d.y)).z;
    float h_UR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x,  d.y)).z;

    // Moyenne pondérée lissée (adoucissement du grain / bruit de la simulation)
    float blurred_height = (h_C * 4.0 + (h_L + h_R + h_D + h_U) * 2.0 + (h_DL + h_DR + h_UL + h_UR) * 1.0) / 16.0;

    // Image 100% blanche, alpha = hauteur lissée
    float alpha = blurred_height;
    alpha -= 0.5; // On recentre autour de 0.5 pour que les pixels à hauteur nulle soient à moitié transparents (au lieu d'invisibles)

    return half4(1.0, 1.0, 1.0, alpha);
}

#endif
