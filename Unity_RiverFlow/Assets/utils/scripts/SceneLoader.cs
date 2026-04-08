using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Scene Loader - Charge les scènes additives par phases de priorité.
/// À placer sur un GameObject dans la scène 0_Boot.
/// </summary>
public class SceneLoader : MonoBehaviour
{
    [System.Serializable]
    public class SceneLoadInfo
    {
        public string sceneName;
        public int priority;

        public SceneLoadInfo(string name, int prio)
        {
            sceneName = name;
            priority = prio;
        }
    }

    [SerializeField] 
    private List<SceneLoadInfo> scenes = new List<SceneLoadInfo>()
    {
        new SceneLoadInfo("4_Network", 0),      // Priorité 0 - Chargée en premier
        new SceneLoadInfo("1_Lighting", 1),    // Priorité 1
        new SceneLoadInfo("2_Enviro_3D", 2),   // Priorité 2
        new SceneLoadInfo("3_Enviro_2D", 2)    // Priorité 2
    };

    private void Start()
    {
        StartCoroutine(LoadScenesByPhases());
    }

    /// <summary>
    /// Charge les scènes par phases selon leur priorité.
    /// Attend que chaque phase soit complètement chargée avant de passer à la suivante.
    /// </summary>
    private IEnumerator LoadScenesByPhases()
    {
        // Trouver la priorité maximale
        int maxPriority = 0;
        foreach (var scene in scenes)
        {
            if (scene.priority > maxPriority)
                maxPriority = scene.priority;
        }

        // Charger par priorité
        for (int currentPriority = 0; currentPriority <= maxPriority; currentPriority++)
        {
            List<AsyncOperation> phaseOperations = new List<AsyncOperation>();

            // Lancer tous les chargements pour cette priorité
            foreach (var scene in scenes)
            {
                if (scene.priority == currentPriority)
                {
                    if (!IsSceneLoaded(scene.sceneName))
                    {
                        AsyncOperation asyncOp = SceneManager.LoadSceneAsync(scene.sceneName, LoadSceneMode.Additive);
                        phaseOperations.Add(asyncOp);
                        Debug.Log($"[Phase {currentPriority}] Chargement en cours: {scene.sceneName}");
                    }
                }
            }

            // Attendre que tous les chargements de cette phase soient terminés
            foreach (var asyncOp in phaseOperations)
            {
                while (!asyncOp.isDone)
                {
                    yield return null;
                }
            }

            // Log de fin de phase
            if (phaseOperations.Count > 0)
            {
                Debug.Log($"✓ Phase {currentPriority} complètement chargée!");
            }
        }

        Debug.Log("✓ Toutes les scènes sont chargées!");
        OnAllScenesLoaded();
    }

    /// <summary>
    /// Appelée quand toutes les scènes sont chargées.
    /// À overrider ou utiliser comme point d'accroche.
    /// </summary>
    private void OnAllScenesLoaded()
    {
        // Vous pouvez ajouter ici du code d'initialisation post-chargement
        Debug.Log("Prêt à jouer!");
    }

    /// <summary>
    /// Vérifie si une scène est déjà chargée.
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

    /// <summary>
    /// Décharge une scène chargée en additif.
    /// </summary>
    public void UnloadScene(string sceneName)
    {
        if (IsSceneLoaded(sceneName))
        {
            SceneManager.UnloadSceneAsync(sceneName);
            Debug.Log($"Scène '{sceneName}' déchargée.");
        }
        else
        {
            Debug.LogWarning($"La scène '{sceneName}' n'est pas chargée.");
        }
    }
}
