# 🌊 AUDIT COMPLET — Système Water (Assets/Shared/Water)

**Date audit** : 9 avril 2026  
**Composants audités** : Shaders + Scripts C#

---

## 📋 ARCHITECTURE GÉNÉRALE

### Concept
Système de simulation d'eau 2D basé sur un **flow field GPU** (champ vectoriel de vélocité).
- **Simulation** : Ping-pong RenderTextures avec 3 passes (Advection → Stamp → Diffusion)
- **Rendu** : Shader simple qui sample la flow map et génère couleur + écume
- **Interacteurs** : CPU → GPU buffer (pieds, impacts)

### Paradigme
```
World Space (pieds réels)
       ↓
GPU StructuredBuffer (WaterInteractor)
       ↓
Shader Pass 1 (Stamp) — injection de vélocité radiale
       ↓
RenderTexture flow map (_WaterFlowMap)
       ↓
S_Water.shader — rendu final avec noise + écume
```

---

## 🎨 SHADERS

### 1️⃣ **S_Water.shader** — Shader de rendu principal
**Fichier** : `S_Water.shader`  
**Type** : Rendu transparent  
**Blend mode** : SrcAlpha OneMinusSrcAlpha ✅

#### Points forts
- Tags corrects : `Transparent`, `Queue=Transparent`, `RenderPipeline=UniversalPipeline`
- `ZWrite Off` + `Cull Off` appropriés pour un overlay
- Include du module surface correctement référencé

#### ⚠️ Problème potentiel
- Pas d'include de `W_Input.hlsl` → OK (la struct n'est pas nécessaire côté rendu)
- Le path include suppose une structure strict : `Modules/W_Surface.hlsl`  
  → Vérifier que le chemin est correct depuis le dossier du shader

#### Code
```hlsl
Varyings vert(Attributes IN)
{
    OUT.positionHCS = TransformObjectToHClip(IN.positionOS.xyz);
    OUT.uv = IN.uv;  // ✅ UV mesh [0,1] — pas de conversion world space
    return OUT;
}
```
✅ Bon : pas de multiplication de scale, juste l'UV du mesh.

---

### 2️⃣ **S_WaterSim.shader** — Simulation GPU (3 passes)
**Fichier** : `Shaders/S_WaterSim.shader`  
**Type** : Hidden shader (compute-like)

#### Pass 0 — Advection semi-Lagrangienne + Dissipation
```glsl
float2 srcUV = saturate(i.uv - vel * _SimDeltaTime);
float2 newVel = SAMPLE_TEXTURE2D(..., srcUV).rg * _Dissipation;
```
✅ **Bon** :
- `saturate()` évite les dépassements UV
- Dissipation appliquée correctement (0.992 par défaut = 99.2% retention par frame)
- Boundary condition avec smoothstep sur les bords

⚠️ **Attention** : `srcUV` peut causer des artefacts si la vélocité dépasse ~1 UV/frame  
→ Vérifier `stampStrength` (actuellement 8.0)

#### Pass 1 — Stamp (injection vélocité radiale)
```glsl
for (int n = 0; n < _InteractorCount; n++)
{
    WaterInteractor a = _Interactors[n];
    
    if (a.isImpact == 1) {
        // Impact : anneau radial expansif
        float ring_r = a.age * _RingExpandSpeed;
        float ringFall = exp(-pow(dist - ring_r, 2) / (ringWidth²));
        vel += dir_vel * ringFall * timeFade * _StampStrength;
    } else {
        // Persistant (pied posé) : Gaussienne stable
        float falloff = exp(-dist²/ (sr²));
        vel += dir_vel * falloff * _StampStrength * 0.15;
    }
}
```
✅ **Bon** :
- Deux modes distincts (impact vs persistant)
- Decay temporel cohérent : `exp(-a.age * _ImpactDecay)`
- Falloff exponentielle → pas de discontinuité

