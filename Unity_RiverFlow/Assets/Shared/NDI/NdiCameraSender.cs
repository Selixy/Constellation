using System.Net.Sockets;
using UnityEngine;

/// <summary>
/// Capture la camera et envoie le flux en UDP+JPEG vers le client RiverFlow.
/// A attacher sur un GameObject portant une Camera.
/// targetIp + targetPort doivent correspondre au YAML du client (riverflow-client-ndi.yaml).
/// </summary>
[RequireComponent(typeof(Camera))]
public class NdiCameraSender : MonoBehaviour
{
    [Tooltip("IP de la machine qui fait tourner le client RiverFlow.")]
    public string targetIp = "127.0.0.1";

    [Tooltip("Port UDP — doit correspondre au champ 'port' dans le YAML (7001, 7002...).")]
    public int targetPort = 7001;

    [Tooltip("Résolution de capture.")]
    public int captureWidth = 960;
    public int captureHeight = 540;

    [Tooltip("Qualité JPEG (1-100).")]
    [Range(1, 100)]
    public int jpegQuality = 75;

    [Tooltip("FPS cible du flux.")]
    [Range(1, 60)]
    public int targetFps = 30;

    // Max bytes de payload par paquet UDP (sous la limite de 65507)
    private const int MaxPayload = 60000;

    private UdpClient _udp;
    private RenderTexture _rt;
    private Texture2D _tex;
    private uint _frameId;
    private float _nextSendTime;

    void Start()
    {
        _nextSendTime = Time.time;

        _udp = new UdpClient();
        _udp.Connect(targetIp, targetPort);

        _rt = new RenderTexture(captureWidth, captureHeight, 24, RenderTextureFormat.ARGB32);
        _rt.Create();

        _tex = new Texture2D(captureWidth, captureHeight, TextureFormat.RGB24, false);

        GetComponent<Camera>().targetTexture = _rt;
    }

    void LateUpdate()
    {
        if (Time.time < _nextSendTime) return;
        _nextSendTime += 1f / Mathf.Max(1, targetFps);

        // Lire la render texture dans le CPU
        var prev = RenderTexture.active;
        RenderTexture.active = _rt;
        _tex.ReadPixels(new Rect(0, 0, captureWidth, captureHeight), 0, 0, false);
        _tex.Apply(false);
        RenderTexture.active = prev;

        // Les RenderTextures Unity sont à l'envers — on flip avant d'encoder
        FlipY(_tex);

        byte[] jpeg = ImageConversion.EncodeToJPG(_tex, jpegQuality);

        // Fragmentation : header 8 octets little-endian
        //   [0..4] frame_id u32 | [4..6] frag_idx u16 | [6..8] frag_count u16
        int fragCount = (jpeg.Length + MaxPayload - 1) / MaxPayload;
        for (int i = 0; i < fragCount; i++)
        {
            int offset = i * MaxPayload;
            int len = Math.Min(MaxPayload, jpeg.Length - offset);
            byte[] pkt = new byte[8 + len];
            Buffer.BlockCopy(BitConverter.GetBytes(_frameId),  0, pkt, 0, 4);
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)i), 0, pkt, 4, 2);
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)fragCount), 0, pkt, 6, 2);
            Buffer.BlockCopy(jpeg, offset, pkt, 8, len);
            try { _udp.Send(pkt, pkt.Length); }
            catch (Exception e) { Debug.LogWarning($"[NdiCameraSender] UDP send: {e.Message}"); }
        }
        _frameId++;
    }

    private static void FlipY(Texture2D tex)
    {
        Color[] px = tex.GetPixels();
        int w = tex.width, h = tex.height;
        for (int y = 0; y < h / 2; y++)
        {
            int a = y * w, b = (h - 1 - y) * w;
            for (int x = 0; x < w; x++)
            {
                (px[a + x], px[b + x]) = (px[b + x], px[a + x]);
            }
        }
        tex.SetPixels(px);
        tex.Apply(false);
    }

    void OnDestroy()
    {
        _udp?.Close();
        _udp = null;
        if (_rt != null) { _rt.Release(); Destroy(_rt); }
        if (_tex != null) Destroy(_tex);
    }
}
