using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Simule un champ de vélocité 2D (flow field) via ping-pong RenderTexture.
///
/// Chaque frame :
///   1. Advection semi-Lagrangienne + dissipation  (Pass 0)
///   2. Stamp des interacteurs (injection de vélocité radiale)  (Pass 1)
///   3. Diffusion Laplacienne (viscosité) — crée des interactions entre fronts (Pass 2)
///
/// Expose _WaterFlowMap globalement pour S_Water.shader.
///
/// NOTE OpenGL : le StructuredBuffer _Interactors est bindé via _simMat.SetBuffer()
/// (pas via Shader.SetGlobalBuffer qui n'est pas fiable sur OpenGL 4.5).
/// </summary>
[ExecuteAlways]
public class WaterRippleController : MonoBehaviour
{
    // ── Struct GPU — stride 16 bytes, miroir exact de W_Input.hlsl ───────────
    private struct WaterInteractor
    {
        public Vector2 position; // 8 bytes
        public float   age;      // 4 bytes
        public int     isImpact; // 4 bytes
    }

    // ── Suivi côté CPU ───────────────────────────────────────────────────────
    private struct ImpactEntry
    {
        public Vector2 position;
        public float   startTime;
        public float   expireAt;
        public int     isImpact;
    }

    // ── Paramètres ───────────────────────────────────────────────────────────
    [Header("Interacteurs")]
    [Tooltip("Durée de vie d'un impact (secondes)")]
    [SerializeField] private float impactLifetime  = 3f;
    [Tooltip("Nombre maximum d'interacteurs simultanés")]
    [SerializeField] private int   maxInteractors  = 32;

    [Header("Simulation")]
    [Tooltip("Résolution de la texture de simulation")]
    [SerializeField] private int   resolution      = 256;
    [Tooltip("Rétention de vélocité par frame (0=instantané, 1=jamais dissipé)")]
    [SerializeField] private float dissipation     = 0.992f;
    [Tooltip("Rayon Gaussien du stamp en espace UV [0,1]")]
    [SerializeField] private float stampRadius     = 0.15f;
    [Tooltip("Amplitude de la vélocité injectée")]
    [SerializeField] private float stampStrength   = 8.0f;
    [Tooltip("Vitesse d'expansion de l'anneau d'impact (UV/s)")]
    [SerializeField] private float ringExpandSpeed = 0.3f;
    [Tooltip("Taux de décroissance temporelle des impacts (1/s)")]
    [SerializeField] private float impactDecay     = 1.0f;
    [Tooltip("Diffusion Laplacienne — étale la vélocité, crée des interactions entre fronts (0=off, max=0.24)")]
    [SerializeField] private float viscosity       = 0.15f;

    // ── Singleton ────────────────────────────────────────────────────────────
    public static WaterRippleController Instance { get; private set; }

    // ── État interne ─────────────────────────────────────────────────────────
    private ComputeBuffer     _buffer;
    private WaterInteractor[] _data;
    private int               _currentCount; // nombre d'interacteurs actifs

    private RenderTexture _rtCurr, _rtNext, _rtSwap;
    private Material      _simMat;
    private Renderer      _renderer;

    private readonly List<ImpactEntry>            _impacts     = new();
    private readonly Dictionary<int, ImpactEntry> _persistents = new();

