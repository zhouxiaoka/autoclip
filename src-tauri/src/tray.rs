use tauri::{
    menu::{MenuBuilder, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager,
};

struct TrayLabels([MenuItem<tauri::Wry>; 6]);

fn labels(language: &str) -> [&'static str; 6] {
    match language {
        "zh" => ["显示主窗口", "隐藏主窗口", "启动后端服务", "停止后端服务", "重启后端服务", "退出应用"],
        "ja" => ["ウィンドウを表示", "ウィンドウを隠す", "サービスを開始", "サービスを停止", "サービスを再起動", "終了"],
        "ko" => ["창 표시", "창 숨기기", "서비스 시작", "서비스 중지", "서비스 다시 시작", "종료"],
        "es" => ["Mostrar ventana", "Ocultar ventana", "Iniciar servicio", "Detener servicio", "Reiniciar servicio", "Salir"],
        "pt" => ["Mostrar janela", "Ocultar janela", "Iniciar serviço", "Parar serviço", "Reiniciar serviço", "Sair"],
        "ru" => ["Показать окно", "Скрыть окно", "Запустить сервис", "Остановить сервис", "Перезапустить сервис", "Выйти"],
        "fr" => ["Afficher la fenêtre", "Masquer la fenêtre", "Démarrer le service", "Arrêter le service", "Redémarrer le service", "Quitter"],
        _ => ["Show window", "Hide window", "Start service", "Stop service", "Restart service", "Quit"],
    }
}

#[tauri::command]
pub fn set_tray_language(app: AppHandle, language: String) -> Result<(), String> {
    let state = app.try_state::<TrayLabels>().ok_or("Tray is unavailable")?;
    for (item, text) in state.0.iter().zip(labels(&language)) {
        item.set_text(text).map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn setup_system_tray(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    // 创建菜单项
    let show = MenuItem::with_id(app, "show", "Show window", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "hide", "Hide window", true, None::<&str>)?;
    let separator = MenuItem::with_id(app, "separator1", "", false, None::<&str>)?;
    let start_backend =
        MenuItem::with_id(app, "start_backend", "Start service", true, None::<&str>)?;
    let stop_backend = MenuItem::with_id(app, "stop_backend", "Stop service", true, None::<&str>)?;
    let restart_backend =
        MenuItem::with_id(app, "restart_backend", "Restart service", true, None::<&str>)?;
    let separator2 = MenuItem::with_id(app, "separator2", "", false, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    // 构建菜单
    let menu = MenuBuilder::new(app)
        .item(&show)
        .item(&hide)
        .item(&separator)
        .item(&start_backend)
        .item(&stop_backend)
        .item(&restart_backend)
        .item(&separator2)
        .item(&quit)
        .build()?;

    app.manage(TrayLabels([show, hide, start_backend, stop_backend, restart_backend, quit]));

    // 创建托盘图标
    let _tray = TrayIconBuilder::with_id("main-tray")
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(move |app, event| {
            match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "hide" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.hide();
                    }
                }
                "start_backend" => {
                    // 启动后端服务
                    let backend_manager = app.state::<crate::BackendManager>();
                    match backend_manager.start(app.app_handle().clone()) {
                        Ok(_) => {
                            println!("后端服务启动成功");
                        }
                        Err(e) => {
                            eprintln!("后端服务启动失败: {}", e);
                        }
                    }
                }
                "stop_backend" => {
                    // 停止后端服务
                    let backend_manager = app.state::<crate::BackendManager>();
                    match backend_manager.stop() {
                        Ok(_) => {
                            println!("后端服务停止成功");
                        }
                        Err(e) => {
                            eprintln!("后端服务停止失败: {}", e);
                        }
                    }
                }
                "restart_backend" => {
                    // 重启后端服务
                    let backend_manager = app.state::<crate::BackendManager>();
                    match backend_manager.restart(app.app_handle().clone()) {
                        Ok(_) => {
                            println!("后端服务重启成功");
                        }
                        Err(e) => {
                            eprintln!("后端服务重启失败: {}", e);
                        }
                    }
                }
                "quit" => {
                    // 退出应用
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)?;

    Ok(())
}
