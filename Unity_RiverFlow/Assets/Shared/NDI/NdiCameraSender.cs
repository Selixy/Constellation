using UnityEngine;
/// <summary>
/// Capture cette caméra et envoie le flux via RiverFlowNetwork.
/// Nécessite un GameObject "Network" portant RiverFlowNetwork dans la scène.
/// </summary>
[RequireComponent(typeof(Camera))]
public class NdiCameraSender : MonoBehaviour
{
    [Tooltip("Identifiant du flux — doit correspondre au champ 'id' dans riverflow-client-ndi.yaml.")]
    public string streamId = "camera_1";

    [Tooltip("Résolution de capture.")]
    public int captureWidth = 960;
    public int captureHeight = 540;

    [Tooltip("Qualité JPEG (1-100).")]
    [Range(1, 100)]
    public int jpegQuality = 75;

    [Tooltip("FPS cible du flux.")]
    [Range(1, 60)]
    public int targetFps = 30;

    private RenderTexture _rt;
    private Texture2D _tex;
    private float _nextSendTime;

    void Start()
    {
        _nextSendTime = Time.time;

        _rt = new RenderTexture(captureWidth, captureHeight, 24, RenderTextureFormat.ARGB32);
        _rt.Create();
        _tex = new Texture2D(captureWidth, captureHeight, TextureFormat.RGB24, false);

        GetComponent<Camera>().targetTexture = _rt;

        if (RiverFlowNetwork.Instance == null)
            Debug.LogWarning($"[NdiCameraSender:{streamId}] RiverFlowNetwork introuvable dans la scène.");
    }

    void LateUpdate()
    {
        if (RiverFlowNetwork.Instance == null) return;
        if (Time.time < _nextSendTime) return;
        _nextSendTime += 1f / Mathf.Max(1, targetFps);

        var prev = RenderTexture.active;
        RenderTexture.active = _rt;
        _tex.ReadPixels(new Rect(0, 0, captureWidth, captureHeight), 0, 0, false);
        _tex.Apply(false);
        RenderTexture.active = prev;

        FlipY(_tex);

        byte[] jpeg = ImageConversion.EncodeToJPG(_tex, jpegQuality);
        RiverFlowNetwork.Instance.SendFrame(streamId, jpeg);
    }

    private static void FlipY(Texture2D tex)
    {
        Color[] px = tex.GetPixels();
        int w = tex.width, h = tex.height;
        for (int y = 0; y < h / 2; y++)
        {
            int a = y * w, b = (h - 1 - y) * w;
            for (int x = 0; x < w; x++)
                (px[a + x], px[b + x]) = (px[b + x], px[a + x]);
        }
        tex.SetPixels(px);
        tex.Apply(false);
    }

    void OnDestroy()
    {
        if (_rt != null) { _rt.Release(); Destroy(_rt); }
        if (_tex != null) Destroy(_tex);
    }
}
