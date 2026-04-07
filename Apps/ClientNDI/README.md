# ClientNDI

Programme client pour recevoir les flux NDI emis par Unity.

## YAML de configuration

Le client lit un fichier YAML place a cote de l'executable:

- `<nom_executable>.yaml` (prioritaire)
- sinon `riverflow-client-ndi.yaml`

Exemple:

```yaml
streams:
	- id: camera_1
		ip: 127.0.0.1
	- id: camera_2
		ip: 127.0.0.2
	- id: camera_3
		ip: 127.0.0.3
	- id: camera_4
		ip: 127.0.0.4
```

Chaque paire `id` + `ip` cree une fenetre.

## Comportement au lancement

1. Le client ouvre une fenetre par paire `id/ip` presente dans le YAML.
2. Chaque fenetre tente de se connecter a une source NDI correspondant a l'IP.
3. Si aucun flux n'est recu, la fenetre affiche `NO SIGNAL`.
4. Quand un flux est recu, l'image remplit toute la fenetre.
: Le ratio est preserve, l'image est recadree (crop) si necessaire, sans deformation.

## Build et execution

Build standard (sans SDK NDI local):

```bash
cargo build -p riverflow-client-ndi
```

Dans ce mode, le client ouvre bien les fenetres et affiche `NO SIGNAL`.

Build Windows vers Dist:

```powershell
cd Apps
.\build_dist_windows.ps1
```

Avec NDI active:

```powershell
cd Apps
.\build_dist_windows.ps1 -EnableNdi -NdiDllPath "C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll"
```

Le script place les sorties dans:

- `Dist/windows/client`
- `Dist/windows/serveur`

Packaging Windows NDI depuis Linux (apres cross-build):

```bash
cd Apps
./package_dist_windows_ndi.sh /chemin/vers/Processing.NDI.Lib.x64.dll
```

Ce script ajoute dans `Dist/windows/client`:

- `Processing.NDI.Lib.x64.dll`
- `run-client-ndi.bat`

Build avec reception NDI reelle:

```bash
cargo build -p riverflow-client-ndi --features ndi
```

Ce mode necessite le SDK NDI installe localement (headers + runtime).

## Package portable Linux

Pour creer un dossier portable a copier sur une autre machine Linux:

```bash
cd Apps/ClientNDI
./package_portable_linux.sh /chemin/vers/Processing.NDI.Lib.x86_64.so
```

Le script cree:

- Dist/linux/client/riverflow-client-ndi/riverflow-client-ndi
- Dist/linux/client/riverflow-client-ndi/riverflow-client-ndi.yaml
- Dist/linux/client/riverflow-client-ndi/Processing.NDI.Lib.x86_64.so
- Dist/linux/client/riverflow-client-ndi/run.sh

Puis lancer avec:

```bash
Dist/linux/client/riverflow-client-ndi/run.sh
```

Important:

- NDI ne peut pas etre compile en binaire 100% autonome sans librairie runtime.
- Le mode portable consiste a fournir un dossier self-contained avec le .so NDI a cote du binaire.

## Fichier YAML auto-genere

Un YAML par defaut est genere automatiquement dans `target/<profile>/riverflow-client-ndi.yaml`
si absent lors de la compilation.
