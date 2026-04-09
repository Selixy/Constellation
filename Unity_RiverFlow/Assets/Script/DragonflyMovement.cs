using UnityEngine;
using System.Collections;

public class DragonflyMovement : MonoBehaviour
{
    [Header("Movement")]
    public float moveSpeed = 2f;
    public float moveDurationMin = 1f;
    public float moveDurationMax = 3f;

    [Header("Idle")]
    public float idleDurationMin = 0.5f;
    public float idleDurationMax = 2f;

    [Header("Rotation")]
    public float rotationSpeed = 180f; // degrés/sec
    public float maxTurnAngle = 120f;

    [Header("Center Bias")]
    [Range(0f, 1f)]
    public float centerBias = 0.25f; // 0 = random, 1 = vers centre

    [Header("Spawner Reference")]
    private BoxCollider boundingBox; // Bounding box récupérée automatiquement

    private GameObject DragonflySpawner;

    private bool isMoving = false;

    void Start()
    {
        // Récupérer automatiquement le DragonflySpawner si non assigné
        if (DragonflySpawner == null)
        {
            DragonflySpawner = GameObject.Find("DragonflySpawner"); // nom exact dans la scène
        }

        if (DragonflySpawner != null)
        {
            boundingBox = DragonflySpawner.GetComponent<BoxCollider>();
            if (boundingBox == null)
                Debug.LogWarning("Aucun BoxCollider trouvé sur le DragonflySpawner !");
        }
        else
        {
            Debug.LogWarning("DragonflySpawner non trouvé dans la scène !");
        }

        StartCoroutine(BehaviorLoop());
    }

    void Update()
    {
        if (isMoving)
        {
            transform.position += transform.forward * moveSpeed * Time.deltaTime;
        }

        CheckBounds();
    }

    IEnumerator BehaviorLoop()
    {
        while (true)
        {
            // MOVE
            isMoving = true;
            float moveTime = Random.Range(moveDurationMin, moveDurationMax);
            yield return new WaitForSeconds(moveTime);

            // STOP
            isMoving = false;
            float idleTime = Random.Range(idleDurationMin, idleDurationMax);
            yield return new WaitForSeconds(idleTime);

            // TURN
            yield return StartCoroutine(TurnRoutine());
        }
    }

    IEnumerator TurnRoutine()
    {
        // Rotation aléatoire
        float randomAngle = Random.Range(-maxTurnAngle, maxTurnAngle);
        Quaternion randomRotation = Quaternion.Euler(0, randomAngle, 0);
        Vector3 randomDirection = randomRotation * transform.forward;

        // Direction vers le centre (si boundingBox existe)
        Vector3 center = boundingBox != null ? boundingBox.bounds.center : Vector3.zero;
        center.y = transform.position.y;
        Vector3 toCenter = (center - transform.position).normalized;

        // Mélange des directions
        Vector3 finalDirection = Vector3.Slerp(randomDirection, toCenter, centerBias).normalized;
        Quaternion targetRotation = Quaternion.LookRotation(finalDirection);

        // Rotation progressive
        while (Quaternion.Angle(transform.rotation, targetRotation) > 1f)
        {
            transform.rotation = Quaternion.RotateTowards(
                transform.rotation,
                targetRotation,
                rotationSpeed * Time.deltaTime
            );

            yield return null;
        }
    }

    void CheckBounds()
    {
        if (boundingBox == null) return;

        if (!boundingBox.bounds.Contains(transform.position))
        {
            Destroy(gameObject);
        }
    }
}