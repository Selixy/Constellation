using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Simule deux pieds qui marchent en ligne droite le long de l'axe Z.
/// Représente une captation mocap réelle : pied posé (persistant) → pied levé (impact).
/// Utilisé pour tester WaterRippleController sans réseau.
/// </summary>
[ExecuteAlways]
public class WaterRipple_Emitter : MonoBehaviour
{
    [Header("Marche")]
    [Tooltip("Vitesse d'avance (unités/s)")]
    [SerializeField] private float walkSpeed  = 0.6f;
    [Tooltip("Écart latéral entre pied gauche et pied droit (axe X)")]
    [SerializeField] private float stepWidth  = 0.15f;
    [Tooltip("Distance entre deux pas consécutifs (axe Z)")]
    [SerializeField] private float stepLength = 0.4f;
    [Tooltip("Durée du pied posé au sol (secondes)")]
    [SerializeField] private float stanceTime = 0.4f;
    [Tooltip("Demi-longueur du chemin (unités world). Rembobine quand dépassé.")]
    [SerializeField] private float halfRange  = 10f;

    private struct Foot
    {
        public int   id;
        public float x;         // position X fixe
        public float z;         // position Z courante
        public bool  isDown;
        public float downUntil; // Time.realtimeSinceStartup auquel lever le pied
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
        _nextFoot    = 0;
        _stepTimer   = 0f;
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
        if (WaterRippleController.Instance == null) return;

        float now   = Time.realtimeSinceStartup;
        float delta = now - _lastRealTime;
        _lastRealTime = now;

        // Lever les pieds dont le temps de stance est écoulé
        for (int i = 0; i < _feet.Length; i++)
        {
            if (_feet[i].isDown && now >= _feet[i].downUntil)
            {
                _feet[i].isDown = false;
                WaterRippleController.Instance.RemovePersistent(_feet[i].id);
            }
        }

        // Poser le prochain pied selon la cadence
        _stepTimer -= delta;
        if (_stepTimer <= 0f)
        {
            int fi = _nextFoot;

            // Chaque pied avance d'un pas double (car ils alternent)
            _feet[fi].z += stepLength * 2f;
            if (_feet[fi].z > halfRange)
                _feet[fi].z = -halfRange + (_feet[fi].z - halfRange);

            Vector2 pos = new Vector2(_feet[fi].x, _feet[fi].z);
            WaterRippleController.Instance.SetPersistent(_feet[fi].id, pos);
            _feet[fi].isDown   = true;
            _feet[fi].downUntil = now + stanceTime;

            _nextFoot  = 1 - _nextFoot;
            _stepTimer = stepLength / walkSpeed;
        }
    }
}
