use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter, Manager};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendStatus {
    pub is_running: bool,
    pub port: u16,
    pub pid: Option<u32>,
    pub start_time: Option<u64>, // 改为u64以支持序列化
}

impl Default for BackendStatus {
    fn default() -> Self {
        Self {
            is_running: false,
            port: 8000,
            pid: None,
            start_time: None,
        }
    }
}

pub struct BackendManager {
    status: Arc<Mutex<BackendStatus>>,
    process: Arc<Mutex<Option<Child>>>,
    /// R16 #42: per-launch secret for POST /internal/shutdown-intent; never logged.
    local_token: Mutex<String>,
    /// R19 #98: per-launch backend instance id (not secret) and the app dir the backend was given,
    /// so an unacknowledged shutdown intent can be recorded for exactly this backend.
    instance_id: Mutex<String>,
    marker_dir: Mutex<Option<PathBuf>>,
    #[cfg(windows)]
    job: Mutex<Option<crate::windows_job::BackendJob>>,
}

struct BackendLaunch {
    program: String,
    args: Vec<String>,
    working_dir: PathBuf,
}

impl BackendManager {
    pub fn new() -> Self {
        Self {
            status: Arc::new(Mutex::new(BackendStatus::default())),
            process: Arc::new(Mutex::new(None)),
            local_token: Mutex::new(String::new()),
            instance_id: Mutex::new(String::new()),
            marker_dir: Mutex::new(None),
            #[cfg(windows)]
            job: Mutex::new(None),
        }
    }

