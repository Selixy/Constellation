#ifndef W_SURFACE_INCLUDED
#define W_SURFACE_INCLUDED

TEXTURE2D(_WaterFlowMap); SAMPLER(sampler_WaterFlowMap);
float4 _WaterFlowMap_TexelSize;  
float4 _WaterPlaneSize;          

// Générateur pseudo-aléatoire 2D (utilisé pour les reflets / pois d'eau)
float2 random2_water(float2 p) {
    return frac(sin(float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)))) * 43758.5453);
}

float random1_water(float2 p) {
    return frac(sin(dot(p, float2(12.9898, 78.233))) * 43758.5453);
}

// Bruit simple (Value Noise) pour le masque
float noise_water(float2 st) {
    float2 i = floor(st);
    float2 f = frac(st);

    float a = random1_water(i);
    float b = random1_water(i + float2(1.0, 0.0));
    float c = random1_water(i + float2(0.0, 1.0));
    float d = random1_water(i + float2(1.0, 1.0));

    float2 u = f * f * (3.0 - 2.0 * f);

    return lerp(a, b, u.x) +
            (c - a)* u.y * (1.0 - u.x) +
            (d - b) * u.x * u.y;
}

half4 ComputeWaterSurface(float2 uv)
{
    // ----- 1. TON SYSTÈME DE VAGUES PHYSIQUES -----
    float2 d = _WaterFlowMap_TexelSize.xy * 2.5; 

    // ON REMET "uv" STRICTEMENT ICI. Décaler les UV cassait l'alignement physique avec les collisions !
    float h_C = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv).z;
    float h_L = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x, 0)).z;
    float h_R = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x, 0)).z;
    float h_D = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(0, -d.y)).z;
    float h_U = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(0,  d.y)).z;

    float h_DL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x, -d.y)).z;
    float h_DR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x, -d.y)).z;
    float h_UL = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2(-d.x,  d.y)).z;
    float h_UR = SAMPLE_TEXTURE2D(_WaterFlowMap, sampler_WaterFlowMap, uv + float2( d.x,  d.y)).z;

    float blurred_height = (h_C * 4.0 + (h_L + h_R + h_D + h_U) * 2.0 + (h_DL + h_DR + h_UL + h_UR) * 1.0) / 16.0;

    // Hauteur extraite de ta simulation de ripple 
    float simAlpha = blurred_height - 0.5;

    // CALCUL DU RELIEF (BUMP) SIMPLIFIÉ
    // Au lieu d'une lumière 3D qui pète tes couleurs, on utilise juste les gradients de ta simulation
    float fakeBump = (h_L - h_R + h_D - h_U) * _BumpStrength;


    // ----- 2. GENERATION DE MOTIFS ORGANIQUES -----
    // Utilisons TA méthode exact de correction de ratio (uv * WaterPlaneSize) :
    float2 env_uv = uv * _WaterPlaneSize.xy; 

    float global_speed = _Time.y * _Speed * 0.2; // Vitesse ralentie

    float2 st = env_uv * (_Scale * 0.1); 
    
    st.y -= global_speed; // Courant
    
    float2 i_st = floor(st);
    float2 f_st = frac(st);

    float m_dist = 1.0;

    // Voronoi
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            float2 neighbor = float2(float(x), float(y));
            float2 pt = random2_water(i_st + neighbor);
            // Oscillation interne des pois ralentie aussi
            pt = 0.5 + 0.5 * sin(_Time.y * (_Speed * 0.5) + 6.2831 * pt);
            
            float2 diff = neighbor + pt - f_st;
            float dist = length(diff);
            m_dist = min(m_dist, dist);
        }
    }

    // Le tracé des pois d'eau
    float spots = smoothstep(0.45, 0.75, 1.0 - m_dist);

    // Création d'un masque de "Noise" pour pas avoir des pois partout
    // On utilise 'st * 0.5' pour que le masque bouge à la même vitesse et direction que les pois
    float noise_mask = noise_water(st * 0.5);
    noise_mask = smoothstep(0.4, 0.6, noise_mask); // Contraste le masque
    spots *= noise_mask; // Appliquer le masque


    // ----- 3. COLORATION ET BLENDING FINAL -----
    // L'eau de base
    float baseAlpha = clamp(_AlphaMin + simAlpha, _AlphaMin, _AlphaMax); // Borne alpha avec sliders
    
    // Mélange couleur (eau de base VS pois opaque)
    half3 finalColor = lerp(_BaseColor.rgb, _SpotColor.rgb, spots);
    
    // Ajout du Bump directement connecté à la courbure de ta simulation (pour que ce soit clean) !
    finalColor += finalColor * fakeBump * 5.0;

    // Alpha Final: On prend l'alpha de base MAIS on ajoute les pois qui vont jusqu'à 1 !
    float finalAlpha = max(baseAlpha, spots);

    return half4(finalColor, finalAlpha);
}
#endif
