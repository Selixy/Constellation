using UnityEngine;

public class WindDisplacement : MonoBehaviour
{
    [SerializeField] private float displacementAmountX = 0.2f; // Intensité du déplacement en X
    [SerializeField] private float displacementAmountY = 0.1f; // Intensité du déplacement en Y
    [SerializeField] private float oscillationSpeed = 1f; // Vitesse d'oscillation
    [SerializeField] private float gustFrequency = 0.3f; // Fréquence des rafales
    [SerializeField] private float gustIntensity = 0.4f; // Intensité des rafales
    [SerializeField] private float displacementReturnSpeed = 2f; // Vitesse de retour à la position initiale
    
    private Vector3 basePosition; // Position de départ de l'objet
    private float perlinNoiseOffset;
    private float gustOffset;
    private Vector3 currentDisplacement; // Déplacement actuel

    void Start()
    {
        // Sauvegarder la position de départ
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
        
        // Oscillation principale lisse en X et Y
        float mainOscillationX = Mathf.PerlinNoise(perlinNoiseOffset, 0) - 0.5f;
        float mainOscillationY = Mathf.PerlinNoise(0, perlinNoiseOffset) - 0.5f;
        
        // Effet de rafales pour plus de naturel
        float gustX = (Mathf.PerlinNoise(gustOffset, 0) - 0.5f) * gustIntensity;
        float gustY = (Mathf.PerlinNoise(0, gustOffset) - 0.5f) * gustIntensity;
        
        // Combiner l'oscillation avec les rafales
        Vector3 targetDisplacement = new Vector3(
            (mainOscillationX + gustX) * displacementAmountX,
            (mainOscillationY + gustY) * displacementAmountY,
            0
        );
        
        // Interpoler le déplacement pour un retour en douceur
        currentDisplacement = Vector3.Lerp(currentDisplacement, targetDisplacement, displacementReturnSpeed * Time.deltaTime);
        
        // Appliquer la position finale
        transform.position = basePosition + currentDisplacement;
    }
}
