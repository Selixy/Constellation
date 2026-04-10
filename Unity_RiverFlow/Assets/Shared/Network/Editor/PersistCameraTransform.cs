using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Persiste les transforms des caméras modifiées en Play mode.
/// À la sortie du Play mode, les positions/rotations sont recopiées dans la scène éditeur.
/// Supporte l'Undo (Ctrl+Z).
/// </summary>
[InitializeOnLoad]
public static class PersistCameraTransform
{
    // Clé : chemin hiérarchique du GameObject (ex: "Scene/CameraRig/camera_1")
    private static Dictionary<string, (Vector3 pos, Quaternion rot)> _snapshot;

    static PersistCameraTransform()
    {
        EditorApplication.playModeStateChanged += OnStateChanged;
    }

    private static void OnStateChanged(PlayModeStateChange state)
    {
        if (state == PlayModeStateChange.ExitingPlayMode)
        {
            _snapshot = new Dictionary<string, (Vector3, Quaternion)>();
            foreach (var cam in Object.FindObjectsByType<Camera>(FindObjectsSortMode.None))
            {
                string path = GetPath(cam.transform);
                _snapshot[path] = (cam.transform.position, cam.transform.rotation);
            }
        }
        else if (state == PlayModeStateChange.EnteredEditMode)
        {
            if (_snapshot == null || _snapshot.Count == 0) return;

            foreach (var cam in Object.FindObjectsByType<Camera>(FindObjectsSortMode.None))
            {
                string path = GetPath(cam.transform);
                if (!_snapshot.TryGetValue(path, out var saved)) continue;

                // On n'applique que si la caméra a bougé pendant le Play mode
                if (cam.transform.position == saved.pos && cam.transform.rotation == saved.rot)
                    continue;

                Undo.RecordObject(cam.transform, $"Persist camera transform: {cam.name}");
                cam.transform.SetPositionAndRotation(saved.pos, saved.rot);
            }

            _snapshot = null;
        }
    }

    private static string GetPath(Transform t)
    {
        return t.parent == null ? t.name : GetPath(t.parent) + "/" + t.name;
    }
}
