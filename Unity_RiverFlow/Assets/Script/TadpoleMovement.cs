using UnityEngine;

public class TadpoleMovement : MonoBehaviour
{
    [Header("Movement")]
    public float moveSpeed = 1.5f;

    [Header("Wander")]
    public float turnSpeed = 60f;
    public float minTurnInterval = 1.5f;
    public float maxTurnInterval = 4f;
    public float maxTurnAngle = 25f;

    private Vector3 moveDirection;
    private float nextTurnTime;

    void Start()
    {
        moveDirection = transform.forward;
        moveDirection.y = 0f;
        moveDirection.Normalize();

        ScheduleNextTurn();
    }

    void Update()
    {
        // 🚀 déplacement
        transform.position += moveDirection * moveSpeed * Time.deltaTime;

        // 🎯 rotation fluide
        float targetY = Mathf.Atan2(moveDirection.x, moveDirection.z) * Mathf.Rad2Deg;
        Quaternion targetRot = Quaternion.Euler(0f, targetY, 0f);

        transform.rotation = Quaternion.RotateTowards(
            transform.rotation,
            targetRot,
            turnSpeed * Time.deltaTime
        );

        // 🧠 random turn
        if (Time.time >= nextTurnTime)
        {
            DoRandomTurn();
            ScheduleNextTurn();
        }

        CheckBounds();
    }

    void DoRandomTurn()
    {
        float randomAngle = Random.Range(-maxTurnAngle, maxTurnAngle);
        moveDirection = Quaternion.Euler(0f, randomAngle, 0f) * moveDirection;
        moveDirection.y = 0f;
        moveDirection.Normalize();
    }

    void ScheduleNextTurn()
    {
        nextTurnTime = Time.time + Random.Range(minTurnInterval, maxTurnInterval);
    }

    void CheckBounds()
    {
        Vector3 pos = transform.position;

        if (pos.x > 20f || pos.x < -20f || pos.z > 40f || pos.z < -40f)
        {
            Destroy(gameObject); // 💀 mort hors zone
        }
    }
}