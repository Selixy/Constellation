using UnityEngine;
using System.Collections.Generic;

public class Fishes : MonoBehaviour
{
    [Header("Déplacement")]
    [SerializeField] private float moveSpeed = 2f;
    [SerializeField] private float directionChangeInterval = 3f;
    [SerializeField] private float speedVariation = 0.5f;
    [SerializeField] private float turnSpeed = 2f;
    
    [Header("Limites du Périmètre")]
    [SerializeField] private Vector3 boundsMin = new Vector3(-10f, -10f, -10f);
    [SerializeField] private Vector3 boundsMax = new Vector3(10f, 10f, 10f);
    
    [Header("Animation des Bones (Optionnel)")]
    [SerializeField] private bool enableBoneAnimation = true;
    [SerializeField] private float tailWaveAmplitude = 15f;
    [SerializeField] private float tailWaveFrequency = 2f;
    [SerializeField] private float finAnimationAmplitude = 10f;
    [SerializeField] private float finAnimationFrequency = 1.5f;
    [SerializeField] private float randomBoneNoiseScale = 0.3f;
    
    [Header("Références")]
    [SerializeField] private Transform rootBone;
    [Header("Références Optionnelles (pour animation des bones)")]
    [SerializeField] private Transform bodyBone;
    [SerializeField] private Transform headBone;
    [SerializeField] private List<Transform> finsBones = new List<Transform>();
    
    private Vector3 currentDirection;
    private Vector3 targetDirection;
    private float directionChangeTimer;
    private float currentSpeed;
    private float perlinNoiseOffset;
    
    private Dictionary<Transform, float> boneNoiseOffsets = new Dictionary<Transform, float>();
    private Dictionary<Transform, Quaternion> boneBaseRotations = new Dictionary<Transform, Quaternion>();

    void Start()
    {
        // Placer le poisson à une position aléatoire dans les bounds
        SetFishWorldPosition(GetRandomPositionInBounds());
        
        // Initialiser la direction
        currentDirection = Vector3.right;
        targetDirection = GetRandomDirection();
        directionChangeTimer = directionChangeInterval;
        currentSpeed = moveSpeed;
        perlinNoiseOffset = Random.Range(0f, 1000f);
        
        // Initialiser les rotations de base et les offsets Perlin
        InitializeBones();
    }

    void Update()
    {
        UpdateDirection();
        UpdateMovement();
        BounceOffBounds();
        AnimateBones();
    }

    /// <summary>
    /// Gère le changement de direction du poisson
    /// </summary>
    private void UpdateDirection()
    {
        directionChangeTimer -= Time.deltaTime;
        
        if (directionChangeTimer <= 0f)
        {
            targetDirection = GetRandomDirection();
            directionChangeTimer = directionChangeInterval + Random.Range(-0.5f, 1f);
            currentSpeed = moveSpeed * Random.Range(1f - speedVariation, 1f + speedVariation);
        }
        
        // Interpolation lisse vers la nouvelle direction
        currentDirection = Vector3.Lerp(currentDirection, targetDirection, turnSpeed * Time.deltaTime).normalized;
        
        // Orienter le poisson vers sa direction
        RotateTowardDirection();
    }

    /// <summary>
    /// Met à jour la position du poisson
    /// </summary>
    private void UpdateMovement()
    {
        // Le poisson avance toujours dans la direction où il regarde
        Vector3 newPosition = GetFishWorldPosition() + currentDirection * currentSpeed * Time.deltaTime;
        
        // Clamp la position dans les limites du périmètre
        newPosition.x = Mathf.Clamp(newPosition.x, boundsMin.x, boundsMax.x);
        newPosition.y = Mathf.Clamp(newPosition.y, boundsMin.y, boundsMax.y);
        newPosition.z = Mathf.Clamp(newPosition.z, boundsMin.z, boundsMax.z);
        
        SetFishWorldPosition(newPosition);
    }

