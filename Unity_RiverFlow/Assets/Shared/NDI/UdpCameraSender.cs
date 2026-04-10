using System;
using System.Net.Sockets;
using UnityEngine;

/// <summary>
/// Captures this camera's output and streams it as JPEG-over-UDP to a RiverFlow client.
/// Add to any Camera GameObject. Set targetIp + targetPort to match riverflow-client-ndi.yaml.
/// </summary>
[RequireComponent(typeof(Camera))]
public class UdpCameraSender : MonoBehaviour
{
    [Tooltip("Identifies this stream (must match 'id' in the client YAML, e.g. camera_1).")]
    public string streamId = "camera_1";

    [Tooltip("IP address of the machine running the RiverFlow client.")]
    public string targetIp = "127.0.0.1";

    [Tooltip("UDP port for this stream (must match 'port' in the client YAML).")]
    public int targetPort = 7001;

    [Tooltip("Capture resolution width.")]
    public int captureWidth = 960;

    [Tooltip("Capture resolution height.")]
    public int captureHeight = 540;

    [Tooltip("JPEG quality (1-100). Lower = smaller packets, more compression artifacts.")]
    [Range(1, 100)]
    public int jpegQuality = 75;

    [Tooltip("Target frame rate for the stream.")]
    [Range(1, 60)]
    public int targetFps = 30;

    // Max UDP payload per packet (stays well below the 65507-byte UDP limit)
    private const int MaxPayloadBytes = 60000;

    private UdpClient _udp;
    private RenderTexture _rt;
    private Texture2D _tex;
    private uint _frameId;
    private float _sendInterval;
    private float _nextSendTime;

    void Start()
    {
        _sendInterval = 1f / Mathf.Max(1, targetFps);
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
        if (Time.time < _nextSendTime)
            return;
        _nextSendTime += _sendInterval;

        // Read camera render texture into CPU texture
        var prev = RenderTexture.active;
        RenderTexture.active = _rt;
        _tex.ReadPixels(new Rect(0, 0, captureWidth, captureHeight), 0, 0, false);
        _tex.Apply(false);
        RenderTexture.active = prev;

        // Unity render textures are flipped vertically — fix before encoding
        FlipTextureVertically(_tex);

        // Encode to JPEG
        byte[] jpeg = ImageConversion.EncodeToJPG(_tex, jpegQuality);

        // Fragment and send
        int fragCount = (jpeg.Length + MaxPayloadBytes - 1) / MaxPayloadBytes;
        for (int i = 0; i < fragCount; i++)
        {
            int offset = i * MaxPayloadBytes;
            int payloadLen = Math.Min(MaxPayloadBytes, jpeg.Length - offset);

            // Header: frame_id(4) + frag_idx(2) + frag_count(2) = 8 bytes, little-endian
            byte[] packet = new byte[8 + payloadLen];
            Buffer.BlockCopy(BitConverter.GetBytes(_frameId), 0, packet, 0, 4);
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)i), 0, packet, 4, 2);
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)fragCount), 0, packet, 6, 2);
            Buffer.BlockCopy(jpeg, offset, packet, 8, payloadLen);

            try { _udp.Send(packet, packet.Length); }
            catch (Exception e) { Debug.LogWarning($"[UdpCameraSender] Send error: {e.Message}"); }
        }

        _frameId++;
    }

    private void FlipTextureVertically(Texture2D tex)
    {
        Color[] pixels = tex.GetPixels();
        int w = tex.width;
        int h = tex.height;
        for (int y = 0; y < h / 2; y++)
        {
            int top = y * w;
            int bottom = (h - 1 - y) * w;
            for (int x = 0; x < w; x++)
            {
                Color tmp = pixels[top + x];
                pixels[top + x] = pixels[bottom + x];
                pixels[bottom + x] = tmp;
            }
        }
        tex.SetPixels(pixels);
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
