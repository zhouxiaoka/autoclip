//! QuitGuard handshake — allow quit before the frontend listener mounts.
//!
//! Until `quit_guard_ready` is invoked, window close, tray Quit, and macOS
//! Cmd+Q / app-menu Quit exit immediately instead of emitting `close-requested`
//! (which nobody would hear on a white screen).

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Emitter, Manager, State};

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
}
