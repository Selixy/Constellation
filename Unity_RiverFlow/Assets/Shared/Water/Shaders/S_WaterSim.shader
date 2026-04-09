Shader "Hidden/WaterSim"
{
    SubShader
    {
        Cull Off ZWrite Off ZTest Always

        // ── PASS 0 : ADVECTION SEMI-LAGRANGIENNE + RÉFLEXION AUX BORDS ─────────
        // Texture : R=velX, G=velY, B=height, A=unused
        // Chaque pixel "remonte" son trajectoire (srcUV = uv - vel*dt),
        // lit l'état à la source, et applique la réflexion si on traverse un bord.
        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag_advect

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            float _Dissipation;
            float _SimDeltaTime;

            struct Attributes { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings   { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.pos = TransformObjectToHClip(v.vertex.xyz);
                o.uv  = v.uv;
                #if UNITY_UV_STARTS_AT_TOP
                    o.uv.y = 1.0 - o.uv.y;
                #endif
                return o;
            }

            float4 frag_advect(Varyings i) : SV_Target
            {
                float2 vel = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rg;

                // Backtrack : d'où vient la particule qui arrive en i.uv ?
                float2 srcUV = i.uv - vel * _SimDeltaTime;

                // Réflexion aux bords (Neumann cinématique) :
                // Si srcUV sort du domaine, on replie + on inverse le composant normal.
                float2 velSign = float2(1.0, 1.0);
                if (srcUV.x < 0.0) { srcUV.x =  -srcUV.x;      velSign.x = -1.0; }
                if (srcUV.x > 1.0) { srcUV.x = 2.0 - srcUV.x;  velSign.x = -1.0; }
                if (srcUV.y < 0.0) { srcUV.y =  -srcUV.y;       velSign.y = -1.0; }
                if (srcUV.y > 1.0) { srcUV.y = 2.0 - srcUV.y;  velSign.y = -1.0; }
                srcUV = saturate(srcUV);

                float4 src = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, srcUV);

                // Appliquer l'inversion + dissipation
                float2 newVel    = src.rg * velSign * _Dissipation;
                float  newHeight = src.b  * _Dissipation;

                return float4(newVel, newHeight, 0.0);
            }
            ENDHLSL
        }

        // ── PASS 1 : STAMP (injection de vélocité + hauteur) ────────────────────
        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag_stamp
            #pragma target   4.5

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "../Modules/W_Input.hlsl"

            StructuredBuffer<WaterInteractor> _Interactors;
            int _InteractorCount;

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);

            float4 _WaterPlaneMin;
            float4 _WaterPlaneSize;
            float  _StampRadius;
            float  _StampStrength;
            float  _ImpactDecay;

            struct Attributes { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings   { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.pos = TransformObjectToHClip(v.vertex.xyz);
                o.uv  = v.uv;
                #if UNITY_UV_STARTS_AT_TOP
                    o.uv.y = 1.0 - o.uv.y;
                #endif
                return o;
            }

            float4 frag_stamp(Varyings i) : SV_Target
            {
                float4 curr   = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float2 vel    = curr.rg;
                float  height = curr.b;

                for (int n = 0; n < _InteractorCount; n++)
                {
                    WaterInteractor a = _Interactors[n];

                    // Position UV de l'interacteur
                    float2 aUV = (a.position - _WaterPlaneMin.xy) / _WaterPlaneSize.xy;
                    #if UNITY_UV_STARTS_AT_TOP
                        aUV.y = 1.0 - aUV.y;
                    #endif

                    // Distance monde + direction radiale sortante
                    float2 diff_world = (i.uv - aUV) * _WaterPlaneSize.xy;
                    float  dist_world = length(diff_world) + 0.0001;
                    float2 dir        = diff_world / dist_world;

                    float sr_world = _StampRadius * max(_WaterPlaneSize.x, _WaterPlaneSize.y);
                    float falloff  = exp(-dist_world * dist_world / (sr_world * sr_world));

                    if (a.isImpact == 1)
                    {
                        // Impact (pied levé) : burst de vélocité radiale + bosse de hauteur
                        float fade = exp(-a.age * _ImpactDecay);
                        if (fade > 0.01)
                        {
                            vel    += dir    * falloff * _StampStrength * fade;
                            height += falloff * _StampStrength * 0.5 * fade;
                        }
                    }
                    else
                    {
                        // Persistant (pied posé) : pousse l'eau doucement vers l'extérieur
                        float freshness = exp(-a.age * 5.0);
                        if (freshness > 0.1)
                        {
                            vel    += dir    * falloff * _StampStrength * 0.4 * freshness;
                            height -= falloff * _StampStrength * 0.2 * freshness;
                        }
                    }
                }

                vel    = clamp(vel,    -20.0, 20.0);
                height = clamp(height, -5.0,   5.0);

                return float4(vel, height, 0.0);
            }
            ENDHLSL
        }
    }
}
