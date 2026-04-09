#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);
float4 _WaterFlowMap_TexelSize;  // Auto-fourni par Unity : (1/width, 1/height, width, height)

// uv : coordonnées UV du mesh [0,1]
half4 ComputeWaterSurface(float2 uv)
{
    // Lire la vélocité et ses voisins pour dériver des gradients
    float2 vel_center = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).rg;
    
    // Magnitude principale
    float speed = length(vel_center);
    
    // Si aucune vélocité : alpha = 0 complètement transparent
    if (speed < 0.001)
        return half4(1.0, 1.0, 1.0, 0.0);
    
    // Offset adaptatif à la résolution (1 pixel = _WaterFlowMap_TexelSize.x)
    float offset = _WaterFlowMap_TexelSize.x * 3.0;  // 3 pixels de distance — ripples fins
    
    float2 vel_right = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(offset, 0)).rg;
    float2 vel_left  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-offset, 0)).rg;
    float2 vel_up    = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(0, offset)).rg;
    float2 vel_down  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(0, -offset)).rg;
    
    // Laplacien magnitude : (sum neighbors) - 4*center
    float laplacian_x = vel_right.x + vel_left.x + vel_up.x + vel_down.x - 4.0 * vel_center.x;
    float laplacian_y = vel_right.y + vel_left.y + vel_up.y + vel_down.y - 4.0 * vel_center.y;
    float laplacian = abs(laplacian_x) + abs(laplacian_y);
    
    // Nuance d'alpha lissée — très subtile au début
    float ripple_detail = saturate(laplacian * 0.08 + speed * 0.004);
    
    // Couleur blanc, alpha variable selon les ripples
    half3 color = half3(1.0, 1.0, 1.0);
    half alpha = ripple_detail;
    
    return half4(color, alpha);
}

#endif
