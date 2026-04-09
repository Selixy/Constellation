# Constelation Mocap Server

Ce projet contient le serveur de motion capture basé sur MediaPipe et OpenCV, avec une interface graphique gérée par PyQt6.
L'objectif est de capturer les poses des utilisateurs depuis différentes caméras, de visionner la capture en direct (debug visuel) et d'envoyer les données correspondantes à Unity via le protocole OSC.

## Fonctionnalités

*   **Gestion multi-caméra** : Scanner et basculer facilement entre les différentes caméras.
*   **Tracking Temps Réel** : Utilisation de **MediaPipe Pose**.
*   **Protocole OSC** : Diffusion sur le réseau en local (par défaut localhost:9000).
*   **Interface Performante** : Développée en PyQt6 pour une gestion native et rapide des fenêtres.

## Lancement

```bash
cd Constelation/Apps/Server
uv run python -m server
```
