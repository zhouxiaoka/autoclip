use tauri::{
    menu::{MenuBuilder, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager,
};

pub fn setup_system_tray(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    // 创建菜单项
    let show = MenuItem::with_id(app, "show", "显示主窗口", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "hide", "隐藏主窗口", true, None::<&str>)?;
    let separator = MenuItem::with_id(app, "separator1", "", false, None::<&str>)?;
    let start_backend =
        MenuItem::with_id(app, "start_backend", "启动后端服务", true, None::<&str>)?;
    let stop_backend = MenuItem::with_id(app, "stop_backend", "停止后端服务", true, None::<&str>)?;
    let restart_backend =
        MenuItem::with_id(app, "restart_backend", "重启后端服务", true, None::<&str>)?;
    let separator2 = MenuItem::with_id(app, "separator2", "", false, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出应用", true, None::<&str>)?;

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
