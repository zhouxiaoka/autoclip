//! Startup facts shared with Python and the webview. No user/machine names.
use std::path::{Path, PathBuf};
use std::process::Command;

pub fn app_dir(platform_data_dir: Option<PathBuf>) -> Option<PathBuf> {
    std::env::var_os("AUTOCLIP_APP_DIR")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("AUTOCLIP_DATA_DIR")
                .filter(|value| !value.is_empty())
                .map(PathBuf::from)
        })
        .or_else(|| platform_data_dir.map(|path| path.join("AutoClip")))
        .map(|path| {
            // Python expands these overrides too; keep both readers on one file.
            if let Ok(relative) = path.strip_prefix("~") {
                if let Some(home) = dirs::home_dir() {
                    return home.join(relative);
                }
            }
            absolute(path)
        })
}

/// R24 #298: a relative AUTOCLIP_APP_DIR / AUTOCLIP_DATA_DIR is resolved against the shell's cwd
/// ONCE, here, and the absolute path is what the backend receives, so the shell and the backend
/// (which may start in another cwd) never resolve it to two different marker dirs.
fn absolute(path: PathBuf) -> PathBuf {
    if path.is_absolute() {
        return path;
    }
    std::path::absolute(&path)
        .or_else(|_| std::env::current_dir().map(|cwd| cwd.join(&path)))
        .unwrap_or(path)
}

pub fn anonymous_id(value: &str) -> bool {
    let parts: Vec<&str> = value.split('-').collect();
    let valid_shape = (parts.len() == 1 && parts[0].len() == 32)
        || (parts.len() == 5 && parts.iter().map(|part| part.len()).eq([8, 4, 4, 4, 12]));
    valid_shape
        && parts
            .iter()
            .all(|part| part.bytes().all(|byte| byte.is_ascii_hexdigit()))
}

pub fn device_id(dir: Option<&Path>) -> Option<String> {
    let stored = dir.and_then(|dir| {
        let path = dir.join("analytics.json");
        if std::fs::metadata(&path).ok()?.len() > 4096 {
            return None;
        }
        let data: serde_json::Value = serde_json::from_slice(&std::fs::read(path).ok()?).ok()?;
        let id = data.get("distinct_id")?.as_str()?;
        anonymous_id(id).then(|| id.to_owned())
    });
    stored.or_else(|| {
        std::env::var("AUTOCLIP_ANONYMOUS_DEVICE_ID")
            .ok()
            .filter(|id| anonymous_id(id))
    })
}

pub fn native_os() -> &'static str {
    match std::env::consts::OS {
        "macos" => "macos",
        "windows" => "windows",
        "linux" => "linux",
        _ => "unknown",
    }
}

pub fn native_arch() -> &'static str {
    match std::env::consts::ARCH {
        "aarch64" | "arm64" => "aarch64",
        "x86_64" | "amd64" => "x86_64",
        _ => "unknown",
    }
}

pub fn configure_backend(cmd: &mut Command, dir: Option<&Path>) {
    cmd.env("AUTOCLIP_NATIVE_OS", native_os())
        .env("AUTOCLIP_NATIVE_ARCH", native_arch());
    if let Some(dir) = dir {
        cmd.env("AUTOCLIP_APP_DIR", dir);
    }
    // Do not inherit an arbitrary string that could be a credential or PII.
    cmd.env_remove("AUTOCLIP_ANONYMOUS_DEVICE_ID");
    if let Some(id) = device_id(dir) {
        cmd.env("AUTOCLIP_ANONYMOUS_DEVICE_ID", id);
    }
}

pub fn webview_script(dir: Option<&Path>) -> String {
    let facts = serde_json::json!({ "os": native_os(), "arch": native_arch(), "distinct_id": device_id(dir) });
    format!("Object.defineProperty(window, '__AUTOCLIP_RUNTIME__', {{ value: Object.freeze({facts}), writable: false }});")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn r24_298_relative_app_dir_override_reaches_the_backend_absolute() {
        let saved_app = std::env::var_os("AUTOCLIP_APP_DIR");
        std::env::set_var("AUTOCLIP_APP_DIR", "relative-autoclip-dir");
        let resolved = app_dir(None).unwrap();
        match saved_app {
            Some(value) => std::env::set_var("AUTOCLIP_APP_DIR", value),
            None => std::env::remove_var("AUTOCLIP_APP_DIR"),
        }
        assert!(resolved.is_absolute(), "relative override must be absolutized in the shell");
        assert_eq!(resolved, std::env::current_dir().unwrap().join("relative-autoclip-dir"));
        let mut cmd = Command::new("unused-test-command");
        configure_backend(&mut cmd, Some(&resolved));
        let env: std::collections::HashMap<_, _> = cmd.get_envs().collect();
        let handed = env[std::ffi::OsStr::new("AUTOCLIP_APP_DIR")].unwrap();
        assert!(Path::new(handed).is_absolute());
    }

    #[test]
    fn only_uuid_shaped_anonymous_ids_qualify() {
        assert!(anonymous_id("018f6b2a-7c3d-7b2a-8c11-111111111111"));
        assert!(anonymous_id("018f6b2a7c3d7b2a8c11111111111111"));
        for id in [
            "sk-private-secret",
            "/Users/private/video.mp4",
            "private-title",
            "a@b.com",
            "https://private.example/a",
        ] {
            assert!(!anonymous_id(id));
        }
    }

    #[test]
    fn shared_file_reaches_backend_and_preload_without_paths() {
        let dir =
            std::env::temp_dir().join(format!("autoclip-identity-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let id = "018f6b2a-7c3d-7b2a-8c11-111111111111";
        std::fs::write(
            dir.join("analytics.json"),
            format!(r#"{{"distinct_id":"{id}"}}"#),
        )
        .unwrap();
        let mut cmd = Command::new("unused-test-command");
        configure_backend(&mut cmd, Some(&dir));
        let env: std::collections::HashMap<_, _> = cmd.get_envs().collect();
        assert_eq!(
            env[std::ffi::OsStr::new("AUTOCLIP_ANONYMOUS_DEVICE_ID")],
            Some(std::ffi::OsStr::new(id))
        );
        assert_eq!(
            env[std::ffi::OsStr::new("AUTOCLIP_NATIVE_ARCH")],
            Some(std::ffi::OsStr::new(native_arch()))
        );
        let script = webview_script(Some(&dir));
        assert!(script.contains(id));
        assert!(!script.contains(dir.to_str().unwrap()));
        std::fs::remove_dir_all(dir).unwrap();
    }
}
