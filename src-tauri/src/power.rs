//! Keep the system awake while AutoClip is producing (R2).
//! Allows display sleep; prevents system idle sleep. Idempotent.
//!
//! # Windows thread binding (P2 #15)
//! On Windows, `SetThreadExecutionState` applies to the **calling thread**.
//! Acquire and release must run on the **same** thread that holds the ES flags;
//! Tauri sync commands run on the main thread, so `commands::set_keep_awake`
//! must stay a sync `fn` (never `async fn`). Making it async would move the
//! call off the main thread and silently break keep-awake / leave ES stuck.

use std::sync::atomic::{AtomicBool, Ordering};

static HELD: AtomicBool = AtomicBool::new(false);

/// Apply or clear the keep-awake assertion. Returns whether it is held after the call.
pub fn set_keep_awake(on: bool) -> Result<bool, String> {
    let currently = HELD.load(Ordering::SeqCst);
    if on == currently {
        return Ok(currently);
    }
    if on {
        acquire()?;
        HELD.store(true, Ordering::SeqCst);
        Ok(true)
    } else {
        release()?;
        HELD.store(false, Ordering::SeqCst);
        Ok(false)
    }
}

pub fn is_held() -> bool {
    HELD.load(Ordering::SeqCst)
}

#[cfg(windows)]
fn acquire() -> Result<(), String> {
    use windows_sys::Win32::System::Power::{
        SetThreadExecutionState, ES_CONTINUOUS, ES_SYSTEM_REQUIRED,
    };
    // Thread-bound: ES flags apply only to this thread. Callers (Tauri sync
    // command on the main thread) must not move this onto a worker / async task.
    // ES_SYSTEM_REQUIRED resets the idle timer; omit ES_DISPLAY_REQUIRED so the screen may sleep.
    let prev = unsafe { SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) };
    if prev == 0 {
        return Err("SetThreadExecutionState failed".into());
    }
    Ok(())
}

#[cfg(windows)]
fn release() -> Result<(), String> {
    use windows_sys::Win32::System::Power::{SetThreadExecutionState, ES_CONTINUOUS};
    // Must run on the same thread that called acquire() (see module docs / P2 #15).
    let prev = unsafe { SetThreadExecutionState(ES_CONTINUOUS) };
    if prev == 0 {
        return Err("SetThreadExecutionState(ES_CONTINUOUS) failed".into());
    }
    Ok(())
}

#[cfg(target_os = "macos")]
mod mac {
    use std::ffi::c_void;
    use std::sync::Mutex;

    type CFStringRef = *const c_void;
    type IOPMAssertionID = u32;

    const K_CF_STRING_ENCODING_UTF8: u32 = 0x0800_0100;
    const K_IOPM_ASSERTION_LEVEL_ON: u32 = 255;

    #[link(name = "CoreFoundation", kind = "framework")]
    extern "C" {
        fn CFStringCreateWithCString(
            alloc: *const c_void,
            c_str: *const i8,
            encoding: u32,
        ) -> CFStringRef;
        fn CFRelease(cf: *const c_void);
    }

    #[link(name = "IOKit", kind = "framework")]
    extern "C" {
        fn IOPMAssertionCreateWithName(
            assertion_type: CFStringRef,
            assertion_level: u32,
            assertion_name: CFStringRef,
            assertion_id: *mut IOPMAssertionID,
        ) -> i32;
        fn IOPMAssertionRelease(assertion_id: IOPMAssertionID) -> i32;
    }

    static ASSERTION: Mutex<Option<IOPMAssertionID>> = Mutex::new(None);

    fn cf_string(text: &str) -> Result<CFStringRef, String> {
        let c = std::ffi::CString::new(text).map_err(|e| e.to_string())?;
        let s = unsafe {
            CFStringCreateWithCString(std::ptr::null(), c.as_ptr(), K_CF_STRING_ENCODING_UTF8)
        };
        if s.is_null() {
            return Err("CFStringCreateWithCString failed".into());
        }
        Ok(s)
    }

    pub fn acquire() -> Result<(), String> {
        let mut slot = ASSERTION.lock().map_err(|e| e.to_string())?;
        if slot.is_some() {
            return Ok(());
        }
        // PreventUserIdleSystemSleep: system stays awake; display may still sleep.
        let ty = cf_string("PreventUserIdleSystemSleep")?;
        let name = cf_string("AutoClip producing")?;
        let mut id: IOPMAssertionID = 0;
        let status = unsafe { IOPMAssertionCreateWithName(ty, K_IOPM_ASSERTION_LEVEL_ON, name, &mut id) };
        unsafe {
            CFRelease(ty);
            CFRelease(name);
        }
        if status != 0 {
            return Err(format!("IOPMAssertionCreateWithName failed: {status}"));
        }
        *slot = Some(id);
        Ok(())
    }

    pub fn release() -> Result<(), String> {
        let mut slot = ASSERTION.lock().map_err(|e| e.to_string())?;
        if let Some(id) = slot.take() {
            let status = unsafe { IOPMAssertionRelease(id) };
            if status != 0 {
                return Err(format!("IOPMAssertionRelease failed: {status}"));
            }
        }
        Ok(())
    }
}

#[cfg(target_os = "macos")]
fn acquire() -> Result<(), String> {
    mac::acquire()
}

#[cfg(target_os = "macos")]
fn release() -> Result<(), String> {
    mac::release()
}

#[cfg(all(not(windows), not(target_os = "macos")))]
fn acquire() -> Result<(), String> {
    // Linux: no portable inhibit without D-Bus; no-op is acceptable per R2.
    Ok(())
}

#[cfg(all(not(windows), not(target_os = "macos")))]
fn release() -> Result<(), String> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn idempotent_toggle() {
        assert!(!is_held());
        assert_eq!(set_keep_awake(true).unwrap(), true);
        assert_eq!(set_keep_awake(true).unwrap(), true);
        assert!(is_held());
        assert_eq!(set_keep_awake(false).unwrap(), false);
        assert_eq!(set_keep_awake(false).unwrap(), false);
        assert!(!is_held());
    }

    /// P2 #15: Win ES is thread-bound; the Tauri command must stay sync so it
    /// runs on the main thread with acquire/release.
    #[test]
    fn tauri_set_keep_awake_command_is_not_async() {
        let src = include_str!("commands.rs");
        assert!(
            src.contains("pub fn set_keep_awake("),
            "commands::set_keep_awake must remain a sync fn"
        );
        assert!(
            !src.contains("pub async fn set_keep_awake("),
            "commands::set_keep_awake must not be async (Win SetThreadExecutionState is thread-bound)"
        );
    }
}
