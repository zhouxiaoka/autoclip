//! QuitGuard handshake — allow quit before the frontend listener mounts.
//!
//! Until `quit_guard_ready` is invoked, window close, tray Quit, and macOS
//! Cmd+Q / app-menu Quit exit immediately instead of emitting `close-requested`
//! (which nobody would hear on a white screen).
//!
//! macOS note: muda's `PredefinedMenuItem::quit` binds `terminate:` which
//! tears the event loop down with no `prevent_exit` point. We replace that
//! item with a normal `MenuItem` id `"quit"` + `CmdOrCtrl+Q`, then route
//! `on_menu_event` through [`handle_quit_click`] → `close-requested`.
//! `should_intercept_exit` / `ExitRequested` stay as a backstop for
//! window-destroy paths that still surface as user exits with `code=None`.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Emitter, Manager, State};
#[cfg(target_os = "macos")]
use tauri::menu::{Menu, MenuItem, MenuItemKind};

pub struct QuitGuardState {
    ready: AtomicBool,
}

impl QuitGuardState {
    pub fn new() -> Self {
        Self {
            ready: AtomicBool::new(false),
        }
    }

    pub fn mark_ready(&self) {
        self.ready.store(true, Ordering::SeqCst);
    }

    pub fn is_ready(&self) -> bool {
        self.ready.load(Ordering::SeqCst)
    }
}

/// True only after the frontend successfully registered the close-requested listener.
pub fn is_ready(app: &AppHandle) -> bool {
    app.try_state::<QuitGuardState>()
        .map(|s| s.is_ready())
        .unwrap_or(false)
}

/// Whether user-driven app exit (Cmd+Q / menu Quit) should be intercepted.
///
/// `exit_code` is [`None`] for user interaction (macOS Cmd+Q / app menu Quit)
/// and [`Some`] when exit was requested via [`AppHandle::exit`] / restart
/// (e.g. FE chose 「仍然退出」 → `confirm_quit`). Only intercept the former,
/// and only after the FE listener is live.
pub fn should_intercept_exit(ready: bool, exit_code: Option<i32>) -> bool {
    ready && exit_code.is_none()
}

/// Emit `close-requested` so QuitGuard can show the dialog (or quit immediately
/// when nothing is running). Shows/focuses main if it was hidden to tray.
pub fn emit_close_requested(app: &AppHandle, from: &str) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.emit(
            "close-requested",
            serde_json::json!({ "from": from }),
        );
    } else {
        app.exit(0);
    }
}

/// Shared Quit click path for tray + macOS app menu (same MenuItem id `"quit"`).
pub fn handle_quit_click(app: &AppHandle, from: &str) {
    if !is_ready(app) {
        app.exit(0);
        return;
    }
    emit_close_requested(app, from);
}

/// macOS app-menu Quit label held so [`crate::tray::set_tray_language`] can update it.
#[cfg(target_os = "macos")]
pub struct AppQuitMenuItem(pub MenuItem<tauri::Wry>);

#[cfg(target_os = "macos")]
fn app_quit_label(language: &str) -> &'static str {
    match language {
        "zh" => "退出 AutoClip",
        "ja" => "AutoClip を終了",
        "ko" => "AutoClip 종료",
        "es" => "Salir de AutoClip",
        "pt" => "Sair do AutoClip",
        "ru" => "Выйти из AutoClip",
        "fr" => "Quitter AutoClip",
        _ => "Quit AutoClip",
    }
}

/// Update the macOS app-menu Quit title after a UI language switch (no-op off macOS / before install).
pub fn set_app_quit_language(app: &AppHandle, language: &str) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        if let Some(item) = app.try_state::<AppQuitMenuItem>() {
            item.0
                .set_text(app_quit_label(language))
                .map_err(|e| e.to_string())?;
        }
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = (app, language);
    }
    Ok(())
}

/// Replace muda's predefined Quit (`terminate:`) with an interceptable MenuItem.
///
/// Call from setup after the shell is up. Installs `Menu::default`, swaps the
/// app-submenu Quit, sets it as the app menu, and manages [`AppQuitMenuItem`].
#[cfg(target_os = "macos")]
pub fn install_interceptable_quit_menu(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let menu = Menu::default(app)?;
    let top = menu.items()?;
    let Some(MenuItemKind::Submenu(app_submenu)) = top.first() else {
        return Err("macOS default menu missing app submenu".into());
    };

    let children = app_submenu.items()?;
    // Menu::default appends PredefinedMenuItem::quit last in the app submenu.
    if let Some(last) = children.last() {
        if last.as_predefined_menuitem().is_some() {
            app_submenu.remove_at(children.len() - 1)?;
        } else {
            return Err("macOS app submenu last item is not predefined Quit".into());
        }
    } else {
        return Err("macOS app submenu is empty".into());
    }

    let quit = MenuItem::with_id(
        app,
        "quit",
        app_quit_label("zh"),
        true,
        Some("CmdOrCtrl+Q"),
    )?;
    app_submenu.append(&quit)?;
    app.manage(AppQuitMenuItem(quit));
    menu.set_as_app_menu()?;
    Ok(())
}

#[tauri::command]
pub fn quit_guard_ready(state: State<'_, QuitGuardState>) {
    state.mark_ready();
}

#[cfg(test)]
mod tests {
    use super::{should_intercept_exit, QuitGuardState};

    #[test]
    fn starts_not_ready() {
        assert!(!QuitGuardState::new().is_ready());
    }

    #[test]
    fn mark_ready_flips_flag() {
        let state = QuitGuardState::new();
        state.mark_ready();
        assert!(state.is_ready());
    }

    #[test]
    fn mark_ready_is_idempotent() {
        let state = QuitGuardState::new();
        state.mark_ready();
        state.mark_ready();
        assert!(state.is_ready());
    }

    #[test]
    fn intercepts_user_cmd_q_when_ready() {
        assert!(should_intercept_exit(true, None));
    }

    #[test]
    fn allows_cmd_q_before_fe_ready() {
        assert!(!should_intercept_exit(false, None));
    }

    #[test]
    fn allows_programmatic_exit_after_confirm() {
        // confirm_quit / quit_app call AppHandle::exit(0) → Some(0)
        assert!(!should_intercept_exit(true, Some(0)));
        assert!(!should_intercept_exit(false, Some(0)));
    }

    #[test]
    fn allows_programmatic_nonzero_exit_code() {
        // AppHandle::restart and other programmatic exits carry Some(code)
        assert!(!should_intercept_exit(true, Some(-1)));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn app_quit_label_defaults_and_zh() {
        assert_eq!(super::app_quit_label("zh"), "退出 AutoClip");
        assert_eq!(super::app_quit_label("en"), "Quit AutoClip");
        assert_eq!(super::app_quit_label("fr"), "Quitter AutoClip");
    }
}
