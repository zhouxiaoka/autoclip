use crate::backend_manager::BackendManager;
use crate::commands::*;
use crate::tray::setup_system_tray;
use tauri::Manager;

mod backend_manager;
mod commands;
mod tray;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            start_backend_service,
            stop_backend_service,
            restart_backend_service,
            get_service_status,
            show_main_window,
            quit_app,
            enable_autostart,
            disable_autostart,
            is_autostart_enabled
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
