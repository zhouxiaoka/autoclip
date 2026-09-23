use std::path::{Path, PathBuf};

use crate::backend_manager::BackendStatus;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_autostart::AutoLaunchManager;

#[tauri::command]
pub async fn start_backend_service(app_handle: AppHandle) -> Result<String, String> {
    let backend_manager = app_handle.state::<crate::BackendManager>();
    match backend_manager.start(app_handle.clone()) {
        Ok(_) => Ok("后端服务启动成功".to_string()),
        Err(e) => Err(e),
    }
}

#[tauri::command]
pub async fn stop_backend_service(app_handle: AppHandle) -> Result<String, String> {
    let backend_manager = app_handle.state::<crate::BackendManager>();
    match backend_manager.stop() {
        Ok(_) => Ok("后端服务停止成功".to_string()),
        Err(e) => Err(e),
    }
}

#[tauri::command]
pub async fn restart_backend_service(app_handle: AppHandle) -> Result<String, String> {
    let backend_manager = app_handle.state::<crate::BackendManager>();
    match backend_manager.restart(app_handle.clone()) {
        Ok(_) => Ok("后端服务重启成功".to_string()),
        Err(e) => Err(e),
    }
}

#[tauri::command]
pub async fn get_service_status(app_handle: AppHandle) -> Result<BackendStatus, String> {
    let backend_manager = app_handle.state::<crate::BackendManager>();
    Ok(backend_manager.get_status())
}

#[tauri::command]
pub async fn show_main_window(app_handle: AppHandle) -> Result<(), String> {
    if let Some(window) = app_handle.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("主窗口不存在".to_string())
    }
}

#[tauri::command]
pub async fn quit_app(app_handle: AppHandle) -> Result<(), String> {
    // 停止后端服务
    let backend_manager = app_handle.state::<crate::BackendManager>();
    let _ = backend_manager.stop();

    // 退出应用
    app_handle.exit(0);
    Ok(())
}

#[tauri::command]
pub async fn enable_autostart(manager: State<'_, AutoLaunchManager>) -> Result<bool, String> {
    match manager.enable() {
        Ok(_) => Ok(true),
        Err(e) => Err(format!("启用自动启动失败: {}", e)),
    }
}

#[tauri::command]
pub async fn disable_autostart(manager: State<'_, AutoLaunchManager>) -> Result<bool, String> {
    match manager.disable() {
        Ok(_) => Ok(false),
        Err(e) => Err(format!("禁用自动启动失败: {}", e)),
    }
}

#[tauri::command]
pub async fn is_autostart_enabled(manager: State<'_, AutoLaunchManager>) -> Result<bool, String> {
    match manager.is_enabled() {
        Ok(enabled) => Ok(enabled),
        Err(e) => Err(format!("检查自动启动状态失败: {}", e)),
    }
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SavedDownload {
    path: String,
    size_bytes: u64,
}

/// macOS 打包后的页面在 `tauri://localhost`。`<a download>` 会被 WKWebView 取消，
/// 因为没有注册下载回调。这里只允许把本机后端的文件写到「下载」文件夹。
#[tauri::command]
pub async fn save_local_download(app: AppHandle, url: String) -> Result<SavedDownload, String> {
    let parsed = local_http_url(&url)?;
    let client = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| e.to_string())?;
    let response = client
        .get(parsed)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    if !response.status().is_success() {
        return Err(format!("download failed: {}", response.status()));
    }
    let filename = filename_from_disposition(
        response
            .headers()
            .get(reqwest::header::CONTENT_DISPOSITION)
            .and_then(|value| value.to_str().ok()),
    );
    let bytes = response.bytes().await.map_err(|e| e.to_string())?;
    if bytes.is_empty() {
        return Err("empty media response".into());
    }
    let dir = app.path().download_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = unique_download_path(&dir, &filename);
    std::fs::write(&path, &bytes).map_err(|e| e.to_string())?;
    Ok(SavedDownload {
        path: path.to_string_lossy().into_owned(),
        size_bytes: bytes.len() as u64,
    })
}

