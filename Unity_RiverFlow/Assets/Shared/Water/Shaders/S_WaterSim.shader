Shader "Hidden/WaterSim"
{
    SubShader
    {
        Cull Off ZWrite Off ZTest Always

        // --- PASS 0 : PROPAGATION DE LA HAUTEUR (ALGO HYPER CLASSIQUE D'EAU 2D) ---
        // On repasse à l'onde "Standard" (height_new = hauteur basée sur ses voisins)
        // car l'eau peu profonde Shallow Water 3D avec vitesse est complexe à faire rebondir sans éclater.
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

                // Condition de Neumann (h_ghost = h_bord) via saturate :
                // WrapMode.Clamp + saturate() = le pixel fantôme hors domaine
                // est identique au pixel de bord → gradient nul → rebond pur.
                float2 uvL = float2(max(i.uv.x - d.x, 0.0),  i.uv.y);
                float2 uvR = float2(min(i.uv.x + d.x, 1.0),  i.uv.y);
                float2 uvD = float2(i.uv.x, max(i.uv.y - d.y, 0.0));
                float2 uvU = float2(i.uv.x, min(i.uv.y + d.y, 1.0));

                float3 center = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rgb;
                float h_L = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvL).z;
                float h_R = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvR).z;
                float h_D = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvD).z;
                float h_U = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvU).z;

                // La formule hyper stable des heightmaps d'eau 2D
                // R = Ancienne hauteur, G = Rien pour le moment, Z = Hauteur Courante
                
                // height = center.z
                // prev_height = center.r (stocké)
                
                float current_height = center.z;
                float previous_height = center.r;
                
                // Formule de propagation d'onde classique avec amortissement (_Damping contrôlé)
                // h_new = (voisins - h_prev) * damp; 
                // Pour que ça ne plante jamais, avec inertie intégrée :
                
                float height_diff = ((h_L + h_R + h_D + h_U) / 2.0) - previous_height;
                
                // On dissipe l'onde très lentement avec Damping (0.99)
                float new_height = height_diff * clamp(_Damping, 0.8, 0.999);

                new_height = clamp(new_height, -5.0, 5.0);

                // On sauvegarde : 
                // Nouvelle 'Hauteur Courante' -> Dans Z
                // Ancienne 'Hauteur Courante' (qui devient l'ancienne) -> Dans R
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
                        // Impulsion ponctuelle courte : on injecte seulement pendant les
                        // premières 0.06s. La wave equation propage ensuite un anneau
                        // physique qui rebondit sur les bords (Neumann).
                        // (l'ancien code dessinait l'anneau directement frame par frame
                        //  → pas de rebond possible car hors physique)
                        if (a.age < 0.06)
                        {
                            float sr_world = _StampRadius * max(_WaterPlaneSize.x, _WaterPlaneSize.y);
                            float falloff  = exp(-dist_world * dist_world / (sr_world * sr_world));
                            float burst    = 1.0 - (a.age / 0.06); // fondu rapide
                            height += falloff * _StampStrength * 4.0 * burst;
                        }
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
                
                // On met à jour Z (Hauteur)
                return float4(center.r, 0.0, height, 0.0);
            }
            ENDHLSL
        }
    }
}
