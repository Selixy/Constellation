Shader "Custom/S_Water"
{
    Properties
    {
        _BaseColor ("Couleur de Base (Rivière)", Color) = (0.10, 0.35, 0.20, 1.0)
        _SpotColor ("Couleur des Pois d'Eau", Color) = (0.25, 0.55, 0.40, 1.0)
        _Scale ("Densité des Pois / Cellules", Range(1, 100)) = 30.0
        _Speed ("Vitesse du Courant / Vie", Range(0, 5)) = 1.2
        _AlphaMin ("Alpha de Base Minimum", Range(0, 1)) = 0.6
        _AlphaMax ("Alpha de Base Maximum", Range(0, 1)) = 0.8
        _BumpStrength ("Force du Relief (Bump des vagues)", Range(0, 15)) = 2.0
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" "RenderPipeline"="UniversalPipeline" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            
            // Déclaration des variables AVANT l'include !
            float4 _BaseColor;
            float4 _SpotColor;
            float _Scale;
            float _Speed;
            float _AlphaMin;
            float _AlphaMax;
            float _BumpStrength;

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
            };

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                OUT.positionHCS = TransformObjectToHClip(IN.positionOS.xyz);
                OUT.uv          = IN.uv;
                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                return ComputeWaterSurface(IN.uv);
            }
            ENDHLSL
        }
    }
}