⚠️ **Peut-être un problème** :
- `_InteractorCount` → dépend de CPU chaque frame. **Possible race condition** si buffer update slow?
- `vel = clamp(vel, -2.0, 2.0)` → Hard-coded. Pourrait être parameter.

#### Pass 2 — Diffusion Laplacienne (viscosité)
```glsl
float2 laplacian = left + right + up + down - 4.0 * center;
float2 result = center + _Viscosity * laplacian;

// Boundary absorbante après diffusion
float2 bnd = smoothstep(0.0, 0.03, uv) * smoothstep(1.0, 0.97, uv);
return result * bnd;
```
✅ **Excellent** :
- Stencil pattern correct (5-point Laplacian)
- `_Viscosity < 0.25` constraint bien documenté
- Boundary réappliquée → stabilité numérique

---

### 3️⃣ **W_Surface.hlsl** — Surface computation
**Fichier** : `Modules/W_Surface.hlsl`  

#### Noise procédural
```glsl
float _hash(float2 p)
{
    p = frac(p * float2(0.1031, 0.1030));
    p += dot(p, p.yx + 33.33);
    return frac((p.x + p.y) * p.x);
}

float _valueNoise(float2 p)
{
    // Interpolation Hermite correcte ✅
    float2 u = f * f * (3.0 - 2.0 * f);
    return lerp(...) [4 lerps];
}
```
✅ **OK** : Hash n'est *pas* cryptographiquement fort, mais suffisant pour du noise visuel.