    // ── Property IDs ─────────────────────────────────────────────────────────
    private static readonly int ID_Dissipation    = Shader.PropertyToID("_Dissipation");
    private static readonly int ID_SimDeltaTime   = Shader.PropertyToID("_SimDeltaTime");
    private static readonly int ID_PlaneMin       = Shader.PropertyToID("_WaterPlaneMin");
    private static readonly int ID_PlaneSize      = Shader.PropertyToID("_WaterPlaneSize");
    private static readonly int ID_StampRadius    = Shader.PropertyToID("_StampRadius");
    private static readonly int ID_StampStrength  = Shader.PropertyToID("_StampStrength");
    private static readonly int ID_RingExpandSpeed = Shader.PropertyToID("_RingExpandSpeed");
    private static readonly int ID_ImpactDecay    = Shader.PropertyToID("_ImpactDecay");
    private static readonly int ID_Viscosity      = Shader.PropertyToID("_Viscosity");
    private static readonly int ID_FlowMap        = Shader.PropertyToID("_WaterFlowMap");

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    private void OnEnable()
    {
        if (Instance != null && Instance != this) return;
        Instance = this;

        _renderer = GetComponent<Renderer>();
        _data     = new WaterInteractor[maxInteractors];
        _buffer   = new ComputeBuffer(maxInteractors, 16);

        CreateRenderTextures();

        var simShader = Shader.Find("Hidden/WaterSim");
        if (simShader == null)
        {
            Debug.LogError("[WaterRippleController] Shader 'Hidden/WaterSim' introuvable. " +
                           "Vérifier que S_WaterSim.shader est dans le projet et compilé.");
            return;
        }
        _simMat = new Material(simShader);
    }

    private void OnDisable()
    {
        _buffer?.Release();
        _buffer = null;
        ReleaseRenderTextures();
        if (_simMat != null)
        {
            if (Application.isPlaying) Object.Destroy(_simMat);
            else Object.DestroyImmediate(_simMat);
            _simMat = null;
        }
        if (Instance == this) Instance = null;
    }

    private void Update()
    {
        if (_buffer == null || _simMat == null) return;
        PurgeExpiredImpacts();
        BuildGPUBuffer();
        StepSimulation();
    }

    // ── API publique ──────────────────────────────────────────────────────────

    /// <summary>Impact bref : pied levé. Génère un anneau expansif.</summary>
    public void AddImpact(Vector2 worldPositionXZ)
    {
        if (_impacts.Count + _persistents.Count >= maxInteractors) return;
        float now = Time.realtimeSinceStartup;
        _impacts.Add(new ImpactEntry
        {
            position  = worldPositionXZ,
            startTime = now,
            expireAt  = now + impactLifetime,
            isImpact  = 1
        });
    }

    /// <summary>Pied posé (persistant) : pousse doucement en continu.</summary>
    public void SetPersistent(int id, Vector2 worldPositionXZ)
    {
        _persistents[id] = new ImpactEntry
        {
            position  = worldPositionXZ,
            startTime = Time.realtimeSinceStartup,
            isImpact  = 0
        };
    }

    /// <summary>Pied levé : convertit le persistant en impact bref.</summary>
    public void RemovePersistent(int id)
    {
        if (!_persistents.TryGetValue(id, out ImpactEntry e)) return;
        _persistents.Remove(id);
        AddImpact(e.position);
    }

    // ── Gestion des interacteurs ──────────────────────────────────────────────
    private void PurgeExpiredImpacts()
    {
        float now = Time.realtimeSinceStartup;
        for (int i = _impacts.Count - 1; i >= 0; i--)
            if (_impacts[i].expireAt <= now)
                _impacts.RemoveAt(i);
    }

    private void BuildGPUBuffer()
    {
        float now   = Time.realtimeSinceStartup;
        int   count = 0;

        foreach (var e in _impacts)
        {
            if (count >= maxInteractors) break;
            _data[count++] = new WaterInteractor
                { position = e.position, age = now - e.startTime, isImpact = e.isImpact };
        }
        foreach (var kv in _persistents)
        {
            if (count >= maxInteractors) break;
            _data[count++] = new WaterInteractor
                { position = kv.Value.position, age = now - kv.Value.startTime, isImpact = kv.Value.isImpact };
        }
        for (int i = count; i < maxInteractors; i++) _data[i] = default;

        _currentCount = count;
        _buffer.SetData(_data);
    }

