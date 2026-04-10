using System;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>
/// Gestionnaire réseau central pour le streaming UDP vers le client RiverFlow.
/// Placer sur un unique GameObject "Network" dans la scène.
/// Les caméras s'y réfèrent via RiverFlowNetwork.Instance.SendFrame(...).
/// </summary>
public class RiverFlowNetwork : MonoBehaviour
{
    public static RiverFlowNetwork Instance { get; private set; }

    [Tooltip("IP de la machine qui fait tourner le client RiverFlow.")]
    public string targetIp = "127.0.0.1";

    [Tooltip("Port UDP unique pour tous les flux.")]
    public int targetPort = 7000;

    // Taille max du payload JPEG par fragment (sous la limite UDP de 65507)
    private const int MaxPayload = 60000;

    private UdpClient _udp;
    // Compteur de frame par stream id
    private System.Collections.Generic.Dictionary<string, uint> _frameIds
        = new System.Collections.Generic.Dictionary<string, uint>();

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Debug.LogWarning("[RiverFlowNetwork] Instance déjà présente — destruction du doublon.");
            Destroy(gameObject);
            return;
        }
        Instance = this;

        _udp = new UdpClient();
        _udp.Connect(targetIp, targetPort);
        Debug.Log($"[RiverFlowNetwork] UDP connecté vers {targetIp}:{targetPort}");
    }

    /// <summary>
    /// Envoie une frame JPEG pour le stream identifié par <paramref name="streamId"/>.
    /// Appelé par chaque NdiCameraSender dans son LateUpdate.
    /// </summary>
    public void SendFrame(string streamId, byte[] jpeg)
    {
        if (_udp == null) return;

        if (!_frameIds.TryGetValue(streamId, out uint frameId))
            frameId = 0;
        _frameIds[streamId] = frameId + 1;

        // Header : [id_len:1][id:N][frame_id:4][frag_idx:2][frag_count:2]
        byte[] idBytes = Encoding.UTF8.GetBytes(streamId);
        if (idBytes.Length > 255)
        {
            Debug.LogWarning($"[RiverFlowNetwork] streamId trop long (>255 bytes) : {streamId}");
            return;
        }
        byte idLen = (byte)idBytes.Length;
        int headerBase = 1 + idLen + 4 + 2 + 2; // sans les 2 octets frag_idx qui varient

        int fragCount = (jpeg.Length + MaxPayload - 1) / MaxPayload;
        for (int i = 0; i < fragCount; i++)
        {
            int offset = i * MaxPayload;
            int payloadLen = Math.Min(MaxPayload, jpeg.Length - offset);
            byte[] pkt = new byte[headerBase + payloadLen];

            int pos = 0;
            pkt[pos++] = idLen;
            Buffer.BlockCopy(idBytes, 0, pkt, pos, idLen);
            pos += idLen;
            Buffer.BlockCopy(BitConverter.GetBytes(frameId),     0, pkt, pos, 4); pos += 4;
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)i),   0, pkt, pos, 2); pos += 2;
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)fragCount), 0, pkt, pos, 2); pos += 2;
            Buffer.BlockCopy(jpeg, offset, pkt, pos, payloadLen);

            try { _udp.Send(pkt, pkt.Length); }
            catch (Exception e)
            {
                Debug.LogWarning($"[RiverFlowNetwork] Send error (stream={streamId}, frag={i}): {e.Message}");
            }
        }
    }

    void OnDestroy()
    {
        _udp?.Close();
        _udp = null;
        if (Instance == this) Instance = null;
    }
}
