// Simulation de champ de vélocité 2D — ping-pong RenderTexture (RGFloat)
//
// Pass 0 — Advection semi-Lagrangienne + Dissipation
// Pass 1 — Stamp (injection vélocité radiale depuis les interacteurs)
// Pass 2 — Diffusion Laplacienne (viscosité) → étale la vélocité, crée des interactions
//
// IMPORTANT : vertex shader utilise POSITION+TEXCOORD0 (appdata de Graphics.Blit).
// NOTE OpenGL : _Interactors bindé via _simMat.SetBuffer() côté C#.

Shader "Hidden/WaterSim"
{
    SubShader
    {
        Cull Off ZWrite Off ZTest Always

        // ── Pass 0 : Advection semi-Lagrangienne + Dissipation ────────────────
        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag_advect

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            float  _Dissipation;
            float  _SimDeltaTime;

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

            float4 frag_advect(Varyings i) : SV_Target
            {
                float2 vel = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rg;

                float2 srcUV  = saturate(i.uv - vel * _SimDeltaTime);
                float2 newVel = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, srcUV).rg * _Dissipation;

                float2 bnd = smoothstep(0.0, 0.03, i.uv) * smoothstep(1.0, 0.97, i.uv);
                return float4(newVel * bnd.x * bnd.y, 0.0, 0.0);
            }
            ENDHLSL
        }

        // ── Pass 1 : Stamp — injection de vélocité radiale ────────────────────
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
                float2 vel = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rg;

                for (int n = 0; n < _InteractorCount; n++)
                {
                    WaterInteractor a = _Interactors[n];

                    float2 aUV = (a.position - _WaterPlaneMin.xy) / _WaterPlaneSize.xy;
                    #if UNITY_UV_STARTS_AT_TOP
                        aUV.y = 1.0 - aUV.y;
                    #endif

                    float2 diff_world = (i.uv - aUV) * _WaterPlaneSize.xy;
                    float  dist_world = length(diff_world) + 0.0001;
                    // ✅ Normaliser le vecteur directionnel (magnitude 1, direction correcte)
                    // (avant : divisé par _WaterPlaneSize qui l'écrasait)
                    float2 dir_vel    = diff_world / dist_world;

                    if (a.isImpact == 1)
                    {
                        float ring_r   = a.age * _RingExpandSpeed;
                        float ring_w   = 0.025;
                        float ringFall = exp(-pow(dist_world - ring_r * max(_WaterPlaneSize.x, _WaterPlaneSize.y), 2.0)
                                             / (ring_w * ring_w * _WaterPlaneSize.x * _WaterPlaneSize.x));
                        float timeFade = exp(-a.age * _ImpactDecay);
                        vel += dir_vel * ringFall * timeFade * _StampStrength;
                    }
                    else
                    {
                        float sr_world = _StampRadius * max(_WaterPlaneSize.x, _WaterPlaneSize.y);
                        float falloff  = exp(-dist_world * dist_world / (sr_world * sr_world));
                        vel += dir_vel * falloff * _StampStrength * 0.15;
                    }
                }

                vel = clamp(vel, -2.0, 2.0);
                return float4(vel, 0.0, 0.0);
            }
            ENDHLSL
        }

        // ── Pass 2 : Diffusion Laplacienne (viscosité) ────────────────────────
        // Étale la vélocité vers les voisins → les fronts se "rencontrent" et
        // créent des tourbillons/interactions là où ils se croisent.
        // Condition de stabilité : _Viscosity < 0.25 (sans facteur dt).
        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag_diffuse

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            float4 _MainTex_TexelSize; // auto-rempli par Unity lors du Blit
            float  _Viscosity;         // 0 = aucune diffusion, 0.25 = max stable

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

            float4 frag_diffuse(Varyings i) : SV_Target
            {
                float2 d = _MainTex_TexelSize.xy;

                float2 center = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv              ).rg;
                float2 left   = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv + float2(-d.x, 0  )).rg;
                float2 right  = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv + float2( d.x, 0  )).rg;
                float2 up     = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv + float2( 0,   d.y)).rg;
                float2 down   = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv + float2( 0,  -d.y)).rg;

                // Laplacien discret : mesure la divergence locale de vélocité
                float2 laplacian = left + right + up + down - 4.0 * center;
                float2 result    = center + _Viscosity * laplacian;

                // Réappliquer la frontière absorbante après diffusion
                float2 bnd = smoothstep(0.0, 0.03, i.uv) * smoothstep(1.0, 0.97, i.uv);
                return float4(result * bnd.x * bnd.y, 0.0, 0.0);
            }
            ENDHLSL
        }
    }
}