    // ── Simulation ping-pong ──────────────────────────────────────────────────
    private void StepSimulation()
    {
        if (_rtCurr == null || !_rtCurr.IsCreated() ||
            _rtNext == null || !_rtNext.IsCreated())
        {
            ReleaseRenderTextures();
            CreateRenderTextures();
            return;
        }

        // Bounds du renderer → mapping world XZ ↔ UV
        Bounds b = _renderer != null
            ? _renderer.bounds
            : new Bounds(transform.position, transform.lossyScale);

#if UNITY_EDITOR
        if (Quaternion.Angle(transform.rotation, Quaternion.identity) > 1f)
            Debug.LogWarning("[WaterRippleController] Le plan est pivoté — le mapping world→UV suppose un plan aligné sur les axes.", this);
#endif

        Vector4 planeMin  = new Vector4(b.min.x,  b.min.z,  0, 0);
        Vector4 planeSize = new Vector4(b.size.x,  b.size.z, 0, 0);

        float dt = Application.isPlaying ? Time.deltaTime : 0.016f;

        // ── Pass 0 : Advection + Dissipation ────────────────────────────────
        var advected = RenderTexture.GetTemporary(resolution, resolution, 0, RenderTextureFormat.RGFloat);
        advected.filterMode = FilterMode.Bilinear;

        _simMat.SetFloat(ID_Dissipation,  dissipation);
        _simMat.SetFloat(ID_SimDeltaTime, dt);
        Graphics.Blit(_rtCurr, advected, _simMat, 0);

        // ── Pass 1 : Stamp des interacteurs ─────────────────────────────────
        // SetBuffer sur le MATERIAL (pas SetGlobal) — obligatoire sur OpenGL 4.5
        _simMat.SetBuffer("_Interactors",     _buffer);
        _simMat.SetInt   ("_InteractorCount", _currentCount);
        _simMat.SetVector(ID_PlaneMin,        planeMin);
        _simMat.SetVector(ID_PlaneSize,       planeSize);
        _simMat.SetFloat (ID_StampRadius,     stampRadius);
        _simMat.SetFloat (ID_StampStrength,   stampStrength);
        _simMat.SetFloat (ID_SimDeltaTime,    dt);
        _simMat.SetFloat (ID_RingExpandSpeed, ringExpandSpeed);
        _simMat.SetFloat (ID_ImpactDecay,     impactDecay);
        Graphics.Blit(advected, _rtNext, _simMat, 1);

        RenderTexture.ReleaseTemporary(advected);

        // ── Rotation curr ↔ next ─────────────────────────────────────────────
        (_rtSwap, _rtCurr, _rtNext) = (_rtCurr, _rtNext, _rtSwap);

        // ── Expose la flow map au shader de rendu ────────────────────────────
        Shader.SetGlobalTexture(ID_FlowMap,  _rtCurr);
        Shader.SetGlobalVector (ID_PlaneMin,  planeMin);
        Shader.SetGlobalVector (ID_PlaneSize, planeSize);
    }

    // ── RenderTextures ────────────────────────────────────────────────────────
    private void CreateRenderTextures()
    {
        _rtCurr = CreateRT();
        _rtNext = CreateRT();
        _rtSwap = CreateRT();
    }

    private RenderTexture CreateRT()
    {
        var rt = new RenderTexture(resolution, resolution, 0, RenderTextureFormat.RGFloat)
        {
            filterMode = FilterMode.Bilinear,
            wrapMode   = TextureWrapMode.Clamp
        };
        rt.Create();
        var prev = RenderTexture.active;
        RenderTexture.active = rt;
        GL.Clear(true, true, Color.black);
        RenderTexture.active = prev;
        return rt;
    }

    private void ReleaseRenderTextures()
    {
        _rtCurr?.Release(); _rtCurr = null;
        _rtNext?.Release(); _rtNext = null;
        _rtSwap?.Release(); _rtSwap = null;
    }
}