    pub fn start(&self, app_handle: AppHandle) -> Result<(), String> {
        let mut status = self.status.lock().unwrap();
        if status.is_running {
            return Err("后端服务已在运行".to_string());
        }

        // 启动后端服务
        let launch = self.get_backend_launch(&app_handle)?;

        let mut cmd = Command::new(&launch.program);
        cmd.args(&launch.args)
            .current_dir(&launch.working_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .env("AUTOCLIP_DESKTOP_MODE", "true")
            .env("AUTOCLIP_MODE", "desktop")
            .env(
                "AUTOCLIP_BUILD_ENVIRONMENT",
                if cfg!(debug_assertions) { "development" } else { "production" },
            )
            // Keep signed bundle resources immutable, including Python startup imports.
            .env("PYTHONDONTWRITEBYTECODE", "1")
            // Single source of truth for the version the backend reports in /settings.
            .env("AUTOCLIP_APP_VERSION", env!("CARGO_PKG_VERSION"))
            // The backend exits when this process is gone, even after kill -9 or a crash
            // (macOS has no Job Object; on Windows the job already covers it).
            .env("AUTOCLIP_PARENT_PID", std::process::id().to_string());
        let token = new_local_token()?;
        cmd.env("AUTOCLIP_SHUTDOWN_TOKEN", &token); // env only: never argv, never logged
        *self.local_token.lock().unwrap() = token;
        let instance_id = new_instance_id()?;
        cmd.env("AUTOCLIP_INSTANCE_ID", &instance_id);
        *self.instance_id.lock().unwrap() = instance_id;

        // 崩溃上报：构建时若注入了 SENTRY_DSN，传给 Python 后端（未配置则为空，sentry_setup no-op）
        if let Some(dsn) = option_env!("SENTRY_DSN") {
            cmd.env("SENTRY_DSN", dsn);
        }
        // 和前端同一个项目 key。空值不传，后端遥测保持关闭。只走环境变量，不进 argv，也不写日志。
        if let Some(key) = option_env!("VITE_PUBLIC_POSTHOG_KEY") {
            if !key.is_empty() {
                cmd.env("AUTOCLIP_POSTHOG_KEY", key);
            }
        }

        // Point the backend at the bundled ffmpeg/ffprobe when present.
        // The backend's ffmpeg_utils reads these env vars before falling back
        // to PATH, so this is what makes video processing work on machines
        // without a system ffmpeg installed.
        let ffmpeg_bin = launch
            .working_dir
            .join("ffmpeg")
            .join(Self::exe_name("ffmpeg"));
        if ffmpeg_bin.is_file() {
            cmd.env("AUTOCLIP_FFMPEG_PATH", &ffmpeg_bin);
        }
        let ffprobe_bin = launch
            .working_dir
            .join("ffmpeg")
            .join(Self::exe_name("ffprobe"));
        if ffprobe_bin.is_file() {
            cmd.env("AUTOCLIP_FFPROBE_PATH", &ffprobe_bin);
        }

        // The backend prints emoji/Chinese to stdout; with a piped stdout on
        // Windows Python falls back to the ANSI code page and dies with
        // UnicodeEncodeError before it ever reaches "PORT=". Force UTF-8.
        cmd.env("PYTHONUTF8", "1");
        cmd.env("PYTHONIOENCODING", "utf-8");

        // Backend defaults its data dir to ~/Library/Application Support/AutoClip,
        // which only makes sense on macOS. Resolve the platform data dir here
        // (%APPDATA%\AutoClip on Windows, ~/.local/share/AutoClip on Linux) —
        // on macOS this is exactly the old default, so existing installs keep
        // their data.
        let app_dir = crate::telemetry_runtime::app_dir(app_handle.path().data_dir().ok());
        crate::telemetry_runtime::configure_backend(&mut cmd, app_dir.as_deref());
        // R21 #196: one marker dir, resolved here, handed to the backend; the shell writes `unacked` there too.
        let markers = app_dir.as_deref().map(shutdown_marker_dir);
        if let Some(dir) = markers.as_deref() {
            cmd.env(SHUTDOWN_MARKER_DIR_ENV, dir);
        }
        *self.marker_dir.lock().unwrap() = markers;

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            // Without this every launch pops a black console window for python.exe.
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        match cmd.spawn() {
            #[allow(unused_mut)]
            Ok(mut child) => {
                #[cfg(windows)]
                {
                    // Own the complete process tree, including Celery/ffmpeg.
                    // Closing the app handle (even on a crash) releases DLL locks.
                    match crate::windows_job::BackendJob::attach(&child) {
                        Ok(job) => *self.job.lock().unwrap() = Some(job),
                        Err(error) => {
                            let _ = child.kill();
                            let _ = child.wait();
                            return Err(format!("无法管理后端进程生命周期: {error}"));
                        }
                    }
                }
                let pid = child.id();
                let start_time = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|duration| duration.as_secs())
                    .unwrap_or(0);

                // 启动时先设置为运行状态，但端口未知
                *status = BackendStatus {
                    is_running: true,
                    port: 0, // 端口将在读取stdout后更新
                    pid: Some(pid),
                    start_time: Some(start_time),
                };

                let mut process = self.process.lock().unwrap();
                *process = Some(child);

                // 启动端口读取和健康检查
                let status_clone = self.status.clone();
                let process_clone = self.process.clone();
                let app_handle_clone = app_handle.clone();

                thread::spawn(move || {
                    Self::read_port_and_health_check(status_clone, process_clone, app_handle_clone);
                });

                Ok(())
            }
            Err(e) => Err(format!("启动后端服务失败: {}", e)),
        }
    }

    pub fn stop(&self) -> Result<(), String> {
        self.stop_with_intent(ShutdownIntent::UserQuit)
    }

