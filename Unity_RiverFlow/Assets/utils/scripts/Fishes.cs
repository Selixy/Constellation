using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Système de mouvement et d'animation pour poisson 2D basé sur chaînes de bones souples.
/// Inspiré par EZ Soft Bones mais adapté pour le 2D avec une logique de mouvement forward + turns.
/// </summary>
public class Fishes : MonoBehaviour
{
    [Header("=== MOUVEMENT ===")]
    [SerializeField] private float moveSpeed = 3f;
    [SerializeField] private float turnInterval = 4f;
    [SerializeField] private float turnDuration = 0.8f;
    [SerializeField] private float turnAngle = 90f;
    
    [Header("=== LIMITES (X et Z pour vue du dessus) ===")]
    [SerializeField] private Vector3 boundsMin = new Vector3(-10f, -10f, -10f);
    [SerializeField] private Vector3 boundsMax = new Vector3(10f, 10f, 10f);
    
    [Header("=== RÉFÉRENCES ===")]
    [SerializeField] private Transform rootBone;
    
    // État du poisson
    private Vector3 currentForwardDirection = Vector3.right;
    private Vector3 targetForwardDirection = Vector3.right;
    private float turnTimer = 0f;
    private bool isTurning = false;
    private float turnProgress = 0f;
    private float currentYawAngle = 0f;
    private float targetYawAngle = 0f;
    
    // Rotations de base de tous les bones
    private Dictionary<Transform, Quaternion> boneBaseRotations = new Dictionary<Transform, Quaternion>();
    
    // Animation
    private float animationTime = 0f;

    void Start()
    {
        // Position initiale aléatoire
        SetFishPosition(GetRandomPositionInBounds());
        
        // Sauvegarder les rotations de base de tous les bones enfants du root
        Transform root = rootBone != null ? rootBone : transform;
        SaveBoneBaseRotations(root);
        
        // Récupérer la rotation Y actuelle du root et l'utiliser comme direction initiale
        float initialYaw = root.eulerAngles.y;
        currentYawAngle = initialYaw;
        targetYawAngle = initialYaw;
        
        // Convertir l'angle Y en direction forward du poisson
        currentForwardDirection = new Vector3(Mathf.Cos(initialYaw * Mathf.Deg2Rad), 0f, Mathf.Sin(initialYaw * Mathf.Deg2Rad)).normalized;
        targetForwardDirection = currentForwardDirection;
        
        // S'assurer que la rotation du root a les bons 90° sur X
        root.rotation = Quaternion.Euler(90f, initialYaw, 0f);
        
        // Reset les timers
        turnTimer = turnInterval;
        animationTime = Random.Range(0f, 100f);
    }

    void Update()
    {
        animationTime += Time.deltaTime;
        
        // Gérer les changements de direction
        UpdateTurning();
        
        // Déplacer le poisson forward
        UpdateMovement();
        
        // Appliquer les limites
        ClampToBounds();
        
        // Animer les chaînes de bones en fonction de la direction et du mouvement
        AnimateBoneChains();
    }

    /// <summary>
    /// Gère la logique de changement de direction (turning)
    /// </summary>
    private void UpdateTurning()
    {
        turnTimer -= Time.deltaTime;
        
        if (!isTurning && turnTimer <= 0f)
        {
            // Démarrer un nouveau turn
            StartNewTurn();
        }
        
        if (isTurning)
        {
            turnProgress += Time.deltaTime / turnDuration;
            
            if (turnProgress >= 1f)
            {
                // Turn terminé
                turnProgress = 1f;
                isTurning = false;
                currentForwardDirection = targetForwardDirection;
                turnTimer = turnInterval + Random.Range(-0.5f, 1f);
            }
            else
            {
                // Interpoler pendant le turn
                currentForwardDirection = Vector3.Lerp(currentForwardDirection, targetForwardDirection, turnProgress).normalized;
            }
        }
        
        // Orienter le poisson dans sa direction forward
        RotateFishTowardDirection();
    }

    /// <summary>
    /// Démarre un nouveau turn aléatoire
    /// </summary>
    private void StartNewTurn()
    {
        isTurning = true;
        turnProgress = 0f;
        
        // Générer une nouvelle direction (rotation autour de Y pour vue de dessus)
        float randomAngle = Random.Range(-turnAngle, turnAngle);
        targetForwardDirection = Quaternion.Euler(0, randomAngle, 0) * currentForwardDirection;
        targetForwardDirection = targetForwardDirection.normalized;
    }

    /// <summary>
    /// Oriente le root du poisson selon la direction forward
    /// </summary>
    private void RotateFishTowardDirection()
    {
        if (currentForwardDirection.magnitude < 0.01f)
            return;
        
        // Calculer l'angle Y cible sur le plan X-Z
        targetYawAngle = Mathf.Atan2(currentForwardDirection.z, currentForwardDirection.x) * Mathf.Rad2Deg;
        
        // Interpoler lisse vers l'angle cible
        float rotationSpeed = 5f;
        currentYawAngle = Mathf.LerpAngle(currentYawAngle, targetYawAngle, rotationSpeed * Time.deltaTime);
        
        // Appliquer la rotation: 90X (pour vue dessus) + rotation Y (direction)
        Quaternion finalRotation = Quaternion.Euler(90f, currentYawAngle, 0f);
        
        if (rootBone != null)
        {
            rootBone.rotation = finalRotation;
        }
        else
        {
            transform.rotation = finalRotation;
        }
    }

