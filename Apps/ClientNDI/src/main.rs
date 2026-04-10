use font8x8::{BASIC_FONTS, UnicodeFonts};
use minifb::{Window, WindowOptions};
use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::thread;
use std::time::{Duration, Instant};

#[cfg(feature = "ndi")]
use grafton_ndi::{
    Finder, FinderOptions, Receiver, ReceiverBandwidth, ReceiverColorFormat, ReceiverOptions,
};

#[cfg(feature = "ndi")]
type NdiReceiver = Receiver;

#[cfg(not(feature = "ndi"))]
#[derive(Debug, Clone, Copy)]
struct NdiReceiver;

const DEFAULT_CONFIG: &str = r#"streams:
  - id: camera_1
    ip: 127.0.0.1
  - id: camera_2
    ip: 127.0.0.2
  - id: camera_3
    ip: 127.0.0.3
  - id: camera_4
    ip: 127.0.0.4
"#;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StreamPair {
    id: String,
    ip: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClientConfig {
    streams: Vec<StreamPair>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("RiverFlow ClientNDI error: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let config_path = resolve_or_create_config_path()?;
    let config = load_config(&config_path)?;

    if config.streams.is_empty() {
        return Err("Le fichier YAML ne contient aucune paire id/ip dans streams".to_string());
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
    let exe = env::current_exe().map_err(|e| format!("Impossible de lire le chemin executable: {e}"))?;
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
    #[cfg(feature = "ndi")]
    let ndi = grafton_ndi::NDI::new().map_err(|e| format!("NDI init failed pour {}: {e}", pair.id))?;

    let mut window = Window::new(
        &format!("{} [{}] - NO SIGNAL", pair.id, pair.ip),
        960,
        540,
        WindowOptions {
            resize: true,
            scale: minifb::Scale::X1,
            ..WindowOptions::default()
        },
    )
    .map_err(|e| format!("Impossible de creer la fenetre {}: {e}", pair.id))?;
    window.set_target_fps(60);

    let mut receiver: Option<NdiReceiver> = None;
    let mut last_connect_attempt = Instant::now() - Duration::from_secs(10);
    let mut frame_buffer: Vec<u32> = Vec::new();

    while window.is_open() && !shutdown.load(Ordering::Relaxed) {
        if receiver.is_none() && last_connect_attempt.elapsed() >= Duration::from_secs(2) {
            #[cfg(feature = "ndi")]
            { receiver = try_connect_receiver(&pair, &ndi).ok(); }
            #[cfg(not(feature = "ndi"))]
            { receiver = try_connect_receiver(&pair).ok(); }
            last_connect_attempt = Instant::now();
        }

        let (win_w, win_h) = window.get_size();
        if win_w == 0 || win_h == 0 {
            continue;
        }
        let required = win_w.saturating_mul(win_h);
        if frame_buffer.len() != required {
            frame_buffer.resize(required, 0x0010_1010);
        }

        #[cfg(feature = "ndi")]
        let mut got_video = false;
        #[cfg(not(feature = "ndi"))]
        let got_video = false;
        #[cfg(feature = "ndi")]
        {
            if let Some(rx) = &receiver {
                match rx.capture_video_timeout(Duration::from_millis(5)) {
                    Ok(Some(frame)) => {
                        if let Err(err) = blit_frame_cover(&frame, &mut frame_buffer, win_w, win_h)
                        {
                            eprintln!("{} frame decode error: {err}", pair.id);
                        } else {
                            got_video = true;
                        }
                    }
                    Ok(None) => {}
                    Err(_) => {
                        receiver = None;
                    }
                }
            }
        }

        #[cfg(not(feature = "ndi"))]
        {
            let _ = &receiver;
        }

        if !got_video {
            draw_no_signal(&mut frame_buffer, win_w, win_h, &pair.id, &pair.ip);
            let _ = window.set_title(&format!("{} [{}] - NO SIGNAL", pair.id, pair.ip));
        } else {
            let _ = window.set_title(&format!("{} [{}] - LIVE", pair.id, pair.ip));
        }

        window
            .update_with_buffer(&frame_buffer, win_w, win_h)
            .map_err(|e| format!("Erreur update fenetre {}: {e}", pair.id))?;
    }

    shutdown.store(true, Ordering::Relaxed);
    Ok(())
}

#[cfg(feature = "ndi")]
fn try_connect_receiver(pair: &StreamPair, ndi: &grafton_ndi::NDI) -> Result<NdiReceiver, String> {
    let finder_options = FinderOptions::builder()
        .show_local_sources(true)
        .extra_ips(pair.ip.as_str())
        .build();
    let finder = Finder::new(ndi, &finder_options).map_err(|e| format!("Finder failed: {e}"))?;

    let _ = finder.wait_for_sources(Duration::from_millis(800));
    let sources = finder
        .sources(Duration::from_millis(200))
        .map_err(|e| format!("Source scan failed: {e}"))?;

    // Filtre par IP d'abord, puis par id (nom du flux NDI).
    // Le nom NDI est au format "MACHINE (id)" — on cherche l'id dans le nom.
    let source = sources
        .into_iter()
        .filter(|s| s.matches_host(&pair.ip))
        .find(|s| s.name.to_lowercase().contains(&pair.id.to_lowercase()))
        .or_else(|| {
            // Fallback : si aucun ne matche le nom, on prend le premier qui matche l'IP
            // (comportement legacy pour configs sans id précis)
            eprintln!(
                "Aucune source NDI avec id '{}' sur {}, tentative sur toutes les sources de cette IP",
                pair.id, pair.ip
            );
            None
        })
        .ok_or_else(|| format!(
            "Aucune source NDI '{}' trouvee sur {} — sources disponibles filtrées par IP",
            pair.id, pair.ip
        ))?;

    let options = ReceiverOptions::builder(source)
        .color(ReceiverColorFormat::BGRX_BGRA)
        .bandwidth(ReceiverBandwidth::Highest)
        .name(format!("RiverFlow ClientNDI {}", pair.id))
        .build();

    Receiver::new(ndi, &options).map_err(|e| format!("Receiver create failed: {e}"))
}

#[cfg(not(feature = "ndi"))]
fn try_connect_receiver(_pair: &StreamPair) -> Result<NdiReceiver, String> {
    Err("Client compile sans feature NDI. Rebuild avec --features ndi".to_string())
}

#[cfg(feature = "ndi")]
fn blit_frame_cover(
    frame: &grafton_ndi::VideoFrame,
    dst: &mut [u32],
    dst_w: usize,
    dst_h: usize,
) -> Result<(), String> {
    if frame.width <= 0 || frame.height <= 0 {
        return Err("Frame dimensions invalides".to_string());
    }

    let src_w = frame.width as usize;
    let src_h = frame.height as usize;

    let stride = match frame.line_stride_or_size {
        grafton_ndi::LineStrideOrSize::LineStrideBytes(v) => v as usize,
        grafton_ndi::LineStrideOrSize::DataSizeBytes(_) => {
            return Err("Format compresse non supporte pour affichage direct".to_string())
        }
    };

    if stride < src_w * 4 {
        return Err("Stride frame invalide".to_string());
    }

    let scale = (dst_w as f32 / src_w as f32).max(dst_h as f32 / src_h as f32);
    let rendered_w = src_w as f32 * scale;
    let rendered_h = src_h as f32 * scale;
    let crop_x = (rendered_w - dst_w as f32) * 0.5;
    let crop_y = (rendered_h - dst_h as f32) * 0.5;

    for y in 0..dst_h {
        for x in 0..dst_w {
            let sx_f = ((x as f32 + crop_x) / scale).clamp(0.0, (src_w - 1) as f32);
            let sy_f = ((y as f32 + crop_y) / scale).clamp(0.0, (src_h - 1) as f32);
            let sx = sx_f as usize;
            let sy = sy_f as usize;

            let src_i = sy * stride + sx * 4;
            let b = frame.data[src_i] as u32;
            let g = frame.data[src_i + 1] as u32;
            let r = frame.data[src_i + 2] as u32;

            dst[y * dst_w + x] = (r << 16) | (g << 8) | b;
        }
    }

    Ok(())
}

fn draw_no_signal(dst: &mut [u32], w: usize, h: usize, id: &str, ip: &str) {
    for px in dst.iter_mut() {
        *px = 0x0012_1212;
    }

    let line1 = "NO SIGNAL";
    let line2 = &format!("{} ({})", id, ip);

    draw_centered_text(dst, w, h, line1, (h / 2).saturating_sub(20), 0x00FF_FFFF, 3);
    draw_centered_text(dst, w, h, line2, (h / 2).saturating_add(20), 0x00C8_C8C8, 2);
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