    /// R16 #42: tell the backend why it is stopping (it writes its marker and answers 200, waited
    /// on for at most 3 s), then kill. A lost parent never comes through here.
    pub fn stop_with_intent(&self, intent: ShutdownIntent) -> Result<(), String> {
        let mut status = self.status.lock().unwrap();
        let mut process = self.process.lock().unwrap();
        if status.port != 0 && process.as_mut().map_or(false, |c| matches!(c.try_wait(), Ok(None))) {
            let token = self.local_token.lock().unwrap().clone();
            let result = notify_shutdown_intent(status.port, &token, intent, Duration::from_secs(3));
            // R19 #98: no 200 in time (timeout, refused, non-200) -> leave a record so the next start
            // reads this exit as unknown instead of crash. Best effort; never blocks the kill.
            if !intent_acknowledged(&result) {
                let instance = self.instance_id.lock().unwrap().clone();
                if let Some(dir) = self.marker_dir.lock().unwrap().as_deref() {
                    let _ = record_unacknowledged_intent(dir, &instance);
                }
            }
        }
        #[cfg(windows)]
        let terminated_tree = {
            let job = self.job.lock().unwrap().take();
            let owned = job.is_some();
            drop(job);
            owned
        };
        #[cfg(not(windows))]
        let terminated_tree = false;
        if let Some(mut child) = process.take() {
            if !terminated_tree && child.try_wait().map_err(|e| e.to_string())?.is_none() {
                if let Err(error) = child.kill() {
                    // Retain ownership if termination failed so it can be retried.
                    *process = Some(child);
                    return Err(format!("停止后端服务失败: {error}"));
                }
            }
            let _ = child.wait();
        }

        *status = BackendStatus::default();
        Ok(())
    }

    pub fn restart(&self, app_handle: AppHandle) -> Result<(), String> {
        // 先停止
        if let Err(e) = self.stop() {
            return Err(format!("停止后端服务失败: {}", e));
        }

        // 等待一秒
        std::thread::sleep(Duration::from_secs(1));

        // 再启动
        self.start(app_handle)
    }

    pub fn get_status(&self) -> BackendStatus {
        self.status.lock().unwrap().clone()
    }

    fn get_backend_launch(&self, app_handle: &AppHandle) -> Result<BackendLaunch, String> {
        if let Ok(resource_path) = app_handle.path().resource_dir() {
            for backend_work_dir in [resource_path.clone(), resource_path.join("resources")] {
                for backend_binary in [
                    backend_work_dir.join(Self::backend_binary_name()),
                    backend_work_dir
                        .join("autoclip-backend")
                        .join(Self::backend_binary_name()),
                ] {
                    if backend_binary.is_file() {
                        let working_dir = backend_binary
                            .parent()
                            .map(|path| path.to_path_buf())
                            .unwrap_or_else(|| backend_work_dir.clone());
                        return Ok(BackendLaunch {
                            program: backend_binary.to_string_lossy().to_string(),
                            args: Vec::new(),
                            working_dir,
                        });
                    }
                }

                let backend_dir = backend_work_dir.join("backend");
                if !backend_dir.exists() {
                    continue;
                }

                let venv_python = Self::venv_python(&backend_work_dir);
                if venv_python.exists() {
                    return Ok(Self::python_launch(
                        venv_python.to_string_lossy().to_string(),
                        backend_work_dir,
                    ));
                }

                // python-build-standalone bundle:
                //   unix:    resources/python/bin/python3
                //   windows: resources/python/python.exe
                let pbs_python = Self::pbs_python(&backend_work_dir);
                if pbs_python.exists() {
                    return Ok(Self::python_launch(
                        pbs_python.to_string_lossy().to_string(),
                        backend_work_dir,
                    ));
                }

                if let Some(system_python) = Self::system_python() {
                    return Ok(Self::python_launch(system_python, backend_work_dir));
                }
            }
        }

        // 开发模式回退到仓库根目录
        if let Ok(current_dir) = std::env::current_dir() {
            if let Some(project_root) = current_dir.parent() {
                let backend_dir = project_root.join("backend");
                if backend_dir.exists() {
                    let venv_python = Self::venv_python(project_root);
                    if venv_python.exists() {
                        return Ok(Self::python_launch(
                            venv_python.to_string_lossy().to_string(),
                            project_root.to_path_buf(),
                        ));
                    }
                    if let Some(system_python) = Self::system_python() {
                        return Ok(Self::python_launch(
                            system_python,
                            project_root.to_path_buf(),
                        ));
                    }
                }
            }
        }

        if let Ok(current_dir) = std::env::current_dir() {
            let backend_dir = current_dir.join("backend");
            if backend_dir.exists() {
                let venv_python = Self::venv_python(&current_dir);
                if venv_python.exists() {
                    return Ok(Self::python_launch(
                        venv_python.to_string_lossy().to_string(),
                        current_dir,
                    ));
                }
                if let Some(system_python) = Self::system_python() {
                    return Ok(Self::python_launch(system_python, current_dir));
                }
            }
        }

        Err("找不到可用的 Python 环境或后端代码".to_string())
    }

