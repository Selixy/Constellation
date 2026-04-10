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
};
use std::thread;
use std::time::{Duration, Instant};

// UDP fragmentation protocol:
//   Header (8 bytes, little-endian):
//     [0..4]  frame_id   : u32
//     [4..6]  frag_idx   : u16  (0-based)
//     [6..8]  frag_count : u16
//   Payload: JPEG fragment bytes

const HEADER_SIZE: usize = 8;
const MAX_PACKET: usize = 65536;
// Stale partial frames older than this are dropped
const FRAME_TIMEOUT: Duration = Duration::from_millis(500);

const DEFAULT_CONFIG: &str = r#"streams:
  - id: camera_1
    ip: 192.168.1.100
    port: 7001
  - id: camera_2
    ip: 192.168.1.100
    port: 7002
  - id: camera_3
    ip: 192.168.1.100
    port: 7003
"#;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StreamPair {
    id: String,
    ip: String,
    port: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClientConfig {
    streams: Vec<StreamPair>,
}

struct PartialFrame {
    frags: Vec<Option<Vec<u8>>>,
    received: usize,
    total: usize,
    last_update: Instant,
}

impl PartialFrame {
    fn new(total: usize) -> Self {
        Self {
            frags: vec![None; total],
            received: 0,
            total,
            last_update: Instant::now(),
        }
    }

    /// Insert a fragment. Returns true when all fragments are received.
    fn insert(&mut self, idx: usize, data: Vec<u8>) -> bool {
        if idx < self.total && self.frags[idx].is_none() {
            self.frags[idx] = Some(data);
            self.received += 1;
            self.last_update = Instant::now();
        }
        self.received == self.total
    }

    fn assemble(&self) -> Vec<u8> {
        self.frags
            .iter()
            .flat_map(|f| f.as_ref().unwrap().iter().copied())
            .collect()
    }
}

