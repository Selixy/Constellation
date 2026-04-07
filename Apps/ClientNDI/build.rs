use std::env;
use std::fs;
use std::path::PathBuf;

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

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap_or_default());
    let profile = env::var("PROFILE").unwrap_or_else(|_| "debug".to_string());

    // Workspace target directory: Apps/target/{profile}
    let target_profile_dir = manifest_dir
        .parent()
        .map(|p| p.join("target").join(&profile))
        .unwrap_or_else(|| manifest_dir.join("target").join(&profile));

    let config_path = target_profile_dir.join("riverflow-client-ndi.yaml");

    if !config_path.exists() {
        let _ = fs::create_dir_all(&target_profile_dir);
        let _ = fs::write(&config_path, DEFAULT_CONFIG);
    }

    println!("cargo:rerun-if-changed=build.rs");
}
