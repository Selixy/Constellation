Shader "Custom/S_Water"
{
    Properties
    {
        _RefractionStrength ("Refraction Strength", Range(0, 0.1)) = 0.02
    }

    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" "RenderPipeline"="UniversalPipeline" }
        // Pas de Blend — on écrit directement la couleur réfractée + alpha
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareOpaqueTexture.hlsl"
            #include "Modules/W_Surface.hlsl"

            float _RefractionStrength;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv         : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionHCS : SV_POSITION;
                float2 uv          : TEXCOORD0;
                float4 screenPos   : TEXCOORD1;
            };

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                OUT.positionHCS = TransformObjectToHClip(IN.positionOS.xyz);
                OUT.uv          = IN.uv;
                OUT.screenPos   = ComputeScreenPos(OUT.positionHCS);
                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                // ── Normale de surface depuis W_Surface ──────────────────────
                float2 d = _WaterFlowMap_TexelSize.xy * 2.5;
                float h_L = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2(-d.x, 0)).z;
                float h_R = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2( d.x, 0)).z;
                float h_D = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2(0, -d.y)).z;
                float h_U = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2(0,  d.y)).z;
                float h_C = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv).z;

                float gx = h_R - h_L;
                float gy = h_U - h_D;
                float2 normalXY = float2(gx, gy); // XY de la normale de surface

                // ── UV écran ─────────────────────────────────────────────────
                float2 screenUV = IN.screenPos.xy / IN.screenPos.w;

                // ── Réfraction : décale les UV écran par la normale ──────────
                float2 refractUV = screenUV + normalXY * _RefractionStrength;

                half3 refractedColor = SampleSceneColor(refractUV);

                // ── Alpha : visible là où il y a de la perturbation ──────────
                float h_DL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2(-d.x, -d.y)).z;
                float h_DR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2( d.x, -d.y)).z;
                float h_UL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2(-d.x,  d.y)).z;
                float h_UR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2( d.x,  d.y)).z;
                float blurred = (h_C * 4.0 + (h_L + h_R + h_D + h_U) * 2.0 + (h_DL + h_DR + h_UL + h_UR)) / 16.0;
                float alpha = saturate(abs(blurred) * 4.0);

                return half4(refractedColor, alpha);
            }
            ENDHLSL
        }
    }
}
