Shader "Hidden/WaterSim"
{
    SubShader
    {
        Cull Off ZWrite Off ZTest Always

        // --- PASS 0 : PROPAGATION DE LA HAUTEUR (ALGO HYPER CLASSIQUE D'EAU 2D) ---
        // R = Ancienne hauteur (prev), G = inutilisé, B = Hauteur courante (curr)
        // Formule Verlet : h_new = (voisins/2) - h_prev, puis * damping
        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag_wave

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            float4 _MainTex_TexelSize;
            float  _Damping;

            struct Attributes { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings   { float4 pos    : SV_POSITION; float2 uv : TEXCOORD0; };

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

            float4 frag_wave(Varyings i) : SV_Target
            {
                float2 d = _MainTex_TexelSize.xy;

                // Neumann BC : gradient nul au bord → rebond
                float2 uvL = float2(max(i.uv.x - d.x, 0.0), i.uv.y);
                float2 uvR = float2(min(i.uv.x + d.x, 1.0), i.uv.y);
                float2 uvD = float2(i.uv.x, max(i.uv.y - d.y, 0.0));
                float2 uvU = float2(i.uv.x, min(i.uv.y + d.y, 1.0));

                float3 center = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rgb;
                float h_L = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvL).z;
                float h_R = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvR).z;
                float h_D = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvD).z;
                float h_U = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvU).z;

                float current_height  = center.z;
                float previous_height = center.r;

                // Verlet : h_new = (somme voisins / 2) - h_prev, puis dissipation
                float new_height = ((h_L + h_R + h_D + h_U) / 2.0) - previous_height;
                new_height *= clamp(_Damping, 0.8, 0.999);
                new_height  = clamp(new_height, -5.0, 5.0);

                // R = ancienne courante (devient prev), B = nouvelle courante
                return float4(current_height, 0.0, new_height, 0.0);
            }
            ENDHLSL
        }

        // --- PASS 1 : STAMP (RIPPLES) ---
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
            float  _SimDeltaTime;
            float  _RingExpandSpeed;
            float  _ImpactDecay;

            struct Attributes { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings   { float4 pos    : SV_POSITION; float2 uv : TEXCOORD0; };

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
                float3 center = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rgb;
                float height  = center.z;

                for (int n = 0; n < _InteractorCount; n++)
                {
                    WaterInteractor a = _Interactors[n];

                    float2 aUV = (a.position - _WaterPlaneMin.xy) / _WaterPlaneSize.xy;
                    #if UNITY_UV_STARTS_AT_TOP
                        aUV.y = 1.0 - aUV.y;
                    #endif

                    float2 diff_world = (i.uv - aUV) * _WaterPlaneSize.xy;
                    float dist_world = length(diff_world);

                    if (a.isImpact == 1)
                    {
                        float ring_r   = a.age * _RingExpandSpeed;
                        float ring_w   = 0.005;
                        float ringFall = exp(-pow(dist_world - ring_r * max(_WaterPlaneSize.x, _WaterPlaneSize.y), 2.0)
                                             / (ring_w * ring_w * _WaterPlaneSize.x * _WaterPlaneSize.x));
                        float timeFade = exp(-a.age * _ImpactDecay);
                        height += ringFall * timeFade * _StampStrength * 4.0;
                    }
                    else
                    {
                        float freshness = exp(-a.age * 5.0);
                        if (freshness > 0.1)
                        {
                            float sr_world = _StampRadius * max(_WaterPlaneSize.x, _WaterPlaneSize.y);
                            float falloff  = exp(-dist_world * dist_world / (sr_world * sr_world));
                            height -= falloff * _StampStrength * 0.5 * freshness;
                        }
                    }
                }

                height = clamp(height, -5.0, 5.0);
                return float4(center.r, 0.0, height, 0.0);
            }
            ENDHLSL
        }
    }
}
