using UnityEngine;
using Klak.Ndi;

/// <summary>
/// A attacher sur un GameObject portant une Camera.
/// Envoie le flux de la camera en NDI.
/// Si aucune RenderTexture n'est assignee sur la camera, en cree une automatiquement
/// a la taille specifiee (par defaut : resolution de l'ecran).
/// </summary>
[RequireComponent(typeof(Camera))]
public class NdiCameraSender : MonoBehaviour
{
    [Header("NDI")]
    [Tooltip("Nom du flux NDI — doit correspondre exactement au champ 'id' dans le YAML du ClientNDI (ex: camera_1).")]
    public string streamName = "camera_1";

    [Header("Render Texture")]
    [Tooltip("Laisser a zero pour utiliser la resolution de l'ecran au demarrage.")]
    public int width  = 0;
    public int height = 0;

    Camera          _camera;
    RenderTexture   _rt;
    NdiSender       _sender;
    bool            _ownRt;

    void Awake()
    {
        _camera = GetComponent<Camera>();

        // Creer la RenderTexture si la camera n'en a pas
        if (_camera.targetTexture == null)
        {
            int w = width  > 0 ? width  : Screen.width;
            int h = height > 0 ? height : Screen.height;
            _rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
            _rt.name = $"{gameObject.name}_NDI_RT";
            _rt.Create();
            _camera.targetTexture = _rt;
            _ownRt = true;
        }
        else
        {
            _rt = _camera.targetTexture;
        }

        // Ajouter le NdiSender sur ce GameObject
        _sender = gameObject.AddComponent<NdiSender>();
        _sender.ndiName = string.IsNullOrEmpty(streamName) ? gameObject.name : streamName;
        _sender.sourceTexture = _rt;
        _sender.captureMethod = CaptureMethod.Texture;
    }

    void OnDestroy()
    {
        if (_ownRt && _rt != null)
        {
            _camera.targetTexture = null;
            _rt.Release();
            Destroy(_rt);
        }
    }
}
