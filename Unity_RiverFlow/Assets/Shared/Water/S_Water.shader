Shader "Custom/S_Water"
{
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" "RenderPipeline"="UniversalPipeline" }
        ZWrite Off
        Cull Off
        Blend SrcAlpha OneMinusSrcAlpha

        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareOpaqueTexture.hlsl"
            #include "Modules/W_Surface.hlsl"

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
                float2 d = _WaterFlowMap_TexelSize.xy * 2.5;
                float h_L = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2(-d.x,  0   )).z;
                float h_R = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2( d.x,  0   )).z;
                float h_D = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2( 0,   -d.y )).z;
                float h_U = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, IN.uv + float2( 0,    d.y )).z;

                // Normale de surface → décalage réfraction
                float2 normalXY  = float2(h_R - h_L, h_U - h_D);
                float2 screenUV  = IN.screenPos.xy / IN.screenPos.w;
                float2 refractUV = screenUV + normalXY * 0.02;

                half3 scene = SampleSceneColor(refractUV);

                // Alpha = magnitude de la distorsion uniquement.
                // Pas de vague → normalXY=0 → alpha=0 → totalement transparent.
                // Avec vague → alpha>0 → montre la scène décalée.
                float distortion = saturate(length(normalXY) * 30.0);
                return half4(scene, distortion);
            }
            ENDHLSL
        }
    }
}
