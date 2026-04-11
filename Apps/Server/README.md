# RiverFlow Vision Server

Serveur de vision par ordinateur pour la détection d'impacts au sol en temps réel. Les flux vidéo de plusieurs caméras sont analysés par flux optique dense ; chaque impact détecté est transmis à Unity via OSC (UDP).

## Architecture

```
Apps/Server/
├── pyproject.toml
├── build_dist_linux.sh          # Script de build distribuable Linux
├── build_dist_windows.ps1       # Script de build distribuable Windows
└── src/
    └── riverflow_server/
        ├── main.py              # Point d'entrée — lance l'application Qt
        ├── config.py            # Configuration (AppConfig, load/save JSON)
        ├── camera/
        │   └── manager.py       # CameraManager — threads de capture OpenCV
        ├── calibration/
        │   └── grid.py          # GridCalibrator — homographie par points cliqués
        ├── detection/
        │   ├── floor.py         # FloorDetector — projection pixel → monde
        │   └── impact.py        # ImpactDetector — seuillage flux optique
        ├── osc/
        │   └── sender.py        # OscSender — client UDP python-osc
        └── ui/
            ├── main_window.py   # Fenêtre principale PySide6
            ├── camera_view.py   # Widget d'affichage flux caméra
            └── calibration_widget.py  # Widget de calibration grille
```

## Prérequis

- **Python** >= 3.11
- **uv** — gestionnaire de paquets/environnements ([installation](https://docs.astral.sh/uv/getting-started/installation/))

## Démarrage rapide

```bash
# 1. Installer les dépendances
uv sync

# 2. Lancer le serveur
uv run riverflow-server
```

## Dépendances Python

| Paquet | Rôle |
|---|---|
| `PySide6 >= 6.7` | Interface graphique Qt6 |
| `opencv-python >= 4.10` | Capture caméra et flux optique |
| `python-osc >= 1.9` | Envoi de messages OSC à Unity |
| `numpy >= 1.26` | Calculs matriciels / images |
| `scipy >= 1.13` | Traitement de signal (filtrage) |

## Build distribuable

### Linux

```bash
bash build_dist_linux.sh
# Produit : dist/riverflow-server  (binaire autonome PyInstaller)
```

### Windows

```powershell
.\build_dist_windows.ps1
# Produit : dist\riverflow-server.exe
```

Les scripts appellent PyInstaller (inclus dans le groupe dev) et produisent un exécutable autonome ne nécessitant pas d'installation Python.

## Configuration

La configuration est chargée depuis un fichier JSON (par défaut `config.json` au lancement). Exemple minimal :

```json
{
  "cameras": [
    { "id": "cam0", "source": 0 },
    { "id": "cam1", "source": "rtsp://192.168.1.10/stream" }
  ],
  "osc_host": "127.0.0.1",
  "osc_port": 9000,
  "grid_rows": 8,
  "grid_cols": 6,
  "velocity_threshold": 5.0,
  "calibration_file": "calibration.json"
}
```

| Clé | Type | Description |
|---|---|---|
| `cameras` | liste | Sources caméras : `id` (str) + `source` (int ou URL/RTSP) |
| `osc_host` | str | IP de la machine Unity cible |
| `osc_port` | int | Port UDP écouté par Unity (défaut `9000`) |
| `grid_rows` / `grid_cols` | int | Dimensions de la grille de calibration |
| `velocity_threshold` | float | Seuil de vélocité de flux optique pour déclencher un impact |
| `calibration_file` | str | Chemin vers le fichier de calibration homographie |

## Protocole OSC

Unity doit écouter les adresses suivantes sur le port configuré :

### `/impact/detected`

Déclenché à chaque impact détecté au sol.

| Index | Type | Description |
|---|---|---|
| 0 | `string` | `camera_id` — identifiant de la caméra source |
| 1 | `float` | `x` — position normalisée [0.0, 1.0] |
| 2 | `float` | `y` — position normalisée [0.0, 1.0] |
| 3 | `float` | `velocity` — magnitude de vélocité (≥ 0) |

### `/camera/mapping`

Envoyé lors de la calibration pour transmettre la zone de projection de chaque caméra.

| Index | Type | Description |
|---|---|---|
| 0 | `string` | `camera_id` — identifiant de la caméra |
| 1 | `float` | `x` — coin haut-gauche, normalisé [0, 1] |
| 2 | `float` | `y` — coin haut-gauche, normalisé [0, 1] |
| 3 | `float` | `w` — largeur de la zone, normalisée [0, 1] |
| 4 | `float` | `h` — hauteur de la zone, normalisée [0, 1] |

## Calibration rapide

La calibration établit la correspondance entre les pixels de chaque caméra et les coordonnées monde du sol (homographie).

1. **Lancer le serveur** : `uv run riverflow-server`
2. **Ouvrir le panneau Calibration** dans l'interface.
3. **Définir la grille** : renseigner le nombre de colonnes et de lignes correspondant au quadrillage physique au sol.
4. **Cliquer les intersections** : pour chaque croisement de la grille visible dans le flux caméra, cliquer le point et saisir ses indices (colonne, ligne). Minimum 4 points requis.
5. **Calculer l'homographie** : bouton "Calculer" — l'algorithme RANSAC rejette les clics aberrants.
6. **Sauvegarder** : le fichier `calibration.json` est écrit et rechargé automatiquement au démarrage suivant.
7. **Vérifier** : les positions d'impacts affichées en overlay doivent correspondre au sol réel.

> Répéter l'opération pour chaque caméra. La calibration est persistante entre les sessions.
