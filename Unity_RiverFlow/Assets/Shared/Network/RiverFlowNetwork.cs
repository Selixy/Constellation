using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>
/// Gestionnaire réseau central pour le streaming UDP vers le(s) client(s) RiverFlow.
/// Placer sur un unique GameObject "Network" dans la scène.
/// Les caméras s'y réfèrent via RiverFlowNetwork.Instance.SendFrame(...).
///
/// Supporte plusieurs destinations simultanées (fan-out) :
/// remplir la liste <see cref="targets"/> dans l'Inspector.
/// </summary>
public class RiverFlowNetwork : MonoBehaviour
{
    public static RiverFlowNetwork Instance { get; private set; }

    [Serializable]
    public struct UdpTarget
    {
        [Tooltip("IP de destination.")]
        public string ip;
        [Tooltip("Port UDP de destination.")]
        public int port;
    }

    [Tooltip("Liste des destinations UDP (fan-out). Ajouter autant d'entrées que nécessaire.")]
    public List<UdpTarget> targets = new()
    {
        new() { ip = "127.0.0.1",  port = 7000 },
        new() { ip = "10.42.0.1",  port = 7000 },
    };

    // Taille max du payload JPEG par fragment (sous la limite UDP de 65507)
    private const int MaxPayload = 60000;

    private UdpClient _udp;
    private IPEndPoint[] _endpoints;

    // Compteur de frame par stream id
    private Dictionary<string, uint> _frameIds = new Dictionary<string, uint>();

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Debug.LogWarning("[RiverFlowNetwork] Instance déjà présente — destruction du doublon.");
            Destroy(gameObject);
            return;
        }
        Instance = this;

        // UdpClient non connecté pour pouvoir envoyer vers plusieurs endpoints.
        _udp = new UdpClient();

        _endpoints = new IPEndPoint[targets.Count];
        for (int i = 0; i < targets.Count; i++)
        {
            _endpoints[i] = new IPEndPoint(IPAddress.Parse(targets[i].ip), targets[i].port);
            Debug.Log($"[RiverFlowNetwork] Target [{i}] → {targets[i].ip}:{targets[i].port}");
        }
    }

    /// <summary>
    /// Envoie une frame JPEG pour le stream identifié par <paramref name="streamId"/>
    /// vers toutes les destinations configurées.
    /// </summary>
    public void SendFrame(string streamId, byte[] jpeg)
    {
        if (_udp == null || _endpoints == null || _endpoints.Length == 0) return;

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
        int headerBase = 1 + idLen + 4 + 2 + 2;

        int fragCount = (jpeg.Length + MaxPayload - 1) / MaxPayload;
        for (int i = 0; i < fragCount; i++)
        {
            int offset = i * MaxPayload;
            int payloadLen = Math.Min(MaxPayload, jpeg.Length - offset);
            byte[] pkt = new byte[headerBase + payloadLen];

            int pos = 0;
            pkt[pos++] = idLen;
            Buffer.BlockCopy(idBytes, 0, pkt, pos, idLen);           pos += idLen;
            Buffer.BlockCopy(BitConverter.GetBytes(frameId),     0, pkt, pos, 4); pos += 4;
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)i),   0, pkt, pos, 2); pos += 2;
            Buffer.BlockCopy(BitConverter.GetBytes((ushort)fragCount), 0, pkt, pos, 2); pos += 2;
            Buffer.BlockCopy(jpeg, offset, pkt, pos, payloadLen);

            foreach (var ep in _endpoints)
            {
                try { _udp.Send(pkt, pkt.Length, ep); }
                catch (Exception e)
                {
                    Debug.LogWarning($"[RiverFlowNetwork] Send error (stream={streamId}, frag={i}, dst={ep}): {e.Message}");
                }
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