fn local_http_url(url: &str) -> Result<reqwest::Url, String> {
    let parsed = reqwest::Url::parse(url).map_err(|e| e.to_string())?;
    let host = parsed.host_str().unwrap_or("");
    if parsed.scheme() == "http" && (host == "127.0.0.1" || host == "localhost") {
        Ok(parsed)
    } else {
        Err("only local http downloads are allowed".into())
    }
}

fn filename_from_disposition(header: Option<&str>) -> String {
    let Some(header) = header else {
        return "clip.mp4".into();
    };
    let lower = header.to_ascii_lowercase();
    if let Some(index) = lower.find("filename*=") {
        let rest = header[index + "filename*=".len()..]
            .split(';')
            .next()
            .unwrap_or("")
            .trim()
            .trim_matches('"');
        let encoded = rest.split("''").nth(1).unwrap_or(rest);
        return safe_filename(&percent_decode(encoded));
    }
    if let Some(index) = lower.find("filename=") {
        let rest = header[index + "filename=".len()..]
            .split(';')
            .next()
            .unwrap_or("")
            .trim()
            .trim_matches('"');
        return safe_filename(&percent_decode(rest));
    }
    "clip.mp4".into()
}

fn safe_filename(name: &str) -> String {
    let base = Path::new(name)
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("clip.mp4");
    let cleaned: String = base
        .chars()
        .map(|ch| {
            if ch.is_control() || ch == '/' || ch == '\\' || ch == ':' {
                '_'
            } else {
                ch
            }
        })
        .collect();
    let cleaned = cleaned.trim().trim_start_matches('.');
    if cleaned.is_empty() {
        "clip.mp4".into()
    } else {
        cleaned.into()
    }
}

fn percent_decode(input: &str) -> String {
    let bytes = input.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            if let Ok(value) = u8::from_str_radix(
                std::str::from_utf8(&bytes[index + 1..index + 3]).unwrap_or(""),
                16,
            ) {
                out.push(value);
                index += 3;
                continue;
            }
        }
        out.push(bytes[index]);
        index += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn unique_download_path(dir: &Path, filename: &str) -> PathBuf {
    let candidate = dir.join(filename);
    if !candidate.exists() {
        return candidate;
    }
    let stem = Path::new(filename)
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("clip");
    let ext = Path::new(filename)
        .extension()
        .and_then(|value| value.to_str())
        .map(|value| format!(".{value}"))
        .unwrap_or_default();
    let mut counter = 1;
    loop {
        let next = dir.join(format!("{stem} ({counter}){ext}"));
        if !next.exists() {
            return next;
        }
        counter += 1;
    }
}

#[cfg(test)]
mod download_tests {
    use super::{filename_from_disposition, local_http_url, safe_filename, unique_download_path};

    #[test]
    fn rejects_remote_and_custom_scheme_urls() {
        assert!(local_http_url("https://example.com/clip.mp4").is_err());
        assert!(local_http_url("tauri://localhost/api/v1/projects/p/clips/c").is_err());
        assert!(local_http_url("http://192.168.1.2:8000/api/v1/projects/p/download").is_err());
        assert!(local_http_url("http://127.0.0.1:56101/api/v1/projects/p/download?clip_id=c").is_ok());
    }

    #[test]
    fn reads_utf8_content_disposition_and_strips_path() {
        let header = "attachment; filename*=UTF-8''%E9%9F%A9%E5%9B%BD.mp4";
        assert_eq!(filename_from_disposition(Some(header)), "韩国.mp4");
        assert_eq!(safe_filename("../../etc/passwd"), "passwd");
        assert_eq!(safe_filename(".."), "clip.mp4");
    }

    #[test]
    fn does_not_overwrite_an_existing_download() {
        let dir = std::env::temp_dir().join(format!("autoclip-download-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("clip.mp4"), b"old").unwrap();
        let path = unique_download_path(&dir, "clip.mp4");
        assert_eq!(path.file_name().unwrap(), "clip (1).mp4");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
