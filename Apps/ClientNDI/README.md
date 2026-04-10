# RiverFlow Client

Reçoit les flux vidéo UDP+JPEG émis par Unity et les affiche dans des fenêtres.

## Configuration YAML

Placé à côté de l'exécutable (`<nom>.yaml` ou `riverflow-client-ndi.yaml`) :

```yaml
port: 7000
streams:
  - id: camera_1
    ip: 192.168.1.100
  - id: camera_2
    ip: 192.168.1.100
  - id: camera_3
    ip: 192.168.1.100
```

- `port` : port UDP unique écouté par le client (doit correspondre à `RiverFlowNetwork.targetPort` dans Unity)
- `id` : identifiant du flux, doit correspondre à `NdiCameraSender.streamId` dans Unity
- `ip` : IP de la machine Unity (informatif, affiché dans le titre de fenêtre)

## Build

```bash
# Linux
cargo build -p riverflow-client-ndi --release

# Via build.py (Linux + Windows)
uv run build.py client-ndi
```

## Protocole UDP

Header variable par paquet (little-endian) :

```
[id_len : u8]         longueur de l'identifiant
[id     : N bytes]    identifiant du stream (ex: "camera_1")
[frame_id  : u32]     compteur de frame par stream
[frag_idx  : u16]     index du fragment (0-based)
[frag_count: u16]     nombre total de fragments
[payload   : ...]     octets JPEG
```

Un seul port UDP pour tous les streams, routage par `id`.