    /// <summary>
    /// Oriente le poisson vers sa direction de mouvement en ne tournant que les bones
    /// </summary>
    private void RotateTowardDirection()
    {
        if (currentDirection.magnitude > 0.01f)
        {
            // Calculer l'angle cible dans le plan XY
            float targetAngle = Mathf.Atan2(currentDirection.y, currentDirection.x) * Mathf.Rad2Deg;
            
            // Appliquer la rotation au root bone qui est correctement orienté par défaut
            if (rootBone != null)
            {
                Quaternion targetRotation = Quaternion.AngleAxis(targetAngle, Vector3.forward);
                rootBone.localRotation = Quaternion.Lerp(rootBone.localRotation, targetRotation, turnSpeed * Time.deltaTime);
                
                // Forcer le root à rester à plat (seulement rotation autour de Z)
                Vector3 eulerAngles = rootBone.localEulerAngles;
                eulerAngles.x = 0f;
                eulerAngles.y = 0f;
                rootBone.localEulerAngles = eulerAngles;
            }
            else
            {
                Quaternion targetRotation = Quaternion.AngleAxis(targetAngle, Vector3.forward);
                transform.localRotation = Quaternion.Lerp(transform.localRotation, targetRotation, turnSpeed * Time.deltaTime);
                
                // Forcer le transform à rester à plat (seulement rotation autour de Z)
                Vector3 eulerAngles = transform.localEulerAngles;
                eulerAngles.x = 0f;
                eulerAngles.y = 0f;
                transform.localEulerAngles = eulerAngles;
            }
        }
    }

    /// <summary>
    /// Anime les rotations des bones (queue, nageoires)
    /// </summary>
    private void AnimateBones()
    {
        if (!enableBoneAnimation)
            return;
            
        perlinNoiseOffset += Time.deltaTime;
        
        // Animer les enfants du body (queue principal)
        if (bodyBone != null)
        {
            AnimateBoneChildren(bodyBone, tailWaveFrequency, tailWaveAmplitude);
        }
        
        // Animer les enfants de la tête
        if (headBone != null)
        {
            AnimateBoneChildren(headBone, finAnimationFrequency, finAnimationAmplitude * 0.5f);
        }
        
        // Animer les enfants de chaque nageoire
        foreach (Transform finBone in finsBones)
        {
            if (finBone != null)
            {
                AnimateBoneChildren(finBone, finAnimationFrequency, finAnimationAmplitude);
            }
        }
    }

    /// <summary>
    /// Anime tous les enfants d'un bone parent
    /// </summary>
    private void AnimateBoneChildren(Transform parentBone, float frequency, float amplitude)
    {
        Transform[] children = parentBone.GetComponentsInChildren<Transform>();
        
        for (int i = 0; i < children.Length; i++)
        {
            Transform bone = children[i];
            if (bone == parentBone) continue; // Ignorer le parent lui-même
            
            float offset = boneNoiseOffsets.ContainsKey(bone) ? boneNoiseOffsets[bone] : i * 0.15f;
            
            // Combiner une onde sinusoïdale avec du bruit Perlin pour plus de naturel
            float sineWave = Mathf.Sin((perlinNoiseOffset + offset) * frequency) * amplitude;
            float perlinNoise = (Mathf.PerlinNoise(perlinNoiseOffset * randomBoneNoiseScale, offset) - 0.5f) * amplitude * 0.5f;
            
            float targetRotation = sineWave + perlinNoise;
            
            Quaternion baseRotation = boneBaseRotations[bone];
            bone.localRotation = baseRotation * Quaternion.Euler(0, 0, targetRotation);
        }
    }

    /// <summary>
    /// Retourne une direction aléatoire
    /// </summary>
    private Vector3 GetRandomDirection()
    {
        // 30% de chance d'aller tout droit (même direction)
        if (Random.value < 0.3f && currentDirection.magnitude > 0.01f)
        {
            return currentDirection;
        }
        
        // Sinon, choisir une direction aléatoire en 3D
        float angleXY = Random.Range(-180f, 180f);
        float angleZ = Random.Range(-90f, 90f);
        
        float x = Mathf.Cos(angleXY * Mathf.Deg2Rad) * Mathf.Cos(angleZ * Mathf.Deg2Rad);
        float y = Mathf.Sin(angleXY * Mathf.Deg2Rad) * Mathf.Cos(angleZ * Mathf.Deg2Rad);
        float z = Mathf.Sin(angleZ * Mathf.Deg2Rad);
        
        return new Vector3(x, y, z).normalized;
    }

    /// <summary>
    /// Retourne une position aléatoire dans les bounds
    /// </summary>
    private Vector3 GetRandomPositionInBounds()
    {
        float randomX = Random.Range(boundsMin.x, boundsMax.x);
        float randomY = Random.Range(boundsMin.y, boundsMax.y);
        float randomZ = Random.Range(boundsMin.z, boundsMax.z);
        
        return new Vector3(randomX, randomY, randomZ);
    }

