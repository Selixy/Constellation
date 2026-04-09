using UnityEngine;
using System.Collections.Generic;

public class Fishes : MonoBehaviour
{
    [Header("Déplacement")]
    [SerializeField] private float moveSpeed = 2f;
    [SerializeField] private float directionChangeInterval = 3f;
    [SerializeField] private float speedVariation = 0.5f;
    [SerializeField] private float turnSpeed = 2f;
    
    [Header("Animation des Bones")]
    [SerializeField] private float tailWaveAmplitude = 15f;
    [SerializeField] private float tailWaveFrequency = 2f;
    [SerializeField] private float finAnimationAmplitude = 10f;
    [SerializeField] private float finAnimationFrequency = 1.5f;
    [SerializeField] private float randomBoneNoiseScale = 0.3f;
    
    [Header("Références")]
    [SerializeField] private Transform rootBone;
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
        // Initialiser la direction
        currentDirection = transform.right;
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
        transform.position += currentDirection * currentSpeed * Time.deltaTime;
    }

    /// <summary>
    /// Oriente le poisson vers sa direction de mouvement en ne tournant que les bones
    /// </summary>
    private void RotateTowardDirection()
    {
        if (currentDirection.magnitude > 0.01f)
        {
            // Calculer l'angle cible
            float targetAngle = Mathf.Atan2(currentDirection.y, currentDirection.x) * Mathf.Rad2Deg;
            
            // Appliquer la rotation au root bone qui est correctement orienté par défaut
            if (rootBone != null)
            {
                Quaternion targetRotation = Quaternion.AngleAxis(targetAngle, Vector3.forward);
                rootBone.localRotation = Quaternion.Lerp(rootBone.localRotation, targetRotation, turnSpeed * Time.deltaTime);
            }
            else
            {
                Quaternion targetRotation = Quaternion.AngleAxis(targetAngle, Vector3.forward);
                transform.localRotation = Quaternion.Lerp(transform.localRotation, targetRotation, turnSpeed * Time.deltaTime);
            }
        }
    }

    /// <summary>
    /// Anime les rotations des bones (queue, nageoires)
    /// </summary>
    private void AnimateBones()
    {
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
        
        // Sinon, choisir une direction aléatoire
        float angle = Random.Range(-180f, 180f);
        return new Vector3(Mathf.Cos(angle * Mathf.Deg2Rad), Mathf.Sin(angle * Mathf.Deg2Rad), 0f).normalized;
    }

    /// <summary>
    /// Initialise les bones et leurs rotations de base
    /// </summary>
    private void InitializeBones()
    {
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
}
