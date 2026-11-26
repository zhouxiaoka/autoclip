//! Native-only destination preference. No project files or model settings live here.
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

pub const FILE_NAME: &str = "export-preferences.json";
const MAX_BYTES: u64 = 16 * 1024;

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Preferences {
    schema_version: u8,
    #[serde(deserialize_with = "required_directory")]
    directory: Option<PathBuf>,
}

// A custom field decoder makes omission an error while preserving an explicit JSON null.
fn required_directory<'de, D: serde::Deserializer<'de>>(deserializer: D) -> Result<Option<PathBuf>, D::Error> {
    Option::<PathBuf>::deserialize(deserializer)
}

fn validate_directory(directory: &Path) -> Result<(), String> {
    if !directory.is_absolute() || !directory.is_dir() {
        return Err("export_directory_unavailable".into());
    }
    Ok(())
}

pub fn read(path: &Path) -> Result<Option<PathBuf>, String> {
    let file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("export_directory_config_unreadable".into()),
    };
    let mut bytes = Vec::new();
    file.take(MAX_BYTES + 1).read_to_end(&mut bytes)
        .map_err(|_| "export_directory_config_unreadable".to_string())?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err("export_directory_config_invalid".into());
    }
    // Parse the original bytes so duplicate fields remain errors, not last-value-wins resets.
    let prefs: Preferences = serde_json::from_slice(&bytes)
        .map_err(|_| "export_directory_config_invalid".to_string())?;
    if prefs.schema_version != 1 {
        return Err("export_directory_config_invalid".into());
    }
    if let Some(directory) = &prefs.directory {
        validate_directory(directory)?;
    }
    Ok(prefs.directory)
}

/// Invalid preferences or a disconnected custom drive never redirect a download elsewhere.
pub fn destination(path: &Path, downloads: impl FnOnce() -> Result<PathBuf, String>) -> Result<PathBuf, String> {
    match read(path)? {
        Some(directory) => Ok(directory),
        None => {
            let downloads = downloads()?;
            fs::create_dir_all(&downloads).map_err(|_| "export_directory_unavailable".to_string())?;
            Ok(downloads)
        }
    }
}