    /// <summary>
    /// Rebondit sur les limites du périmètre de manière naturelle
    /// </summary>
    private void BounceOffBounds()
    {
        Vector3 fishPos = GetFishWorldPosition();
        bool hitBound = false;
        
        // Si on atteint les limites en X, inverser la direction X
        if (fishPos.x <= boundsMin.x || fishPos.x >= boundsMax.x)
        {
            currentDirection.x *= -1f;
            hitBound = true;
        }
        
        // Si on atteint les limites en Y, inverser la direction Y
        if (fishPos.y <= boundsMin.y || fishPos.y >= boundsMax.y)
        {
            currentDirection.y *= -1f;
            hitBound = true;
        }
        
        // Si on atteint les limites en Z, inverser la direction Z
        if (fishPos.z <= boundsMin.z || fishPos.z >= boundsMax.z)
        {
            currentDirection.z *= -1f;
            hitBound = true;
        }
        
        // Si on a touché une limite, re-générer une nouvelle direction cible
        if (hitBound)
        {
            targetDirection = GetRandomDirection();
            directionChangeTimer = directionChangeInterval * 0.5f; // Forcer un changement rapide
        }
    }

    /// <summary>
    /// Initialise les bones et leurs rotations de base
    /// </summary>
    private void InitializeBones()
    {
        if (!enableBoneAnimation)
            return;

        // Collecter tous les enfants des parents spécifiés
        List<Transform> allBones = new List<Transform>();
        
        if (bodyBone != null)
        {
            foreach (Transform child in bodyBone.GetComponentsInChildren<Transform>())
            {
                if (child != bodyBone)
                    allBones.Add(child);
            }
        }
        
        if (headBone != null)
        {
            foreach (Transform child in headBone.GetComponentsInChildren<Transform>())
            {
                if (child != headBone)
                    allBones.Add(child);
            }
        }
        
        foreach (Transform finBone in finsBones)
        {
            if (finBone != null)
            {
                foreach (Transform child in finBone.GetComponentsInChildren<Transform>())
                {
                    if (child != finBone)
                        allBones.Add(child);
                }
            }
        }
        
        // Sauvegarder les rotations de base et les offsets Perlin
        foreach (Transform bone in allBones)
        {
            if (bone != null)
            {
                boneBaseRotations[bone] = bone.localRotation;
                if (!boneNoiseOffsets.ContainsKey(bone))
                {
                    boneNoiseOffsets[bone] = Random.Range(0f, 1000f);
                }
            }
        }
    }

    /// <summary>
    /// Retourne la position mondiale du poisson (rootBone ou transform)
    /// </summary>
    private Vector3 GetFishWorldPosition()
    {
        return rootBone != null ? rootBone.position : transform.position;
    }

    /// <summary>
    /// Définit la position mondiale du poisson (rootBone ou transform)
    /// </summary>
    private void SetFishWorldPosition(Vector3 newPosition)
    {
        if (rootBone != null)
        {
            rootBone.position = newPosition;
        }
        else
        {
            transform.position = newPosition;
        }
    }

    /// <summary>
    /// Affiche les limites du périmètre en Gizmo (visible dans le viewport)
    /// </summary>
    private void OnDrawGizmos()
    {
        // Calculer le centre et la taille de la boîte
        Vector3 center = (boundsMin + boundsMax) * 0.5f;
        Vector3 size = boundsMax - boundsMin;
        
        // Dessiner le contour de la boîte en vert (wireframe)
        Gizmos.color = Color.green;
        DrawBoxOutline(center, size);
    }

    /// <summary>
    /// Dessine le contour d'une boîte
    /// </summary>
    private void DrawBoxOutline(Vector3 center, Vector3 size)
    {
        Vector3 extents = size * 0.5f;
        
        // Les 8 coins de la boîte
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
        
        // Dessiner les 12 arêtes de la boîte
        // Face avant
        Gizmos.DrawLine(corners[0], corners[1]);
        Gizmos.DrawLine(corners[1], corners[2]);
        Gizmos.DrawLine(corners[2], corners[3]);
        Gizmos.DrawLine(corners[3], corners[0]);
        
        // Face arrière
        Gizmos.DrawLine(corners[4], corners[5]);
        Gizmos.DrawLine(corners[5], corners[6]);
        Gizmos.DrawLine(corners[6], corners[7]);
        Gizmos.DrawLine(corners[7], corners[4]);
        
        // Arêtes connectant les deux faces
        Gizmos.DrawLine(corners[0], corners[4]);
        Gizmos.DrawLine(corners[1], corners[5]);
        Gizmos.DrawLine(corners[2], corners[6]);
        Gizmos.DrawLine(corners[3], corners[7]);
    }
}
