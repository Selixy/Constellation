using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Debug Boot Loader - Vérifie si la scène 0_Boot est chargée au démarrage.
/// Si elle n'est pas chargée, la charge.
/// Utile pour tester des scènes individuelles en développement.
/// </summary>
public class Debug_BootLoader : MonoBehaviour
{
    private const string BOOT_SCENE_NAME = "0_Boot";

    private void Start()
    {
        CheckAndLoadBootScene();
    }

    /// <summary>
    /// Vérifie si la scène Boot est chargée, sinon la charge.
    /// </summary>
    private void CheckAndLoadBootScene()
    {
        if (IsSceneLoaded(BOOT_SCENE_NAME))
        {
            return;
        }

        SceneManager.LoadScene(BOOT_SCENE_NAME, LoadSceneMode.Single);
    }

    /// <summary>
    /// Vérifie si une scène est chargée.
    /// </summary>
    private bool IsSceneLoaded(string sceneName)
    {
        for (int i = 0; i < SceneManager.sceneCount; i++)
        {
            if (SceneManager.GetSceneAt(i).name == sceneName)
            {
                return true;
            }
        }
        return false;
    }
}
