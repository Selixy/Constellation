using UnityEngine;

public class RandomRotation : MonoBehaviour
{
    [SerializeField] private float rotationMin = -5f; // Rotation minimale relative en degrés
    [SerializeField] private float rotationMax = 5f; // Rotation maximale relative en degrés
    [SerializeField] private float oscillationSpeed = 1f; // Vitesse d'oscillation
    [SerializeField] private float gustFrequency = 0.3f; // Fréquence des rafales
    [SerializeField] private float windDisplacementAmount = 0.1f; // Intensité du déplacement du vent
    [SerializeField] private float displacementReturnSpeed = 2f; // Vitesse de retour à la position initiale
    
    private float baseRotationZ; // Rotation de départ de l'objet
    private Vector3 basePosition; // Position de départ de l'objet
    private float perlinNoiseOffset;
    private float gustOffset;
    private Vector3 currentDisplacement; // Déplacement actuel

    void Start()
    {
        // Sauvegarder la rotation Z et la position de départ
        baseRotationZ = transform.eulerAngles.z;
        basePosition = transform.position;
        currentDisplacement = Vector3.zero;
        perlinNoiseOffset = Random.Range(0f, 1000f);
        gustOffset = Random.Range(0f, 1000f);
    }

    void Update()
    {
        // Mettre à jour les offsets de bruit Perlin
        perlinNoiseOffset += Time.deltaTime * oscillationSpeed;
        gustOffset += Time.deltaTime * gustFrequency;
        
        // Oscillation principale lisse
        float mainOscillation = Mathf.PerlinNoise(perlinNoiseOffset, 0);
        float mainRotation = Mathf.Lerp(rotationMin, rotationMax, mainOscillation);
        
        // Effet de rafales pour plus de naturel
        float gust = (Mathf.PerlinNoise(gustOffset, 0) - 0.5f) * (rotationMax - rotationMin) * 0.4f;
        
        // Combiner l'oscillation avec les rafales
        float rotationOffset = mainRotation + gust;
        
        // Appliquer la rotation relative à la position de départ
        Vector3 eulerAngles = transform.eulerAngles;
        eulerAngles.z = baseRotationZ + rotationOffset;
        transform.eulerAngles = eulerAngles;
        
        // Ajouter un déplacement très léger basé sur les rafales
        // Les rafales créent un petit décalage en X et Y
        float gustStrength = Mathf.Abs(gust) / ((rotationMax - rotationMin) * 0.4f); // Normaliser l'intensité des rafales
        Vector3 targetDisplacement = new Vector3(gust * windDisplacementAmount, (Mathf.PerlinNoise(0, gustOffset) - 0.5f) * windDisplacementAmount, 0);
        
        // Interpoler le déplacement pour un retour en douceur
        currentDisplacement = Vector3.Lerp(currentDisplacement, targetDisplacement, displacementReturnSpeed * Time.deltaTime);
        
        // Appliquer la position finale
        transform.position = basePosition + currentDisplacement;
    }
}
