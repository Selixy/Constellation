use font8x8::{BASIC_FONTS, UnicodeFonts};
use minifb::{Window, WindowOptions};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use std::fs;
use std::net::UdpSocket;
use std::path::{Path, PathBuf};
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
    mpsc,
};
use std::thread;
use std::time::{Duration, Instant};

// Protocole UDP (little-endian) :
//   [id_len : u8]
//   [id     : id_len bytes]  — identifiant du stream (ex: "camera_1")
//   [frame_id  : u32]
//   [frag_idx  : u16]        — index 0-based du fragment
//   [frag_count: u16]        — nombre total de fragments
//   [payload   : ...]        — octets JPEG

const MAX_PACKET: usize = 65536;
const FRAME_TIMEOUT: Duration = Duration::from_millis(500);

const DEFAULT_CONFIG: &str = r#"port: 7000
streams:
  - id: camera_1
    ip: 192.168.1.100
  - id: camera_2
    ip: 192.168.1.100
  - id: camera_3
    ip: 192.168.1.100
"#;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StreamPair {
    id: String,
    ip: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClientConfig {
    port: u16,
    streams: Vec<StreamPair>,
}

// Frame décodée prête à l'affichage : pixels ARGB + dimensions
type DecodedFrame = (Vec<u32>, usize, usize);

struct PartialFrame {
    frags: Vec<Option<Vec<u8>>>,
    received: usize,
    total: usize,
    last_update: Instant,
}

impl PartialFrame {
    fn new(total: usize) -> Self {
        Self { frags: vec![None; total], received: 0, total, last_update: Instant::now() }
    }

    fn insert(&mut self, idx: usize, data: Vec<u8>) -> bool {
        if idx < self.total && self.frags[idx].is_none() {
            self.frags[idx] = Some(data);
            self.received += 1;
            self.last_update = Instant::now();
        }
        self.received == self.total
    }

    fn assemble(&self) -> Vec<u8> {
        self.frags.iter().flat_map(|f| f.as_ref().unwrap().iter().copied()).collect()
    }
}

