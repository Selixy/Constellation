using UnityEngine;
using Klak.Ndi;

/// <summary>
/// A attacher sur un GameObject portant une Camera ET un NdiSender.
/// Configure le NdiSender en mode Camera — KlakNDI gere la RenderTexture automatiquement.
/// Le champ streamName doit correspondre exactement au champ 'id' du YAML ClientNDI.
/// </summary>
[RequireComponent(typeof(Camera))]
[RequireComponent(typeof(NdiSender))]
public class NdiCameraSender : MonoBehaviour
{
    [Tooltip("Doit correspondre au champ 'id' dans le YAML du ClientNDI (ex: camera_1).")]
    public string streamName = "camera_1";

    void Awake()
    {
        var sender = GetComponent<NdiSender>();
        sender.ndiName       = streamName;
        sender.captureMethod = CaptureMethod.Camera;
        sender.sourceCamera  = GetComponent<Camera>();
    }
}