/// Commit only after a complete private temporary file is flushed; failed writes keep the old value.
pub fn save(path: &Path, directory: Option<&Path>) -> Result<(), String> {
    if let Some(directory) = directory {
        validate_directory(directory)?;
    }
    let payload = serde_json::to_vec(&Preferences {
        schema_version: 1,
        directory: directory.map(Path::to_path_buf),
    }).map_err(|_| "export_directory_config_write_failed".to_string())?;
    let parent = path.parent().ok_or("export_directory_config_write_failed")?;
    fs::create_dir_all(parent).map_err(|_| "export_directory_config_write_failed".to_string())?;
    let mut random = [0_u8; 16];
    getrandom::getrandom(&mut random).map_err(|_| "export_directory_config_write_failed".to_string())?;
    let suffix: String = random.iter().map(|byte| format!("{byte:02x}")).collect();
    let temporary = parent.join(format!(".export-preferences-{suffix}.tmp"));
    let result = (|| {
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options.open(&temporary)?;
        file.write_all(&payload)?;
        file.sync_all()?;
        drop(file);
        fs::rename(&temporary, path)
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result.map_err(|_| "export_directory_config_write_failed".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    static NEXT: AtomicU64 = AtomicU64::new(0);

    struct Sandbox(PathBuf);
    impl Sandbox {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!("autoclip-export-preference-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
        fn folder(&self, name: &str) -> PathBuf {
            let path = self.0.join(name);
            fs::create_dir_all(&path).unwrap();
            path
        }
        fn config(&self) -> PathBuf { self.0.join(FILE_NAME) }
    }
    impl Drop for Sandbox { fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); } }

    #[test]
    fn missing_configuration_preserves_downloads_default() {
        let temp = Sandbox::new();
        let downloads = temp.0.join("Downloads");
        assert_eq!(destination(&temp.config(), || Ok(downloads.clone())).unwrap(), downloads);
        assert!(downloads.is_dir());
        assert!(!temp.config().exists());
    }

    #[test]
    fn selection_survives_a_fresh_disk_read_and_reset() {
        let temp = Sandbox::new();
        let directory = temp.folder("成片 folder");
        let downloads = temp.folder("Downloads");
        save(&temp.config(), Some(&directory)).unwrap();
        assert_eq!(read(&temp.config()).unwrap(), Some(directory.clone()));
        assert_eq!(destination(&temp.config(), || Ok(downloads.clone())).unwrap(), directory);
        save(&temp.config(), None).unwrap();
        assert_eq!(read(&temp.config()).unwrap(), None);
        assert_eq!(destination(&temp.config(), || Ok(downloads.clone())).unwrap(), downloads);
    }

    #[test]
    fn damaged_or_unknown_configuration_does_not_fall_back() {
        let temp = Sandbox::new();
        let downloads = temp.folder("Downloads");
        for payload in ["{", r#"{"schema_version":2,"directory":null}"#, r#"{"schema_version":1,"directory":null,"extra":"unsafe"}"#, "[]"] {
            fs::write(temp.config(), payload).unwrap();
            assert!(destination(&temp.config(), || Ok(downloads.clone())).is_err());
        }
        save(&temp.config(), None).unwrap();
        assert_eq!(destination(&temp.config(), || Ok(downloads.clone())).unwrap(), downloads);
    }

    #[test]
    fn disconnected_custom_folder_is_not_recreated_or_redirected() {
        let temp = Sandbox::new();
        let directory = temp.folder("removable");
        let downloads = temp.folder("Downloads");
        save(&temp.config(), Some(&directory)).unwrap();
        fs::remove_dir(&directory).unwrap();
        assert_eq!(destination(&temp.config(), || Ok(downloads.clone())).unwrap_err(), "export_directory_unavailable");
        assert!(!directory.exists());
    }

    #[test]
    fn invalid_selection_keeps_existing_configuration() {
        let temp = Sandbox::new();
        let directory = temp.folder("valid");
        save(&temp.config(), Some(&directory)).unwrap();
        let before = fs::read(temp.config()).unwrap();
        let file = temp.0.join("not-a-folder");
        fs::write(&file, b"user file").unwrap();
        for invalid in [Path::new("relative"), &file, &temp.0.join("missing")] {
            assert!(save(&temp.config(), Some(invalid)).is_err());
            assert_eq!(fs::read(temp.config()).unwrap(), before);
        }
    }

    #[test]
    fn failed_commit_removes_temporary_file_and_preserves_target() {
        let temp = Sandbox::new();
        let directory = temp.folder("valid");
        let invalid_target = temp.folder("target-is-directory");
        assert!(save(&invalid_target, Some(&directory)).is_err());
        assert!(invalid_target.is_dir());
        assert!(!fs::read_dir(&temp.0).unwrap().any(|entry| entry.unwrap().file_name().to_string_lossy().ends_with(".tmp")));
    }

    #[test]
    fn existing_configuration_requires_an_explicit_directory_field() {
        let temp = Sandbox::new();
        fs::write(temp.config(), r#"{"schema_version":1}"#).unwrap();
        assert_eq!(destination(&temp.config(), || panic!("incomplete configuration must not use Downloads")).unwrap_err(), "export_directory_config_invalid");
        fs::write(temp.config(), r#"{"schema_version":1,"directory":null}"#).unwrap();
        assert_eq!(read(&temp.config()).unwrap(), None);
    }

    #[test]
    fn repeated_fields_cannot_reset_a_custom_destination() {
        let temp = Sandbox::new();
        let custom = temp.folder("custom");
        let encoded = serde_json::to_string(&custom).unwrap();
        for payload in [
            format!(r#"{{"schema_version":1,"directory":{encoded},"directory":null}}"#),
            format!(r#"{{"schema_version":1,"directory":null,"directory":{encoded}}}"#),
            r#"{"schema_version":1,"schema_version":1,"directory":null}"#.to_string(),
        ] {
            fs::write(temp.config(), payload).unwrap();
            assert_eq!(destination(&temp.config(), || panic!("duplicate fields must not use Downloads")).unwrap_err(), "export_directory_config_invalid");
        }
    }

    #[test]
    fn oversized_configuration_is_rejected() {
        let temp = Sandbox::new();
        fs::write(temp.config(), vec![b' '; MAX_BYTES as usize + 1]).unwrap();
        assert_eq!(read(&temp.config()).unwrap_err(), "export_directory_config_invalid");
    }
}
