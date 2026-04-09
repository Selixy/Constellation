using UnityEngine;
using System.Collections;

public class DragonflySpawner : MonoBehaviour
{
    public BoxCollider boundingBox;

    [Header("Dragonflies")]
    public GameObject[] dragonflyPrefabs;

    [Header("Spawn Settings")]
    public float minSpawnDelay = 4f;
    public float maxSpawnDelay = 10f;

    [Header("Scale Settings")]
    public float minScale = 0.05f;
    public float maxScale = 0.12f;

    [Header("Sprite Orientation Offset")]
    public float yRotationOffset = 0f; 
    // 👉 mets 90 ou -90 si ton sprite regarde mal

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
        if (dragonflyPrefabs.Length == 0) return;

        Vector3 spawnPos = GetRandomPointOnBounds(bounds);

        // 🎯 direction vers centre (XZ uniquement)
        Vector3 center = bounds.center;
        Vector3 direction = center - spawnPos;
        direction.y = 0f;
        direction.Normalize();

        // 👉 angle propre
        float angle = Mathf.Atan2(direction.x, direction.z) * Mathf.Rad2Deg;

        // 🔥 rotation finale FIXE (X toujours 90)
        Quaternion rotation = Quaternion.Euler(90f, angle + yRotationOffset, 0f);

        GameObject chosenPrefab = dragonflyPrefabs[Random.Range(0, dragonflyPrefabs.Length)];

        GameObject obj = Instantiate(chosenPrefab, spawnPos, rotation);

        // 🎲 scale
        float scale = Random.Range(minScale, maxScale);
        obj.transform.localScale = Vector3.one * scale;
    }

    Vector3 GetRandomPointOnBounds(Bounds bounds)
    {
        Vector3 point = Vector3.zero;

        float centerY = bounds.center.y;

        int side = Random.Range(0, 4);

        switch (side)
        {
            case 0: point.x = bounds.max.x; break;
            case 1: point.x = bounds.min.x; break;
            case 2: point.z = bounds.max.z; break;
            case 3: point.z = bounds.min.z; break;
        }

        if (side < 2)
            point.z = Random.Range(bounds.min.z, bounds.max.z);
        else
            point.x = Random.Range(bounds.min.x, bounds.max.x);

        point.y = centerY;

        return point;
    }
}