    fn exe_name(base: &str) -> String {
        if cfg!(target_os = "windows") {
            format!("{}.exe", base)
        } else {
            base.to_string()
        }
    }

    fn venv_python(root: &std::path::Path) -> PathBuf {
        if cfg!(target_os = "windows") {
            root.join("venv").join("Scripts").join("python.exe")
        } else {
            root.join("venv").join("bin").join("python")
        }
    }

    fn pbs_python(root: &std::path::Path) -> PathBuf {
        if cfg!(target_os = "windows") {
            root.join("python").join("python.exe")
        } else {
            root.join("python").join("bin").join("python3")
        }
    }

    /// First interpreter on PATH that answers `--version`. On Windows `python3`
    /// is usually the Microsoft Store stub, so prefer plain `python` there.
    fn system_python() -> Option<String> {
        let candidates: [&str; 2] = if cfg!(target_os = "windows") {
            ["python", "python3"]
        } else {
            ["python3", "python"]
        };
        candidates
            .iter()
            .find(|name| Command::new(name).arg("--version").output().is_ok())
            .map(|name| name.to_string())
    }

    fn python_launch(program: String, working_dir: PathBuf) -> BackendLaunch {
        BackendLaunch {
            program,
            args: vec!["-m".to_string(), "backend.desktop_main".to_string()],
            working_dir,
        }
    }

    fn backend_binary_name() -> &'static str {
        if cfg!(target_os = "windows") {
            "autoclip-backend.exe"
        } else {
            "autoclip-backend"
        }
    }

    fn read_port_and_health_check(
        status: Arc<Mutex<BackendStatus>>,
        process: Arc<Mutex<Option<Child>>>,
        app_handle: AppHandle,
    ) {
        let (stdout, stderr) = {
            let mut process_guard = process.lock().unwrap();
            if let Some(child) = process_guard.as_mut() {
                (child.stdout.take(), child.stderr.take())
            } else {
                (None, None)
            }
        };

        if let Some(stderr) = stderr {
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().flatten() {
                    eprintln!("Backend error: {}", line);
                }
            });
        }

        if let Some(stdout) = stdout {
            let reader = BufReader::new(stdout);
            let mut emitted_started = false;

            for line in reader.lines().flatten() {
                println!("Backend output: {}", line);

                if !emitted_started && line.starts_with("PORT=") {
                    if let Some(port_str) = line.strip_prefix("PORT=") {
                        if let Ok(port) = port_str.parse::<u16>() {
                            let backend_status = {
                                let mut status_guard = status.lock().unwrap();
                                status_guard.port = port;
                                BackendStatus {
                                    is_running: true,
                                    port,
                                    pid: status_guard.pid,
                                    start_time: status_guard.start_time,
                                }
                            };

                            let _ = app_handle.emit("backend-started", backend_status);
                            println!("Backend started on port: {}", port);

                            let status_health = status.clone();
                            let process_health = process.clone();
                            thread::spawn(move || {
                                Self::health_check_loop(status_health, process_health);
                            });

                            emitted_started = true;
                        }
                    }
                }
            }
        }
    }

    fn health_check_loop(status: Arc<Mutex<BackendStatus>>, process: Arc<Mutex<Option<Child>>>) {
        loop {
            thread::sleep(Duration::from_secs(5));

            // 检查状态
            let should_continue = {
                let status_guard = status.lock().unwrap();
                status_guard.is_running
            };

            if !should_continue {
                break;
            }

            // 检查进程是否还在运行
            let process_exited = {
                let mut process_guard = process.lock().unwrap();
                if let Some(ref mut child) = process_guard.as_mut() {
                    match child.try_wait() {
                        Ok(Some(_)) => {
                            // 进程已退出
                            *process_guard = None;
                            true
                        }
                        Ok(None) => false, // 进程仍在运行
                        Err(_) => {
                            // 检查进程状态失败
                            *process_guard = None;
                            true
                        }
                    }
                } else {
                    true
                }
            };

            if process_exited {
                // 更新状态
                let mut status_guard = status.lock().unwrap();
                *status_guard = BackendStatus::default();
                break;
            }

            // 健康检查
            let port = {
                let status_guard = status.lock().unwrap();
                status_guard.port
            };

            if port > 0 {
                let addr = SocketAddr::from(([127, 0, 0, 1], port));
                if TcpStream::connect_timeout(&addr, Duration::from_secs(2)).is_err() {
                    eprintln!("后端健康检查失败: 端口 {} 不可连接", port);
                }
            }
        }
    }
}


