# DCC Workflow (par asset)

Objectif:
- Chaque asset a son propre dossier, cree a la demande.
- Chaque dossier d'asset contient toujours un sous-dossier `output/textures`.

## Structure attendue

```text
DCC/
├── create_asset.bat      # Windows
├── create_asset.sh       # Linux/macOS
├── README.md
└── NomAsset/
    └── output/
        └── textures/
```

## Regles

1. Creer un dossier par asset (ex: `Coral_Rock_A`, `Seaweed_Long_01`).
2. Garder tous les fichiers lies a cet asset dans son dossier.
3. Utiliser `output/` pour les exports intermediaires/finals.
4. Mettre les textures exportees dans `output/textures/`.
5. Importer ensuite les fichiers utiles dans Unity (`Unity_RiverFlow/Assets/`).

## Creation rapide

- Windows: lancer `create_asset.bat`
- Linux/macOS: lancer `./create_asset.sh`

Les deux scripts demandent le nom de l'asset puis creent:

- `NomAsset/`
- `NomAsset/output/`
- `NomAsset/output/textures/`

