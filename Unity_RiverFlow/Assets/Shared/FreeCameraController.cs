using UnityEngine;

/// <summary>
/// Contrôleur de caméra calqué sur la vue Scène Unity.
/// À attacher sur un GameObject Camera.
///
/// Contrôles :
///   Clic droit maintenu  →  regarder autour (mouse look)
///     + W/A/S/D          →  avancer / reculer / gauche / droite
///     + Q/E              →  descendre / monter
///     + Shift            →  vitesse ×3
///   Molette              →  avancer / reculer
///   Clic milieu maintenu →  pan (glisser horizontalement/verticalement)
///   Alt + clic gauche    →  orbiter autour d'un pivot
/// </summary>
public class FreeCameraController : MonoBehaviour
{
    [Header("Fly")]
    public float moveSpeed = 10f;
    public float fastMultiplier = 3f;
    public float mouseSensitivity = 2f;

    [Header("Scroll")]
    public float scrollSpeed = 20f;

    [Header("Pan")]
    public float panSpeed = 0.5f;

    [Header("Orbit")]
    public float orbitSpeed = 200f;

    private float _yaw;
    private float _pitch;

    // Pivot pour l'orbite (Alt + clic gauche)
    private Vector3 _orbitPivot;
    private float _orbitDistance;
    private bool _orbiting;

    void OnEnable()
    {
        _yaw   = transform.eulerAngles.y;
        _pitch = transform.eulerAngles.x;
    }

    void Update()
    {
        // ── Orbite : Alt + clic gauche ────────────────────────────────────
        if (Input.GetKey(KeyCode.LeftAlt) || Input.GetKey(KeyCode.RightAlt))
        {
            if (Input.GetMouseButtonDown(0))
            {
                _orbitPivot    = transform.position + transform.forward * 10f;
                _orbitDistance = Vector3.Distance(transform.position, _orbitPivot);
                _orbiting      = true;
            }
            if (Input.GetMouseButtonUp(0)) _orbiting = false;

            if (_orbiting && Input.GetMouseButton(0))
            {
                float dx = Input.GetAxis("Mouse X") * orbitSpeed * Time.deltaTime;
                float dy = Input.GetAxis("Mouse Y") * orbitSpeed * Time.deltaTime;
                _yaw   += dx;
                _pitch -= dy;
                _pitch  = Mathf.Clamp(_pitch, -89f, 89f);

                Quaternion rot = Quaternion.Euler(_pitch, _yaw, 0f);
                transform.position = _orbitPivot - rot * Vector3.forward * _orbitDistance;
                transform.rotation = rot;
                return;
            }
        }
        else
        {
            _orbiting = false;
        }

        // ── Pan : clic milieu ─────────────────────────────────────────────
        if (Input.GetMouseButton(2))
        {
            float dx = -Input.GetAxis("Mouse X") * panSpeed;
            float dy = -Input.GetAxis("Mouse Y") * panSpeed;
            transform.Translate(dx, dy, 0f, Space.Self);
            return;
        }

        // ── Molette : zoom rapide ─────────────────────────────────────────
        float scroll = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(scroll) > 0.001f)
        {
            float speed = scrollSpeed * (Input.GetKey(KeyCode.LeftShift) ? fastMultiplier : 1f);
            transform.Translate(0f, 0f, scroll * speed, Space.Self);
        }

        // ── Fly : clic droit ──────────────────────────────────────────────
        if (Input.GetMouseButton(1))
        {
            // Mouse look
            _yaw   += Input.GetAxis("Mouse X") * mouseSensitivity;
            _pitch -= Input.GetAxis("Mouse Y") * mouseSensitivity;
            _pitch  = Mathf.Clamp(_pitch, -89f, 89f);
            transform.rotation = Quaternion.Euler(_pitch, _yaw, 0f);

            // Déplacement WASD + QE
            float speed = moveSpeed * Time.deltaTime
                          * (Input.GetKey(KeyCode.LeftShift) ? fastMultiplier : 1f);

            Vector3 move = Vector3.zero;
            if (Input.GetKey(KeyCode.W)) move += transform.forward;
            if (Input.GetKey(KeyCode.S)) move -= transform.forward;
            if (Input.GetKey(KeyCode.D)) move += transform.right;
            if (Input.GetKey(KeyCode.A)) move -= transform.right;
            if (Input.GetKey(KeyCode.E)) move += Vector3.up;
            if (Input.GetKey(KeyCode.Q)) move -= Vector3.up;

            transform.position += move * speed;
        }
        else
        {
            // Resync yaw/pitch si la rotation a été changée de l'extérieur
            _yaw   = transform.eulerAngles.y;
            _pitch = transform.eulerAngles.x;
            if (_pitch > 180f) _pitch -= 360f;
        }
    }
}