#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShutdownIntent {
    UserQuit,
    Update,
}

impl ShutdownIntent {
    pub fn as_str(self) -> &'static str {
        match self {
            ShutdownIntent::UserQuit => "user_quit",
            ShutdownIntent::Update => "update",
        }
    }
}

/// 32 bytes from the OS CSPRNG, hex-encoded (64 chars). Fails the launch rather than fall back.
fn new_local_token() -> Result<String, String> {
    let mut bytes = [0u8; 32];
    getrandom::getrandom(&mut bytes).map_err(|_| "无法生成本地令牌".to_string())?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

/// 16 bytes from the OS CSPRNG, hex (32 chars): the backend's per-launch instance id.
fn new_instance_id() -> Result<String, String> {
    let mut bytes = [0u8; 16];
    getrandom::getrandom(&mut bytes).map_err(|_| "无法生成实例标识".to_string())?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

pub(crate) fn intent_acknowledged(result: &std::io::Result<bool>) -> bool {
    matches!(result, Ok(true))
}

pub(crate) const SHUTDOWN_MARKER_DIR_ENV: &str = "AUTOCLIP_SHUTDOWN_MARKER_DIR";

/// R21 #196: the single shutdown-record dir for this launch (shell and backend both use it).
pub(crate) fn shutdown_marker_dir(app_dir: &std::path::Path) -> std::path::PathBuf {
    app_dir.join("shutdown_markers")
}

/// R19 #98 / R20 #134: the same per-instance record the backend writes (`<marker dir>/<instance>`)
/// with content `unacked` -> unknown. Created only if no marker exists yet: a marker that landed in time wins.
pub(crate) fn record_unacknowledged_intent(dir: &std::path::Path, instance: &str) -> std::io::Result<()> {
    if instance.len() != 32 || !instance.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) {
        return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "instance"));
    }
    use std::io::Write;
    std::fs::create_dir_all(dir)?;
    match std::fs::OpenOptions::new().write(true).create_new(true).open(dir.join(instance)) {
        Ok(mut file) => file.write_all(b"unacked"),
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => Ok(()),
        Err(error) => Err(error),
    }
}

