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

    [Header("Turn")]
    public float turnSpeed = 180f;
    public float maxTurnAngle = 120f;

    [Header("Center Bias")]
    [Range(0f, 1f)]
    public float centerBias = 0.2f;

    private BoxCollider boundingBox;
    private float fixedY;

    private bool isMoving;

    private Vector3 moveDirection = Vector3.forward;

    void Start()
    {
        GameObject spawner = GameObject.Find("DragonflySpawner");

        if (spawner != null)
        {
            boundingBox = spawner.GetComponent<BoxCollider>();

            if (boundingBox != null)
            {
                fixedY = boundingBox.bounds.center.y;
            }
        }

        StartCoroutine(StateLoop());
    }

    void Update()
    {
        // 🚀 Mouvement en XZ monde (PAS transform.forward)
        if (isMoving)
        {
            Vector3 move = moveDirection;
            move.y = 0f;

            transform.position += move.normalized * moveSpeed * Time.deltaTime;
        }

        // 📏 Lock hauteur
        Vector3 pos = transform.position;
        pos.y = fixedY;
        transform.position = pos;

        CheckBounds();
    }

    IEnumerator StateLoop()
    {
        while (true)
        {
            // MOVE
            isMoving = true;
            yield return new WaitForSeconds(Random.Range(moveDurationMin, moveDurationMax));

            // STOP
            isMoving = false;
            yield return new WaitForSeconds(Random.Range(idleDurationMin, idleDurationMax));

            // TURN
            yield return StartCoroutine(Turn());
        }
    }

    IEnumerator Turn()
    {
        // 🎲 direction aléatoire
        float randomAngle = Random.Range(-maxTurnAngle, maxTurnAngle);
        Vector3 randomDir = Quaternion.Euler(0f, randomAngle, 0f) * Vector3.forward;

        // 🎯 direction vers centre
        Vector3 center = boundingBox != null ? boundingBox.bounds.center : Vector3.zero;
        Vector3 toCenter = center - transform.position;
        toCenter.y = 0f;
        toCenter = toCenter.normalized;

        // 🧠 mix intelligent
        moveDirection = Vector3.Slerp(randomDir, toCenter, centerBias).normalized;

        // 🔄 rotation Y uniquement (visuelle)
        float targetY = Mathf.Atan2(moveDirection.x, moveDirection.z) * Mathf.Rad2Deg;

        Quaternion targetRot = Quaternion.Euler(90f, targetY, 0f);

        while (Quaternion.Angle(transform.rotation, targetRot) > 1f)
        {
            transform.rotation = Quaternion.RotateTowards(
                transform.rotation,
                targetRot,
                turnSpeed * Time.deltaTime
            );

            yield return null;
        }

        // 🔒 sécurité finale
        transform.rotation = Quaternion.Euler(90f, targetY, 0f);
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