    /// <summary>
    /// Met à jour la position du poisson (avance toujours forward sur le plan X-Z)
    /// </summary>
    private void UpdateMovement()
    {
        // Utiliser X et Z pour le déplacement (vue de dessus)
        // Inverser la direction si le poisson avance à l'envers
        Vector3 movement = new Vector3(-currentForwardDirection.x, 0f, -currentForwardDirection.z) * moveSpeed * Time.deltaTime;
        Vector3 newPos = GetFishPosition() + movement;
        SetFishPosition(newPos);
    }

    /// <summary>
    /// Restreint la position du poisson aux limites et force un turn si on touche une bordure
    /// </summary>
    private void ClampToBounds()
    {
        Vector3 pos = GetFishPosition();
        bool hitBound = false;
        
        // Vérifier si on touche une bordure
        if (pos.x <= boundsMin.x || pos.x >= boundsMax.x)
            hitBound = true;
        if (pos.y <= boundsMin.y || pos.y >= boundsMax.y)
            hitBound = true;
        if (pos.z <= boundsMin.z || pos.z >= boundsMax.z)
            hitBound = true;
        
        // Clamper la position
        pos.x = Mathf.Clamp(pos.x, boundsMin.x, boundsMax.x);
        pos.y = Mathf.Clamp(pos.y, boundsMin.y, boundsMax.y);
        pos.z = Mathf.Clamp(pos.z, boundsMin.z, boundsMax.z);
        SetFishPosition(pos);
        
        // Si on a touché une bordure, forcer un nouveau turn
        if (hitBound && !isTurning)
        {
            StartNewTurn();
        }
    }

    /// <summary>
    /// Anime toutes les chaînes de bones de manière cohérente
    /// </summary>
    private void AnimateBoneChains()
    {
        Transform rootTransform = rootBone != null ? rootBone : transform;
        
        // Oscillation générale de tous les bones autour de leur rotation de base (sauf le root)
        foreach (var kvp in boneBaseRotations)
        {
            Transform bone = kvp.Key;
            Quaternion baseRotation = kvp.Value;
            
            // Ignorer le root - il ne doit être contrôlé que par la direction
            if (bone == rootTransform)
                continue;
            
            // Créer une oscillation simple basée sur le temps
            float frequency = 2f;
            float amplitude = 10f;
            float offset = bone.GetInstanceID() * 0.1f; // Offset unique par bone pour variation
            
            float oscillation = Mathf.Sin((animationTime + offset) * frequency) * amplitude;
            
            // Appliquer la rotation de base + oscillation
            bone.localRotation = baseRotation * Quaternion.Euler(0, 0, oscillation);
        }
    }

    /// <summary>
    /// Sauvegarde les rotations de base de tous les bones enfants
    /// </summary>
    private void SaveBoneBaseRotations(Transform root)
    {
        boneBaseRotations.Clear();
        Transform[] allBones = root.GetComponentsInChildren<Transform>();
        
        foreach (Transform bone in allBones)
        {
            boneBaseRotations[bone] = bone.localRotation;
        }
    }

    #region Helpers

    private Vector3 GetFishPosition()
    {
        return rootBone != null ? rootBone.position : transform.position;
    }

    private void SetFishPosition(Vector3 newPos)
    {
        if (rootBone != null)
            rootBone.position = newPos;
        else
            transform.position = newPos;
    }

    private Vector3 GetRandomPositionInBounds()
    {
        return new Vector3(
            Random.Range(boundsMin.x, boundsMax.x),
            Random.Range(boundsMin.y, boundsMax.y),
            Random.Range(boundsMin.z, boundsMax.z)
        );
    }

    private void OnDrawGizmos()
    {
        Vector3 center = (boundsMin + boundsMax) * 0.5f;
        Vector3 size = boundsMax - boundsMin;
        Vector3 extents = size * 0.5f;
        
        Gizmos.color = Color.green;
        
        Vector3[] corners = new Vector3[8]
        {
            center + new Vector3(-extents.x, -extents.y, -extents.z),
            center + new Vector3(extents.x, -extents.y, -extents.z),
            center + new Vector3(extents.x, extents.y, -extents.z),
            center + new Vector3(-extents.x, extents.y, -extents.z),
            center + new Vector3(-extents.x, -extents.y, extents.z),
            center + new Vector3(extents.x, -extents.y, extents.z),
            center + new Vector3(extents.x, extents.y, extents.z),
            center + new Vector3(-extents.x, extents.y, extents.z)
        };
        
        Gizmos.DrawLine(corners[0], corners[1]);
        Gizmos.DrawLine(corners[1], corners[2]);
        Gizmos.DrawLine(corners[2], corners[3]);
        Gizmos.DrawLine(corners[3], corners[0]);
        
        Gizmos.DrawLine(corners[4], corners[5]);
        Gizmos.DrawLine(corners[5], corners[6]);
        Gizmos.DrawLine(corners[6], corners[7]);
        Gizmos.DrawLine(corners[7], corners[4]);
        
        Gizmos.DrawLine(corners[0], corners[4]);
        Gizmos.DrawLine(corners[1], corners[5]);
        Gizmos.DrawLine(corners[2], corners[6]);
        Gizmos.DrawLine(corners[3], corners[7]);
    }

    #endregion
}