/// R16 #42: POST /internal/shutdown-intent on loopback and wait (bounded by `budget`) for 200.
pub(crate) fn notify_shutdown_intent(port: u16, token: &str, intent: ShutdownIntent, budget: Duration) -> std::io::Result<bool> {
    use std::io::{Read, Write};
    let deadline = std::time::Instant::now() + budget;
    let left = || deadline.saturating_duration_since(std::time::Instant::now()).max(Duration::from_millis(1));
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&addr, left().min(Duration::from_secs(1)))?;
    stream.set_write_timeout(Some(left()))?;
    let body = format!("{{\"kind\":\"{}\"}}", intent.as_str());
    let request = format!(
        "POST /internal/shutdown-intent HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nX-AutoClip-Local-Token: {token}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    stream.write_all(request.as_bytes())?;
    let mut head = Vec::new();
    let mut buf = [0u8; 64];
    while head.len() < 12 {
        stream.set_read_timeout(Some(left()))?;
        let n = stream.read(&mut buf)?;
        if n == 0 {
            break;
        }
        head.extend_from_slice(&buf[..n]);
    }
    Ok(head.len() >= 12 && &head[9..12] == b"200")
}

#[cfg(test)]
mod shutdown_intent_tests {
    use super::{intent_acknowledged, new_instance_id, new_local_token, notify_shutdown_intent, record_unacknowledged_intent, shutdown_marker_dir, ShutdownIntent, SHUTDOWN_MARKER_DIR_ENV};
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::mpsc;
    use std::thread;
    use std::time::{Duration, Instant};

