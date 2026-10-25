use crate::backend_manager::BackendManager;
use crate::commands::*;
use crate::tray::setup_system_tray;
use tauri::Manager;

mod backend_manager;
#[cfg(windows)]
mod windows_job;
mod commands;
mod tray;
mod telemetry_runtime;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Use the same platform data-directory resolver as Tauri's path API.
    let telemetry_dir = telemetry_runtime::app_dir(dirs::data_dir());
    let mut builder = tauri::Builder::default();
    // Must be first. The callback receives the launch argv, which can contain
    // an autoclip:// URL and an API key. Do not log argv or cwd.
    #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }));
    }
    builder
        .plugin(tauri::plugin::Builder::<tauri::Wry>::new("telemetry-runtime")
            .js_init_script(telemetry_runtime::webview_script(telemetry_dir.as_deref()))
            .build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .invoke_handler(tauri::generate_handler![
            start_backend_service,
            stop_backend_service,
            restart_backend_service,
            get_service_status,
            show_main_window,
            quit_app,
            enable_autostart,
            disable_autostart,
            is_autostart_enabled,
            crate::tray::set_tray_language,
            save_local_download
        ])
        .manage(BackendManager::new())
        .setup(|app| {
            // 设置环境变量
            std::env::set_var("AUTOCLIP_DESKTOP_MODE", "true");
            std::env::set_var("AUTOCLIP_MODE", "desktop");

            // 设置系统托盘
            if let Err(e) = setup_system_tray(&app.handle()) {
                eprintln!("设置系统托盘失败: {}", e);
            }

            // macOS registers the scheme from the bundled Info.plist only.
            // Windows and Linux also register at runtime so dev and portable builds work.
            #[cfg(any(target_os = "windows", target_os = "linux"))]
            {
                use tauri_plugin_deep_link::DeepLinkExt;
                if let Err(_err) = app.deep_link().register_all() {
                    eprintln!("autoclip deep link registration failed");
                }
            }

            let backend_manager = app.state::<BackendManager>();
            match backend_manager.start(app.handle().clone()) {
                Ok(_) => {
                    println!("后端服务启动中");
                }
                Err(e) => {
                    eprintln!("后端服务启动失败: {}", e);
                    eprintln!("应用将继续运行，但某些功能可能不可用");
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                let _ = app.state::<BackendManager>().stop();
            }
        });
}
