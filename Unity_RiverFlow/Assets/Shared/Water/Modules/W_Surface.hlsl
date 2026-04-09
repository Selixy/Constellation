#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);
float4 _WaterFlowMap_TexelSize;
float4 _WaterPlaneSize;

half4 ComputeWaterSurface(float2 uv)
{
    float2 d = _WaterFlowMap_TexelSize.xy * 2.5;

    float h_C  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).z;
    float h_L  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x,  0   )).z;
    float h_R  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x,  0   )).z;
    float h_D  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( 0,   -d.y )).z;
    float h_U  = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( 0,    d.y )).z;
    float h_DL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x, -d.y )).z;
    float h_DR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x, -d.y )).z;
    float h_UL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x,  d.y )).z;
    float h_UR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x,  d.y )).z;

    float blurred = (h_C * 4.0 + (h_L + h_R + h_D + h_U) * 2.0 + (h_DL + h_DR + h_UL + h_UR)) / 16.0;

    // Normale de surface depuis le gradient de hauteur
    float gx = h_R - h_L;
    float gy = h_U - h_D;
    float3 normal = normalize(float3(-gx, -gy, 0.1));

    // Encode en couleur RGB [0,1]
    float3 col = normal * 0.5 + 0.5;
    float  alpha = saturate(abs(blurred) * 4.0);
    return half4(col, alpha);
}

#endif