    #[test]
    fn posts_intent_with_token_and_waits_for_200_before_returning() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let (tx, rx) = mpsc::channel();
        let server = std::thread::spawn(move || {
            let (mut conn, _) = listener.accept().unwrap();
            let mut buf = [0u8; 1024];
            let n = conn.read(&mut buf).unwrap();
            // The marker write happens here; the caller must still be blocked.
            std::thread::sleep(Duration::from_millis(300));
            tx.send(Instant::now()).unwrap();
            conn.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n").unwrap();
            String::from_utf8_lossy(&buf[..n]).to_string()
        });
        let ok = notify_shutdown_intent(port, "tok123", ShutdownIntent::Update, Duration::from_secs(3)).unwrap();
        let returned = Instant::now();
        assert!(ok);
        assert!(returned >= rx.recv().unwrap(), "returned before the backend answered");
        let request = server.join().unwrap();
        assert!(request.starts_with("POST /internal/shutdown-intent HTTP/1.1"));
        assert!(request.contains("X-AutoClip-Local-Token: tok123"));
        assert!(request.ends_with("{\"kind\":\"update\"}"));
    }

    #[test]
    fn non_200_is_not_success() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            let (mut conn, _) = listener.accept().unwrap();
            let mut buf = [0u8; 1024];
            let _ = conn.read(&mut buf);
            conn.write_all(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n").unwrap();
        });
        assert!(!notify_shutdown_intent(port, "bad", ShutdownIntent::UserQuit, Duration::from_secs(3)).unwrap());
    }

    #[test]
    fn silent_backend_times_out_within_budget() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let hold = std::thread::spawn(move || {
            let (conn, _) = listener.accept().unwrap();
            std::thread::sleep(Duration::from_millis(1500));
            drop(conn);
        });
        let started = Instant::now();
        let result = notify_shutdown_intent(port, "t", ShutdownIntent::UserQuit, Duration::from_millis(400));
        assert!(result.is_err() || !result.unwrap());
        assert!(started.elapsed() < Duration::from_millis(1200), "waited past the budget");
        hold.join().unwrap();
    }

    #[test]
    fn unreachable_backend_does_not_block() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        drop(listener);
        assert!(notify_shutdown_intent(port, "t", ShutdownIntent::UserQuit, Duration::from_secs(3)).is_err());
    }

    #[test]
    fn tokens_are_32_csprng_bytes_and_fresh() {
        let (a, b) = (new_local_token().unwrap(), new_local_token().unwrap());
        assert_eq!(a.len(), 64); // 32 bytes
        assert!(a.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(a, b);
    }

    // --- R19 #98 ---------------------------------------------------------------------------
    #[test]
    fn timeout_or_non_200_is_not_acknowledged_and_leaves_an_unacked_record() {
        let silent = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = silent.local_addr().unwrap().port();
        let _hold = thread::spawn(move || { let (_s, _) = silent.accept().unwrap(); thread::sleep(Duration::from_secs(2)); });
        let timed_out = notify_shutdown_intent(port, "t", ShutdownIntent::UserQuit, Duration::from_millis(300));
        assert!(!intent_acknowledged(&timed_out));
        assert!(!intent_acknowledged(&Ok(false)));
        assert!(!intent_acknowledged(&Err(std::io::Error::from(std::io::ErrorKind::ConnectionRefused))));
        assert!(intent_acknowledged(&Ok(true)));
        let dir = std::env::temp_dir().join(format!("acr19-{}", new_instance_id().unwrap()));
        let instance = new_instance_id().unwrap();
        record_unacknowledged_intent(&shutdown_marker_dir(&dir), &instance).unwrap();
        assert_eq!(std::fs::read(dir.join("shutdown_markers").join(&instance)).unwrap(), b"unacked");
        assert!(record_unacknowledged_intent(&shutdown_marker_dir(&dir), "../../etc/passwd").is_err());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn unacked_record_never_overwrites_a_marker_that_landed() {
        // R20 #134: one record per instance in the backend's shutdown_markers dir; marker wins.
        let dir = std::env::temp_dir().join(format!("acr20-{}", new_instance_id().unwrap()));
        let instance = new_instance_id().unwrap();
        std::fs::create_dir_all(dir.join("shutdown_markers")).unwrap();
        std::fs::write(dir.join("shutdown_markers").join(&instance), b"user_quit").unwrap();
        record_unacknowledged_intent(&shutdown_marker_dir(&dir), &instance).unwrap();
        assert_eq!(std::fs::read(dir.join("shutdown_markers").join(&instance)).unwrap(), b"user_quit");
        assert!(!dir.join("shutdown_unacked").exists());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn instance_ids_are_32_hex_and_fresh() {
        let a = new_instance_id().unwrap();
        assert_eq!(a.len(), 32);
        assert!(a.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()));
        assert_ne!(a, new_instance_id().unwrap());
    }

    #[test]
    fn stop_records_unacked_only_when_the_intent_was_not_acknowledged() {
        let src = include_str!("backend_manager.rs");
        let stop = &src[src.find("pub fn stop_with_intent").unwrap()..src.find("pub fn restart").unwrap()];
        let notify = stop.find("notify_shutdown_intent(").unwrap();
        let record = stop.find("record_unacknowledged_intent(").unwrap();
        let kill = stop.find("child.kill()").unwrap();
        assert!(notify < record && record < kill, "record before kill, after notify");
        assert!(stop.contains("if !intent_acknowledged(&result)"));
        assert!(!stop.contains("let _ = notify_shutdown_intent"), "result must not be discarded");
    }
    #[test]
    fn shell_writes_unacked_into_the_dir_it_hands_the_backend() {
        // R21 #196: one resolved dir, passed to the backend in env and used by stop() for `unacked`.
        assert_eq!(SHUTDOWN_MARKER_DIR_ENV, "AUTOCLIP_SHUTDOWN_MARKER_DIR");
        let src = include_str!("backend_manager.rs");
        let start = &src[src.find("pub fn start").unwrap()..src.find("pub fn stop_with_intent").unwrap()];
        assert!(start.contains("cmd.env(SHUTDOWN_MARKER_DIR_ENV, dir)"));
        assert!(start.contains("*self.marker_dir.lock().unwrap() = markers;"));
        let stop = &src[src.find("pub fn stop_with_intent").unwrap()..src.find("pub fn restart").unwrap()];
        assert!(stop.contains("self.marker_dir.lock()"));
    }
}
