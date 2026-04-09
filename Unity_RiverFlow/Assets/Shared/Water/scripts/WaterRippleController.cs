using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Simule l'équation d'onde 2D (Wave Equation) via ping-pong RenderTexture.
/// Texture : R=prev_height, G=unused, B=curr_height
///
/// Chaque frame :
///   1. Propagation Verlet × simStepsPerFrame (sub-stepping pour atteindre les bords)
///   2. Stamp des interacteurs
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
    [SerializeField] private int   resolution       = 512;
    [Tooltip("Nombre de pas de physique par frame — augmente la vitesse de propagation")]
    [Range(1, 32)]
    [SerializeField] private int   simStepsPerFrame = 8;
    [Tooltip("Amortissement global par frame (0.999 = longue durée, 0.97 = courte)")]
    [Range(0.9f, 0.999f)]
    [SerializeField] private float damping          = 0.985f;
    [Tooltip("Rayon du stamp en proportion du plan [0,1]")]
    [SerializeField] private float stampRadius      = 0.05f;
    [Tooltip("Hauteur injectée")]
    [SerializeField] private float stampStrength    = 4.0f;
    [Tooltip("Vitesse d'expansion de l'anneau (UV/s * planeSize)")]
    [SerializeField] private float ringExpandSpeed  = 0.2f;
    [Tooltip("Taux de décroissance temporelle des impacts (1/s)")]
    [SerializeField] private float impactDecay      = 1.0f;

    // ── Singleton ────────────────────────────────────────────────────────────
    public static WaterRippleController Instance { get; private set; }

    // ── État interne ─────────────────────────────────────────────────────────
    private ComputeBuffer     _buffer;
    private WaterInteractor[] _data;
    private int               _currentCount;

    private RenderTexture _rtCurr, _rtNext, _rtSwap;
    private Material      _simMat;
    private Renderer      _renderer;

    private readonly List<ImpactEntry>            _impacts     = new();
    private readonly Dictionary<int, ImpactEntry> _persistents = new();

    // ── Property IDs ─────────────────────────────────────────────────────────
    private static readonly int ID_Damping         = Shader.PropertyToID("_Damping");
    private static readonly int ID_SimDeltaTime    = Shader.PropertyToID("_SimDeltaTime");
    private static readonly int ID_PlaneMin        = Shader.PropertyToID("_WaterPlaneMin");
    private static readonly int ID_PlaneSize       = Shader.PropertyToID("_WaterPlaneSize");
    private static readonly int ID_StampRadius     = Shader.PropertyToID("_StampRadius");
    private static readonly int ID_StampStrength   = Shader.PropertyToID("_StampStrength");
    private static readonly int ID_RingExpandSpeed = Shader.PropertyToID("_RingExpandSpeed");
    private static readonly int ID_ImpactDecay     = Shader.PropertyToID("_ImpactDecay");
    private static readonly int ID_FlowMap         = Shader.PropertyToID("_WaterFlowMap");

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
            Debug.LogError("[WaterRippleController] Shader 'Hidden/WaterSim' introuvable.");
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

    public void SetPersistent(int id, Vector2 worldPositionXZ)
    {
        _persistents[id] = new ImpactEntry
        {
            position  = worldPositionXZ,
            startTime = Time.realtimeSinceStartup,
            isImpact  = 0
        };
    }

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

        Bounds b = _renderer != null
            ? _renderer.bounds
            : new Bounds(transform.position, transform.lossyScale);

#if UNITY_EDITOR
        if (Quaternion.Angle(transform.rotation, Quaternion.identity) > 1f)
            Debug.LogWarning("[WaterRippleController] Le plan est pivoté.", this);
#endif

        Vector4 planeMin  = new Vector4(b.min.x, b.min.z, 0, 0);
        Vector4 planeSize = new Vector4(b.size.x, b.size.z, 0, 0);

        float dt = Application.isPlaying ? Time.deltaTime : 0.016f;

        _simMat.SetVector(ID_PlaneMin,  planeMin);
        _simMat.SetVector(ID_PlaneSize, planeSize);

        // ── Pass 0 : Propagation Verlet (sub-stepping) ───────────────────────
        // La vague avance de 0.5 texel/step. Avec simStepsPerFrame=8 et res=512 :
        // 0.5 * 8 * 60fps / 512 ≈ 0.47 UV/s → traverse le plan en ~2s.
        // Le damping est la racine N-ième pour garder le damping total constant.
        float dampPerStep = Mathf.Pow(damping, 1f / Mathf.Max(1, simStepsPerFrame));
        _simMat.SetFloat(ID_Damping,      dampPerStep);
        _simMat.SetFloat(ID_SimDeltaTime, dt);

        for (int step = 0; step < simStepsPerFrame; step++)
        {
            Graphics.Blit(_rtCurr, _rtNext, _simMat, 0);
            (_rtCurr, _rtNext) = (_rtNext, _rtCurr);
        }

        // ── Pass 1 : Stamp des interacteurs ─────────────────────────────────
        _simMat.SetBuffer("_Interactors",     _buffer);
        _simMat.SetInt   ("_InteractorCount", _currentCount);
        _simMat.SetFloat (ID_StampRadius,     stampRadius);
        _simMat.SetFloat (ID_StampStrength,   stampStrength);
        _simMat.SetFloat (ID_SimDeltaTime,    dt);
        _simMat.SetFloat (ID_RingExpandSpeed, ringExpandSpeed);
        _simMat.SetFloat (ID_ImpactDecay,     impactDecay);
        Graphics.Blit(_rtCurr, _rtSwap, _simMat, 1);

        // Rotation : swap devient le nouvel état courant
        (_rtCurr, _rtSwap) = (_rtSwap, _rtCurr);

        // ── Expose ──────────────────────────────────────────────────────────
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
        var rt = new RenderTexture(resolution, resolution, 0, RenderTextureFormat.ARGBFloat)
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
