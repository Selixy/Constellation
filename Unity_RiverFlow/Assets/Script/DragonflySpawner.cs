using UnityEngine;
using System.Collections;

public class DragonflySpawner : MonoBehaviour
{
    public BoxCollider boundingBox;
    public GameObject dragonflyPrefab;

    [Header("Spawn Settings")]
    public float minSpawnDelay = 4f;
    public float maxSpawnDelay = 10f;

    void Start()
    {
        StartCoroutine(SpawnRoutine());
    }

    IEnumerator SpawnRoutine()
    {
        Bounds bounds = boundingBox.bounds;

        while (true)
        {
            SpawnOne(bounds);

            float delay = Random.Range(minSpawnDelay, maxSpawnDelay);
            yield return new WaitForSeconds(delay);
        }
    }

    void SpawnOne(Bounds bounds)
    {
        Vector3 spawnPos = GetRandomPointOnBounds(bounds);

        Vector3 center = bounds.center;
        center.y = spawnPos.y;

        Vector3 direction = (center - spawnPos).normalized;

        Quaternion rotation = Quaternion.LookRotation(direction);
        
        rotation = Quaternion.Euler(0, rotation.eulerAngles.y, 0);

        Instantiate(dragonflyPrefab, spawnPos, rotation);
    }

    Vector3 GetRandomPointOnBounds(Bounds bounds)
    {
        Vector3 point = Vector3.zero;

        float centerY = bounds.center.y;

        int side = Random.Range(0, 4);

        switch (side)
        {
            case 0: // +X
                point.x = bounds.max.x;
                point.z = Random.Range(bounds.min.z, bounds.max.z);
                break;

            case 1: // -X
                point.x = bounds.min.x;
                point.z = Random.Range(bounds.min.z, bounds.max.z);
                break;

            case 2: // +Z
                point.z = bounds.max.z;
                point.x = Random.Range(bounds.min.x, bounds.max.x);
                break;

            case 3: // -Z
                point.z = bounds.min.z;
                point.x = Random.Range(bounds.min.x, bounds.max.x);
                break;
        }

        point.y = centerY;

        return point;
    }
}