using UnityEngine;
using UnityEngine.SceneManagement;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Version debug de WaterRipple_Emitter.
/// Se coupe automatiquement quand la scène réseau (mocap réel) est chargée.
/// </summary>
[ExecuteAlways]
public class WaterRippleTest : MonoBehaviour
{
    [Header("Scène réseau")]
    [Tooltip("Le test s'arrête quand cette scène est chargée (mocap réel actif)")]
    [SerializeField] private string networkSceneName = "4_Network";

    [Header("Marche")]
    [Tooltip("Vitesse d'avance (unités/s)")]
    [SerializeField] private float walkSpeed  = 0.6f;
    [Tooltip("Écart latéral entre pied gauche et pied droit (axe X)")]
    [SerializeField] private float stepWidth  = 0.15f;
    [Tooltip("Distance entre deux pas consécutifs (axe Z)")]
    [SerializeField] private float stepLength = 0.4f;
    [Tooltip("Durée du pied posé au sol (secondes)")]
    [SerializeField] private float stanceTime = 0.4f;
    [Tooltip("Demi-longueur du chemin (unités world)")]
    [SerializeField] private float halfRange  = 10f;

    private struct Foot
    {
        public int   id;
        public float x;
        public float z;
        public bool  isDown;
        public float downUntil;
    }

    private Foot[] _feet;
    private float  _stepTimer;
    private int    _nextFoot;
    private float  _lastRealTime;

    private void OnEnable()
    {
        _feet = new Foot[]
        {
            new Foot { id = 0, x = -stepWidth, z = -halfRange,              isDown = false },
            new Foot { id = 1, x =  stepWidth, z = -halfRange + stepLength, isDown = false },
        };
        _nextFoot     = 0;
        _stepTimer    = 0f;
        _lastRealTime = Time.realtimeSinceStartup;
    }

    private void Update()
    {
#if UNITY_EDITOR
        if (!Application.isPlaying)
        {
            EditorApplication.QueuePlayerLoopUpdate();
            SceneView.RepaintAll();
        }
#endif
        if (IsNetworkSceneLoaded()) return;
        if (WaterRippleController.Instance == null) return;

        float now   = Time.realtimeSinceStartup;
        float delta = now - _lastRealTime;
        _lastRealTime = now;

        for (int i = 0; i < _feet.Length; i++)
        {
            if (_feet[i].isDown && now >= _feet[i].downUntil)
            {
                _feet[i].isDown = false;
                WaterRippleController.Instance.RemovePersistent(_feet[i].id);
            }
        }

        _stepTimer -= delta;
        if (_stepTimer <= 0f)
        {
            int fi = _nextFoot;

            _feet[fi].z += stepLength * 2f;
            if (_feet[fi].z > halfRange)
                _feet[fi].z = -halfRange + (_feet[fi].z - halfRange);

            Vector2 pos = new Vector2(_feet[fi].x, _feet[fi].z);
            WaterRippleController.Instance.SetPersistent(_feet[fi].id, pos);
            _feet[fi].isDown    = true;
            _feet[fi].downUntil = now + stanceTime;

            _nextFoot  = 1 - _nextFoot;
            _stepTimer = stepLength / walkSpeed;
        }
    }

    private bool IsNetworkSceneLoaded()
    {
        for (int i = 0; i < SceneManager.sceneCount; i++)
        {
            Scene s = SceneManager.GetSceneAt(i);
            if (s.name == networkSceneName && s.isLoaded) return true;
        }
        return false;
    }
}
