# RiverFlow

Ce dépôt contient un projet Unity et les ressources DCC (Blender et autres) pour créer les props.

Note rapide: un script de creation de dossier d'asset existe deja dans `DCC/` (`create_asset.bat` pour Windows et `create_asset.sh` pour Linux/macOS).

## Structure des dossiers

- `Unity_RiverFlow/` : projet Unity principal.
- `DCC/` : fichiers sources DCC, organises par asset (crees a la demande).
- `Apps/` : programmes externes en Rust (serveur/client) pour la communication OSC/NDI.
- `Dist/` : exports, builds et livrables par plateforme (`windows`, `linux`).

## Organisation des scenes

Le projet est pense pour un chargement additive afin de separer les responsabilites.

Ordre propose des scenes:

- `0_Boot` : point d'entree, initialise les systems et charge le reste.
- `1_Lighting` : lumiere globale, probes, fog et post-process.
- `2_Enviro_3D` : environnement 3D, decors, props et collisions.
- `3_Enviro_2D` : environnement 2D, sprites, fonds et overlays.
- `4_Network` : communication externe, OSC, NDI et outils reseau.

Chargement type:

1. Charger `0_Boot` en `Single`.
2. Charger `1_Lighting` en `Additive`.
3. Charger `2_Enviro_3D` en `Additive`.
4. Charger `3_Enviro_2D` en `Additive`.
5. Charger `4_Network` en `Additive`.

## Arborescence

```text
.
├── Unity_RiverFlow/
│   ├── Assets/
│   │   ├── Scenes/
│   │   │   ├── 0_Boot.unity
│   │   │   ├── 1_Lighting.unity
│   │   │   ├── 2_Enviro_3D.unity
│   │   │   ├── 3_Enviro_2D.unity
│   │   │   └── 4_Network.unity
│   │   ├── Projection/    # calibration, masques, warp, profils projo
│   │   ├── Shared/        # assets communs (materiaux, shaders, utilitaires)
│   │   └── Settings/      # reglages projet/gameplay (ScriptableObjects, presets)
│   ├── Packages/
│   ├── ProjectSettings/
│   └── UserSettings/
├── Apps/
│   ├── Cargo.toml          # workspace Rust
│   ├── Server/             # binaire Rust: recoit les interactions et envoie en OSC vers Unity
│   └── ClientNDI/          # binaire Rust: recoit les flux video NDI emis par Unity
├── DCC/
│   ├── README.md            # regles de structure DCC par asset
│   ├── create_asset.bat     # script Windows: cree un dossier d'asset
│   ├── create_asset.sh      # script Linux/macOS: meme logique
│   └── <NomAsset>/
│       └── output/
│           └── textures/
└── Dist/
	├── windows/
	│   ├── client/
	│   ├── serveur/
	│   └── engin/
	└── linux/
		├── client/
		├── serveur/
		└── engin/
```

Details rapides:

- `Projection/` : tout ce qui sert au mapping/projection (calibration, zones, masques, profils par installation).
- `Shared/` : contenu reutilisable par plusieurs scenes pour eviter les doublons.
- `Settings/` : reglages centralises du projet (presets, parametres globaux, donnees de config).
- `Apps/Server` : service reseau qui agrege les interactions (capteurs, events, etc.) puis publie vers Unity en OSC.
- `Apps/ClientNDI` : client de reception des flux NDI generes par Unity (preview, monitoring, routing).
- `Apps/Cargo.toml` : workspace Rust pour compiler/lancer les deux apps avec une seule commande Cargo.
- `DCC` : workflow par asset. Chaque asset a son propre dossier avec un sous-dossier `output/textures`.
- `Dist/windows` et `Dist/linux` : dossiers de sortie separes par plateforme.
- `Dist/*/client` : livrables du client.
- `Dist/*/serveur` : livrables du serveur.
- `Dist/*/engin` : livrables du moteur/engine Unity.

## Convention proposée

- Créer les props dans `DCC/` (ex: fichiers `.blend`), puis exporter vers `Unity_RiverFlow/Assets/` pour intégration dans Unity.
- Pour le detail du workflow DCC (creation par asset), voir `DCC/README.md`.
- Garder les builds exportes dans `Dist/windows` et `Dist/linux`, puis classer par `client`, `serveur` et `engin`.
- Garder les sources de lumiere dans la scene `1_Lighting` uniquement pour eviter les conflits entre scenes.
- Garder `2_Enviro_3D`, `3_Enviro_2D` et `4_Network` separes, puis composer le rendu final via chargement additive.