#### Calcul de la surface
```glsl
float speed = length(vel);

float calmVis = noise * 0.07;           // Grain léger au repos
float disturb = saturate(speed * 5.0);  // Perturbation proportionnelle
float foamBase = saturate((speed - 0.12) * 6.0);
float foam = foamBase * (0.55 + noise * 0.45);

// Blending couleur
half3 color = lerp(calmCol, moveCol, disturb);
color = lerp(color, foamCol, foam);

half alpha = saturate(calmVis + disturb * 0.55 + foam * 0.90);
```
✅ **Bon** :
- Foam threshold à 0.12 UV/frame → réaliste
- Alpha composition = calmVis + disturb + foam (pas d'overblend)

---

### 4️⃣ **W_Input.hlsl** — Struct GPU partagée
```glsl
struct WaterInteractor {
    float2 position;  // 8 bytes
    float  age;       // 4 bytes
    int    isImpact;  // 4 bytes
};
```
✅ **Parfait** : stride = 16 bytes, aligné. Miroir exact du C#.

---

### 5️⃣ **W_FlowMap.hlsl** — ⚠️ DEPRECATED
```glsl
// DEPRECATED — Ce fichier n'est plus utilisé.
// L'ancienne approche (ComputeFlow / ComputeHeight via sin + falloff CPU)
// a été remplacée par la simulation ping-pong GPU dans S_WaterSim.shader.
```
**Action** : À supprimer (nettoyage du code).

---

## 🖥️ SCRIPTS C#

### 1️⃣ **WaterRippleController.cs** — Cœur du système
**Type** : MonoBehaviour `[ExecuteAlways]`  
**Lifecycle** : OnEnable → Update → OnDisable

#### Points forts ✅
- **Singleton pattern** : `public static WaterRippleController Instance`
- **Properly cleanup** : ComputeBuffer.Release(), RenderTexture.Release()
- **OpenGL compatibility** : `_simMat.SetBuffer()` au lieu de `Shader.SetGlobalBuffer()` (requis OpenGL 4.5)
- **ExeuteAlways** → fonctionne en edit mode
- **Gestion temporal** : `Time.realtimeSinceStartup` pour stabilité en edit mode

#### Gestion des interacteurs
```csharp
public void AddImpact(Vector2 worldPositionXZ)
{
    if (_impacts.Count + _persistents.Count >= maxInteractors) return;
    _impacts.Add(new ImpactEntry { ... expireAt = now + impactLifetime, isImpact = 1 });
}

public void SetPersistent(int id, Vector2 worldPositionXZ)
{
    _persistents[id] = new ImpactEntry { ..., isImpact = 0 };
}

public void RemovePersistent(int id)
{
    if (!_persistents.TryGetValue(id, out var e)) return;
    _persistents.Remove(id);
    AddImpact(e.position);  // ← Convertit en impact bref
}
```
✅ **Bon** : Trois états bien définis.

#### Simulation ping-pong
```csharp
private void StepSimulation()
{
    // Pass 0 - Advection
    var advected = RenderTexture.GetTemporary(...);
    Graphics.Blit(_rtCurr, advected, _simMat, 0);
    
    // Pass 1 - Stamp
    _simMat.SetBuffer("_Interactors", _buffer);
    _simMat.SetInt("_InteractorCount", _currentCount);
    Graphics.Blit(advected, _rtNext, _simMat, 1);
    
    RenderTexture.ReleaseTemporary(advected);
    
    // Swap
    (_rtSwap, _rtCurr, _rtNext) = (_rtCurr, _rtNext, _rtSwap);
    
    // Expose globally
    Shader.SetGlobalTexture(ID_FlowMap, _rtCurr);
}
```
✅ **Excellent** :
- Temporary texture properly released
- Swap optimisé (tuple-style, pas de 3ème variable)
- Global texture exposure → S_Water.shader peut l'accéder

#### ⚠️ Problèmes potentiels

1. **Monde rotation non-supporter**
```csharp
#if UNITY_EDITOR
if (Quaternion.Angle(transform.rotation, Quaternion.identity) > 1f)
    Debug.LogWarning("[...] Le plan est pivoté — le mapping world→UV suppose un plan aligné sur les axes.", this);
#endif
```
→ Warning uniquement en editor. À runtime, peut causer des artefacts si rotationné.

2. **Pass 2 (Diffusion) absente du StepSimulation()**
```csharp
// Le shader S_WaterSim.shader DÉFINIT une Pass 2, mais...
// Graphics.Blit(..., _simMat, 2) n'existe PAS en code!
```
❌ **C'EST UN BUG** : La diffusion Laplacienne n'est jamais exécutée!  
→ Voir si c'est intentionnel ou oublié.

3. **RenderTexture.active** manipulation potentiellement risquée
```csharp
private RenderTexture CreateRT()
{
    var rt = new RenderTexture(resolution, resolution, 0, RenderTextureFormat.RGFloat) { ... };
    rt.Create();
    var prev = RenderTexture.active;
    RenderTexture.active = rt;
    GL.Clear(true, true, Color.black);  // ← Peut fail si previous était null?
    RenderTexture.active = prev;
    return rt;
}
```
⚠️ Pas vraiment un bug, mais fragile. `prev` pourrait être null.

4. **Buffer stride mismatch?**
```csharp
private struct WaterInteractor
{
    public Vector2 position;  // 8 bytes
    public float   age;       // 4 bytes
    public int     isImpact;  // 4 bytes
}
// = 16 bytes ✅
```
Déclaration du buffer `new ComputeBuffer(maxInteractors, 16)` ✅ OK.

5. **`_currentCount` mutable entre BuildGPUBuffer() et StepSimulation()**
```csharp
private void Update()
{
    PurgeExpiredImpacts();  // ← Modifie _impacts.Count
    BuildGPUBuffer();       // ← Calcule _currentCount
    StepSimulation();       // ← Utilise _currentCount
}
```
✅ Order correct (aucune race condition).

6. **Paramètre `Pass 2` non-utilisé**
Chercher si vraiment intentionnel ou oublié. Peut bloquer les interactions complexes.

---

### 2️⃣ **WaterRipple_Emitter.cs** — Générateur de pas simple
**Type** : MonoBehaviour `[ExecuteAlways]`

#### Concept
Deux pieds marchent linéairement selon l'axe Z.  
- **Left foot** : `x = -stepWidth`, alterne posé/levé
- **Right foot** : `x = +stepWidth`, alterne posé/levé

#### Code
```csharp
_stepTimer -= delta;
if (_stepTimer <= 0f) {
    int fi = _nextFoot;
    _feet[fi].z += stepLength * 2f;  // ← Double length (pas suivant)
    if (_feet[fi].z > halfRange)
        _feet[fi].z = -halfRange + (_feet[fi].z - halfRange);  // ← Wrap
    
    Vector2 pos = new Vector2(_feet[fi].x, _feet[fi].z);
    WaterRippleController.Instance.SetPersistent(_feet[fi].id, pos);
    ...
}
```
✅ **Bon** : Logique simple, wrap propre.

#### ⚠️ Problème potentiel
```csharp
_stepTimer = stepLength / walkSpeed;
```
→ Période fixe. Pas d'accélération/décélération réaliste. OK pour un test simple.

---

### 3️⃣ **WaterRippleTest.cs** — Générateur de pas debug
**Identique à WaterRipple_Emitter + Scene loader check.**

```csharp
if (IsNetworkSceneLoaded()) return;  // ← Se désactive si scène réseau chargée
```
✅ **Bon** : Permet de switcher debug ↔ mocap réel.

#### Implémentation `IsNetworkSceneLoaded()`
```csharp
private bool IsNetworkSceneLoaded()
{
    for (int i = 0; i < SceneManager.sceneCount; i++) {
        Scene s = SceneManager.GetSceneAt(i);
        if (s.name == networkSceneName && s.isLoaded) return true;
    }
    return false;
}
```
✅ Robuste.

---

## 🔴 RÉSUMÉ DES PROBLÈMES IDENTIFIÉS

| Sévérité | Problème | Fichier | Impact |
|----------|----------|---------|--------|
| 🔴 **CRITIQUE** | Pass 2 (Diffusion) manquante en exécution | WaterRippleController.cs | **Les fronts d'eau ne diffusent pas** → pas d'interactions complexes |
| 🟡 **MAJEUR** | Material "M_Warer.mat" → typo possible | N/A (fichier binaire) | Interface confuse |
| 🟡 **MAJEUR** | Rotation du monde non-supportée | WaterRippleController.cs + Stamp Pass | Artefacts si mesh pivoté |
| 🟠 **MODÉRÉ** | `GL.Clear()` avec `RenderTexture.active=null` possible | CreateRT() | Crash potentiel rare |
| 🟠 **MODÉRÉ** | W_FlowMap.hlsl deprecated non supprimé | Modules/W_FlowMap.hlsl | Confusion/maintenance |
| 🟡 **INFORMATION** | Clamping vel à [-2, 2] hard-coded | S_WaterSim Pass 1 | Pourrait être paramètre |

---

## ✅ POINTS FORTS

1. **Architecture modulaire** : Shaders séparés, HLSL modules réutilisables
2. **GPU-optimisé** : Simulation complète sur GPU, CPU émet événements uniquement
3. **Gestion mémoire** : Cleanup robuste, pas de leaks
4. **OpenGL compatible** : Usage correct de SetBuffer au lieu de SetGlobalBuffer
5. **Temporal stability** : `Time.realtimeSinceStartup` pour predictability
6. **Edit mode support** : `[ExecuteAlways]` permet testing en editor

---

## 🎯 CHECKLIST DE VÉRIFICATION

- [ ] **Pass 2 réellement absent ?** Ou Pass 1 includes la diffusion?
- [ ] Material "M_Warer.mat" — est-ce une typo ou intentionnel?
- [ ] Prefab "2D-O_Water.prefab" — vérifie la configuration (size, position, shader assigns)
- [ ] Test en runtime : impacts se propagent-ils correctement?
- [ ] Perf : quelle résolution 256² est utilisée? Scalable?
- [ ] Mode réseauu mocap : WaterRippleTest.cs se désactive-t-il bien?

---

**Audité par** : Audit Tool  
**Status** : ⚠️ En attente de feedback (BUG Pass 2 à confirmer)
