//! P2 #10: QuitGuard handshake — allow quit before the frontend listener mounts.
//!
//! Until `quit_guard_ready` is invoked, window close and tray Quit exit immediately
//! instead of emitting `close-requested` (which nobody would hear on a white screen).

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Manager, State};

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

#[tauri::command]
pub fn quit_guard_ready(state: State<'_, QuitGuardState>) {
    state.mark_ready();
}

#[cfg(test)]
mod tests {
    use super::QuitGuardState;

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
}
