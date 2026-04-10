using UnityEngine;
using System.Collections;

public class TadpoleSpawner : MonoBehaviour
{
    public BoxCollider boundingBox;

    [Header("Tadpoles")]
    public GameObject tadpolePrefab;

    [Header("Spawn Settings")]
    public float minSpawnDelay = 4f;
    public float maxSpawnDelay = 10f;

    [Header("Scale Settings")]
    public float minScale = 0.05f;
    public float maxScale = 0.12f;

    [Header("Sprite Orientation Offset")]
    public float yRotationOffset = 0f;

    void Start()
    {
        StartCoroutine(SpawnRoutine());
    }

    IEnumerator SpawnRoutine()
    {
        while (true)
        {
            Bounds bounds = boundingBox.bounds;

            SpawnOne(bounds);

            float delay = Random.Range(minSpawnDelay, maxSpawnDelay);
            yield return new WaitForSeconds(delay);
        }
    }

    void SpawnOne(Bounds bounds)
    {
        if (tadpolePrefab == null) return;

        Vector3 spawnPos = GetRandomPointOnBounds(bounds);

        Vector3 center = bounds.center;
        Vector3 direction = center - spawnPos;
        direction.y = 0f;
        direction.Normalize();

        float angle = Mathf.Atan2(direction.x, direction.z) * Mathf.Rad2Deg;

        Quaternion rotation = Quaternion.Euler(0f, angle + yRotationOffset, 0f);

        GameObject obj = Instantiate(tadpolePrefab, spawnPos, rotation);

        float scale = Random.Range(minScale, maxScale);
        obj.transform.localScale = Vector3.one * scale;
    }

    Vector3 GetRandomPointOnBounds(Bounds bounds)
    {
        Vector3 center = bounds.center;
        Vector3 extents = bounds.extents;

        int side = Random.Range(0, 4);
        Vector3 point = center;

        switch (side)
        {
            case 0: point.x = center.x + extents.x; break;
            case 1: point.x = center.x - extents.x; break;
            case 2: point.z = center.z + extents.z; break;
            case 3: point.z = center.z - extents.z; break;
        }

        if (side < 2)
            point.z = Random.Range(center.z - extents.z, center.z + extents.z);
        else
            point.x = Random.Range(center.x - extents.x, center.x + extents.x);

        point.y = 1.5f;

        return point;
    }
}