fn main() {
    if let Err(err) = run() {
        eprintln!("RiverFlow Client error: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let config_path = resolve_or_create_config_path()?;
    let config = load_config(&config_path)?;

    if config.streams.is_empty() {
        return Err("Le fichier YAML ne contient aucun stream dans 'streams'".to_string());
    }

    let shutdown = Arc::new(AtomicBool::new(false));

    {
        let shutdown = Arc::clone(&shutdown);
        let _ = ctrlc::set_handler(move || {
            shutdown.store(true, Ordering::Relaxed);
        });
    }

    let mut handles = Vec::with_capacity(config.streams.len());
    for pair in config.streams {
        let shutdown = Arc::clone(&shutdown);
        handles.push(thread::spawn(move || run_stream_window(pair, shutdown)));
    }

    for handle in handles {
        match handle.join() {
            Ok(Ok(())) => {}
            Ok(Err(err)) => eprintln!("Thread stream error: {err}"),
            Err(_) => eprintln!("Thread stream panic"),
        }
    }

    Ok(())
}

fn resolve_or_create_config_path() -> Result<PathBuf, String> {
    let exe = env::current_exe()
        .map_err(|e| format!("Impossible de lire le chemin executable: {e}"))?;
    let exe_dir = exe
        .parent()
        .ok_or_else(|| "Impossible de determiner le dossier executable".to_string())?;
    let exe_stem = exe
        .file_stem()
        .and_then(|s| s.to_str())
        .ok_or_else(|| "Impossible de determiner le nom executable".to_string())?;

    let preferred = exe_dir.join(format!("{exe_stem}.yaml"));
    let fallback = exe_dir.join("riverflow-client-ndi.yaml");

    if preferred.exists() {
        return Ok(preferred);
    }
    if fallback.exists() {
        return Ok(fallback);
    }

    fs::write(&preferred, DEFAULT_CONFIG)
        .map_err(|e| format!("Impossible de creer le YAML a cote de l'executable: {e}"))?;
    Ok(preferred)
}

fn load_config(path: &Path) -> Result<ClientConfig, String> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Impossible de lire le YAML '{}': {e}", path.display()))?;
    serde_yaml::from_str::<ClientConfig>(&content)
        .map_err(|e| format!("YAML invalide dans '{}': {e}", path.display()))
}

fn run_stream_window(pair: StreamPair, shutdown: Arc<AtomicBool>) -> Result<(), String> {
    let socket = UdpSocket::bind(format!("0.0.0.0:{}", pair.port))
        .map_err(|e| format!("Bind UDP 0.0.0.0:{} impossible pour '{}': {e}", pair.port, pair.id))?;
    socket
        .set_read_timeout(Some(Duration::from_millis(5)))
        .map_err(|e| format!("set_read_timeout failed: {e}"))?;

    let mut window = Window::new(
        &format!("{} [{}:{}] - NO SIGNAL", pair.id, pair.ip, pair.port),
        960,
        540,
        WindowOptions {
            resize: true,
            scale: minifb::Scale::X1,
            ..WindowOptions::default()
        },
    )
    .map_err(|e| format!("Impossible de creer la fenetre '{}': {e}", pair.id))?;
    window.set_target_fps(60);

    let mut frame_buffer: Vec<u32> = Vec::new();
    let mut partial_frames: HashMap<u32, PartialFrame> = HashMap::new();
    // Last successfully decoded frame (RGB 0x00RRGGBB)
    let mut live_pixels: Option<(Vec<u32>, usize, usize)> = None;
    let mut recv_buf = vec![0u8; MAX_PACKET];

    while window.is_open() && !shutdown.load(Ordering::Relaxed) {
        // Drain all pending UDP packets this tick
        loop {
            match socket.recv(&mut recv_buf) {
                Ok(len) => {
                    if len < HEADER_SIZE {
                        continue;
                    }
                    let frame_id =
                        u32::from_le_bytes(recv_buf[0..4].try_into().unwrap());
                    let frag_idx =
                        u16::from_le_bytes(recv_buf[4..6].try_into().unwrap()) as usize;
                    let frag_count =
                        u16::from_le_bytes(recv_buf[6..8].try_into().unwrap()) as usize;

                    if frag_count == 0 || frag_idx >= frag_count {
                        continue;
                    }

                    let payload = recv_buf[HEADER_SIZE..len].to_vec();
                    let partial = partial_frames
                        .entry(frame_id)
                        .or_insert_with(|| PartialFrame::new(frag_count));

                    if partial.insert(frag_idx, payload) {
                        let jpeg_data = partial.assemble();
                        partial_frames.remove(&frame_id);

                        // Purge stale incomplete frames
                        partial_frames
                            .retain(|_, v| v.last_update.elapsed() < FRAME_TIMEOUT);

                        match decode_jpeg(&jpeg_data) {
                            Ok((pixels, w, h)) => {
                                live_pixels = Some((pixels, w, h));
                            }
                            Err(e) => eprintln!("'{}' JPEG decode error: {e}", pair.id),
                        }
                    }
                }
                Err(ref e)
                    if e.kind() == std::io::ErrorKind::WouldBlock
                        || e.kind() == std::io::ErrorKind::TimedOut =>
                {
                    break
                }
                Err(e) => {
                    eprintln!("'{}' UDP recv error: {e}", pair.id);
                    break;
                }
            }
        }

        let (win_w, win_h) = window.get_size();
        if win_w == 0 || win_h == 0 {
            continue;
        }
        let required = win_w * win_h;
        if frame_buffer.len() != required {
            frame_buffer.resize(required, 0x0010_1010);
        }

        if let Some((ref pixels, src_w, src_h)) = live_pixels {
            blit_cover(pixels, src_w, src_h, &mut frame_buffer, win_w, win_h);
            let _ = window
                .set_title(&format!("{} [{}:{}] - LIVE", pair.id, pair.ip, pair.port));
        } else {
            draw_no_signal(&mut frame_buffer, win_w, win_h, &pair.id, &pair.ip, pair.port);
            let _ = window.set_title(&format!(
                "{} [{}:{}] - NO SIGNAL",
                pair.id, pair.ip, pair.port
            ));
        }

        window
            .update_with_buffer(&frame_buffer, win_w, win_h)
            .map_err(|e| format!("Erreur update fenetre '{}': {e}", pair.id))?;
    }

    shutdown.store(true, Ordering::Relaxed);
    Ok(())
}

fn decode_jpeg(data: &[u8]) -> Result<(Vec<u32>, usize, usize), String> {
    let img = image::load_from_memory(data)
        .map_err(|e| format!("JPEG decode: {e}"))?
        .into_rgb8();
    let w = img.width() as usize;
    let h = img.height() as usize;
    let raw = img.into_raw(); // Vec<u8>, RGB interleaved
    let pixels: Vec<u32> = raw
        .chunks_exact(3)
        .map(|c| ((c[0] as u32) << 16) | ((c[1] as u32) << 8) | c[2] as u32)
        .collect();
    Ok((pixels, w, h))
}

fn blit_cover(
    src: &[u32],
    src_w: usize,
    src_h: usize,
    dst: &mut [u32],
    dst_w: usize,
    dst_h: usize,
) {
    if src_w == 0 || src_h == 0 {
        return;
    }
    let scale = (dst_w as f32 / src_w as f32).max(dst_h as f32 / src_h as f32);
    let crop_x = (src_w as f32 * scale - dst_w as f32) * 0.5;
    let crop_y = (src_h as f32 * scale - dst_h as f32) * 0.5;

    for y in 0..dst_h {
        for x in 0..dst_w {
            let sx = (((x as f32 + crop_x) / scale) as usize).min(src_w - 1);
            let sy = (((y as f32 + crop_y) / scale) as usize).min(src_h - 1);
            dst[y * dst_w + x] = src[sy * src_w + sx];
        }
    }
}

fn draw_no_signal(dst: &mut [u32], w: usize, h: usize, id: &str, ip: &str, port: u16) {
    for px in dst.iter_mut() {
        *px = 0x0012_1212;
    }
    draw_centered_text(dst, w, h, "NO SIGNAL", (h / 2).saturating_sub(20), 0x00FF_FFFF, 3);
    let line2 = format!("{} ({}:{})", id, ip, port);
    draw_centered_text(dst, w, h, &line2, (h / 2).saturating_add(20), 0x00C8_C8C8, 2);
}

fn draw_centered_text(
    dst: &mut [u32],
    w: usize,
    h: usize,
    text: &str,
    y: usize,
    color: u32,
    scale: usize,
) {
    let char_w = 8 * scale;
    let text_w = text.chars().count() * char_w;
    let x0 = w.saturating_sub(text_w) / 2;
    let mut x = x0;
    for ch in text.chars() {
        draw_char(dst, w, h, x, y, ch, color, scale);
        x += char_w;
    }
}

fn draw_char(
    dst: &mut [u32],
    w: usize,
    h: usize,
    x: usize,
    y: usize,
    ch: char,
    color: u32,
    scale: usize,
) {
    if let Some(glyph) = BASIC_FONTS.get(ch) {
        for (row, bits) in glyph.iter().enumerate() {
            for col in 0..8 {
                if (bits >> col) & 1 == 1 {
                    for sy in 0..scale {
                        for sx in 0..scale {
                            let px = x + col * scale + sx;
                            let py = y + row * scale + sy;
                            if px < w && py < h {
                                dst[py * w + px] = color;
                            }
                        }
                    }
                }
            }
        }
    }
}