fn main() {
    if let Err(e) = run() {
        eprintln!("RiverFlow Client error: {e}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let config_path = resolve_or_create_config_path()?;
    let config = load_config(&config_path)?;

    if config.streams.is_empty() {
        return Err("Aucun stream dans le YAML".to_string());
    }

    let shutdown = Arc::new(AtomicBool::new(false));
    {
        let s = Arc::clone(&shutdown);
        let _ = ctrlc::set_handler(move || s.store(true, Ordering::Relaxed));
    }

    // Un channel par stream : le receiver thread envoie les frames décodées aux window threads
    let mut senders: HashMap<String, mpsc::Sender<DecodedFrame>> = HashMap::new();
    let mut handles = Vec::new();

    for pair in config.streams {
        let (tx, rx) = mpsc::channel::<DecodedFrame>();
        senders.insert(pair.id.clone(), tx);
        let s = Arc::clone(&shutdown);
        handles.push(thread::spawn(move || run_window(pair, rx, s)));
    }

    // Thread receiver UDP — parse et route les paquets vers les bons channels
    let socket = UdpSocket::bind(format!("0.0.0.0:{}", config.port))
        .map_err(|e| format!("Bind UDP 0.0.0.0:{} impossible: {e}", config.port))?;
    socket.set_read_timeout(Some(Duration::from_millis(20)))
        .map_err(|e| format!("set_read_timeout: {e}"))?;

    {
        let s = Arc::clone(&shutdown);
        thread::spawn(move || run_receiver(socket, senders, s));
    }

    for h in handles {
        match h.join() {
            Ok(Ok(())) => {}
            Ok(Err(e)) => eprintln!("Window thread error: {e}"),
            Err(_)     => eprintln!("Window thread panic"),
        }
    }
    Ok(())
}

// ── Thread réception UDP ──────────────────────────────────────────────────────

fn run_receiver(
    socket: UdpSocket,
    senders: HashMap<String, mpsc::Sender<DecodedFrame>>,
    shutdown: Arc<AtomicBool>,
) {
    // Clé : (stream_id, frame_id)
    let mut partial: HashMap<(String, u32), PartialFrame> = HashMap::new();
    let mut buf = vec![0u8; MAX_PACKET];

    while !shutdown.load(Ordering::Relaxed) {
        match socket.recv(&mut buf) {
            Ok(len) => {
                if let Some((id, frame_id, frag_idx, frag_count, payload)) =
                    parse_header(&buf[..len])
                {
                    let entry = partial
                        .entry((id.clone(), frame_id))
                        .or_insert_with(|| PartialFrame::new(frag_count));

                    if entry.insert(frag_idx, payload.to_vec()) {
                        let jpeg = entry.assemble();
                        partial.remove(&(id.clone(), frame_id));

                        // Purge des frames partielles trop vieilles
                        partial.retain(|_, v| v.last_update.elapsed() < FRAME_TIMEOUT);

                        if let Ok(decoded) = decode_jpeg(&jpeg) {
                            if let Some(tx) = senders.get(&id) {
                                let _ = tx.send(decoded);
                            }
                        }
                    }
                }
            }
            Err(ref e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut => {}
            Err(e) => eprintln!("UDP recv error: {e}"),
        }
    }
}

fn parse_header(buf: &[u8]) -> Option<(String, u32, usize, usize, &[u8])> {
    if buf.is_empty() { return None; }
    let id_len = buf[0] as usize;
    let min_len = 1 + id_len + 4 + 2 + 2;
    if buf.len() < min_len { return None; }

    let id = std::str::from_utf8(&buf[1..1 + id_len]).ok()?.to_string();
    let base = 1 + id_len;
    let frame_id   = u32::from_le_bytes(buf[base..base + 4].try_into().ok()?);
    let frag_idx   = u16::from_le_bytes(buf[base + 4..base + 6].try_into().ok()?) as usize;
    let frag_count = u16::from_le_bytes(buf[base + 6..base + 8].try_into().ok()?) as usize;

    if frag_count == 0 || frag_idx >= frag_count { return None; }

    Some((id, frame_id, frag_idx, frag_count, &buf[min_len..]))
}

// ── Thread fenêtre (un par stream) ───────────────────────────────────────────

fn run_window(
    pair: StreamPair,
    rx: mpsc::Receiver<DecodedFrame>,
    shutdown: Arc<AtomicBool>,
) -> Result<(), String> {
    let mut window = Window::new(
        &format!("{} [{}] - NO SIGNAL", pair.id, pair.ip),
        960,
        540,
        WindowOptions { resize: true, scale: minifb::Scale::X1, ..WindowOptions::default() },
    )
    .map_err(|e| format!("Fenetre '{}': {e}", pair.id))?;
    window.set_target_fps(60);

    let mut frame_buf: Vec<u32> = Vec::new();
    let mut live: Option<DecodedFrame> = None;

    while window.is_open() && !shutdown.load(Ordering::Relaxed) {
        // Draine le channel — garde uniquement la frame la plus récente
        loop {
            match rx.try_recv() {
                Ok(frame) => { live = Some(frame); }
                Err(mpsc::TryRecvError::Empty) => break,
                Err(mpsc::TryRecvError::Disconnected) => break,
            }
        }

        let (w, h) = window.get_size();
        if w == 0 || h == 0 { continue; }
        if frame_buf.len() != w * h { frame_buf.resize(w * h, 0x0010_1010); }

        if let Some((ref pixels, src_w, src_h)) = live {
            blit_cover(pixels, src_w, src_h, &mut frame_buf, w, h);
            let _ = window.set_title(&format!("{} [{}] - LIVE", pair.id, pair.ip));
        } else {
            draw_no_signal(&mut frame_buf, w, h, &pair.id, &pair.ip);
            let _ = window.set_title(&format!("{} [{}] - NO SIGNAL", pair.id, pair.ip));
        }

        window
            .update_with_buffer(&frame_buf, w, h)
            .map_err(|e| format!("update_with_buffer '{}': {e}", pair.id))?;
    }

    shutdown.store(true, Ordering::Relaxed);
    Ok(())
}

// ── JPEG + blit ───────────────────────────────────────────────────────────────

fn decode_jpeg(data: &[u8]) -> Result<DecodedFrame, String> {
    let img = image::load_from_memory(data)
        .map_err(|e| format!("JPEG decode: {e}"))?
        .into_rgb8();
    let w = img.width() as usize;
    let h = img.height() as usize;
    let pixels = img
        .into_raw()
        .chunks_exact(3)
        .map(|c| ((c[0] as u32) << 16) | ((c[1] as u32) << 8) | c[2] as u32)
        .collect();
    Ok((pixels, w, h))
}

fn blit_cover(src: &[u32], src_w: usize, src_h: usize, dst: &mut [u32], dst_w: usize, dst_h: usize) {
    if src_w == 0 || src_h == 0 { return; }
    let scale = (dst_w as f32 / src_w as f32).max(dst_h as f32 / src_h as f32);
    let cx = (src_w as f32 * scale - dst_w as f32) * 0.5;
    let cy = (src_h as f32 * scale - dst_h as f32) * 0.5;
    for y in 0..dst_h {
        for x in 0..dst_w {
            let sx = (((x as f32 + cx) / scale) as usize).min(src_w - 1);
            let sy = (((y as f32 + cy) / scale) as usize).min(src_h - 1);
            dst[y * dst_w + x] = src[sy * src_w + sx];
        }
    }
}

// ── Config ────────────────────────────────────────────────────────────────────

fn resolve_or_create_config_path() -> Result<PathBuf, String> {
    let exe = env::current_exe()
        .map_err(|e| format!("current_exe: {e}"))?;
    let dir = exe.parent()
        .ok_or("pas de dossier parent pour l'executable")?;
    let stem = exe.file_stem().and_then(|s| s.to_str())
        .ok_or("nom executable illisible")?;

    let preferred = dir.join(format!("{stem}.yaml"));
    let fallback  = dir.join("riverflow-client-ndi.yaml");

    if preferred.exists() { return Ok(preferred); }
    if fallback.exists()  { return Ok(fallback); }

    fs::write(&preferred, DEFAULT_CONFIG)
        .map_err(|e| format!("Création YAML: {e}"))?;
    Ok(preferred)
}

fn load_config(path: &Path) -> Result<ClientConfig, String> {
    let txt = fs::read_to_string(path)
        .map_err(|e| format!("Lecture '{}': {e}", path.display()))?;
    serde_yaml::from_str::<ClientConfig>(&txt)
        .map_err(|e| format!("YAML invalide '{}': {e}", path.display()))
}

// ── Affichage NO SIGNAL ───────────────────────────────────────────────────────

fn draw_no_signal(dst: &mut [u32], w: usize, h: usize, id: &str, ip: &str) {
    for px in dst.iter_mut() { *px = 0x0012_1212; }
    draw_centered(dst, w, h, "NO SIGNAL", (h / 2).saturating_sub(20), 0x00FF_FFFF, 3);
    draw_centered(dst, w, h, &format!("{id} ({ip})"), (h / 2).saturating_add(20), 0x00C8_C8C8, 2);
}

fn draw_centered(dst: &mut [u32], w: usize, h: usize, text: &str, y: usize, color: u32, scale: usize) {
    let tw = text.chars().count() * 8 * scale;
    let x0 = w.saturating_sub(tw) / 2;
    let mut x = x0;
    for ch in text.chars() {
        draw_char(dst, w, h, x, y, ch, color, scale);
        x += 8 * scale;
    }
}

fn draw_char(dst: &mut [u32], w: usize, h: usize, x: usize, y: usize, ch: char, color: u32, scale: usize) {
    if let Some(glyph) = BASIC_FONTS.get(ch) {
        for (row, bits) in glyph.iter().enumerate() {
            for col in 0..8usize {
                if (bits >> col) & 1 == 1 {
                    for sy in 0..scale { for sx in 0..scale {
                        let px = x + col * scale + sx;
                        let py = y + row * scale + sy;
                        if px < w && py < h { dst[py * w + px] = color; }
                    }}
                }
            }
        }
    }
}
