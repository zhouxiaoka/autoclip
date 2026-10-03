fn main() {
    // Tauri 2.4 requires this opt-in. Link the desktop VC runtime into the exe:
    // a clean Windows machine must not need a separate redistributable install.
    if std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") {
        std::env::set_var("STATIC_VCRUNTIME", "true");
    }
    tauri_build::build()
}
