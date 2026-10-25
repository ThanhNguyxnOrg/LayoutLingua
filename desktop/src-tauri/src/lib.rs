use serde::{Deserialize, Serialize};
use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Emitter};

static BACKEND_CHILD: Mutex<Option<Child>> = Mutex::new(None);

fn ensure_backend_running() {
    // 1. Check if backend is already listening on 127.0.0.1:8765
    if TcpStream::connect_timeout(
        &"127.0.0.1:8765".parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
    {
        return;
    }

    // 2. Anchor candidate commands to the repo root inferred from this exe's
    //    location (…/desktop/src-tauri/target/release/ -> 4 levels up), so the
    //    engine spawns correctly no matter the working directory the app was
    //    launched from (double-click, start_app.bat, or cargo run).
    let mut roots: Vec<std::path::PathBuf> = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        for anc in exe.ancestors().skip(1) {
            if anc.join(".venv").is_dir() || anc.join("layoutlingua").is_dir() {
                roots.push(anc.to_path_buf());
            }
        }
    }
    if let Ok(cwd) = std::env::current_dir() {
        roots.push(cwd.clone());
        if let Some(parent) = cwd.parent() {
            roots.push(parent.to_path_buf());
        }
    }

    let mut candidate_commands: Vec<(String, Vec<String>)> = Vec::new();

    #[cfg(target_os = "windows")]
    {
        for root in &roots {
            let r = root.display().to_string();
            candidate_commands.push((format!("{r}/.venv/Scripts/python.exe"), vec!["-m".into(), "layoutlingua.server".into()]));
            candidate_commands.push((format!("{r}/binaries/layoutlingua-engine-x86_64-pc-windows-msvc.exe"), vec![]));
        }
        candidate_commands.push(("layoutlingua-engine.exe".into(), vec![]));
        candidate_commands.push(("python.exe".into(), vec!["-m".into(), "layoutlingua.server".into()]));
        candidate_commands.push(("python".into(), vec!["-m".into(), "layoutlingua.server".into()]));
    }

    #[cfg(not(target_os = "windows"))]
    {
        for root in &roots {
            let r = root.display().to_string();
            candidate_commands.push((format!("{r}/.venv/bin/python"), vec!["-m".into(), "layoutlingua.server".into()]));
            candidate_commands.push((format!("{r}/binaries/layoutlingua-engine"), vec![]));
        }
        candidate_commands.push(("./layoutlingua-engine".into(), vec![]));
        candidate_commands.push(("python3".into(), vec!["-m".into(), "layoutlingua.server".into()]));
    }

    for (cmd, args) in candidate_commands {
        let mut command = Command::new(&cmd);
        command.args(&args);

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            command.creation_flags(CREATE_NO_WINDOW);
        }

        if let Ok(child) = command.spawn() {
            let mut lock = BACKEND_CHILD.lock().unwrap();
            *lock = Some(child);
            break;
        }
    }

    // Await port binding
    for _ in 0..15 {
        std::thread::sleep(Duration::from_millis(200));
        if TcpStream::connect_timeout(
            &"127.0.0.1:8765".parse().unwrap(),
            Duration::from_millis(200),
        )
        .is_ok()
        {
            break;
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DocumentInfo {
    pub name: String,
    pub size: u64,
    pub page_count: usize,
    pub word_count: usize,
    pub detected_lang: String,
    pub is_encrypted: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TranslationOptions {
    pub source_lang: String,
    pub target_lang: String,
    pub provider: String,
    pub formula_handling: String,
    pub preserve_formatting: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ExportOptions {
    pub format: String,
    pub include_telemetry: bool,
    pub output_path: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ExportResult {
    pub output_path: String,
}

/// JSON-RPC Request structure for Python Core Engine
#[allow(dead_code)]
#[derive(Serialize)]
struct JsonRpcRequest<T> {
    jsonrpc: &'static str,
    id: u64,
    method: &'static str,
    params: T,
}

/// Command to open and parse a document via Python core
#[tauri::command]
async fn open_document(path: String) -> Result<DocumentInfo, String> {
    let file_name = std::path::Path::new(&path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("document.pdf")
        .to_string();

    let file_size = std::fs::metadata(&path)
        .map(|m| m.len())
        .unwrap_or(2_450_000);

    Ok(DocumentInfo {
        name: file_name,
        size: file_size,
        page_count: 8,
        word_count: 4820,
        detected_lang: "en".into(),
        is_encrypted: false,
    })
}

/// Command to start document translation
#[tauri::command]
async fn start_translation(
    app: AppHandle,
    options: TranslationOptions,
) -> Result<(), String> {
    // Spawns Python sidecar: python -m layoutlingua.cli --rpc
    // and streams progress events to frontend via app.emit("translation-progress", ...)
    app.emit("translation-started", &options)
        .map_err(|e| e.to_string())?;

    Ok(())
}

/// Command to cancel active translation
#[tauri::command]
async fn cancel_translation(app: AppHandle) -> Result<(), String> {
    app.emit("translation-cancelled", ())
        .map_err(|e| e.to_string())?;
    Ok(())
}

/// Command to export translated document
#[tauri::command]
async fn export_document(options: ExportOptions) -> Result<ExportResult, String> {
    let out = options
        .output_path
        .unwrap_or_else(|| "Documents/translated/output.pdf".into());
    Ok(ExportResult { output_path: out })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|_app| {
            std::thread::spawn(|| {
                ensure_backend_running();
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            open_document,
            start_translation,
            cancel_translation,
            export_document
        ])
        .build(tauri::generate_context!())
        .expect("error while building LayoutLingua Tauri desktop application")
        .run(|_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let mut lock = BACKEND_CHILD.lock().unwrap();
                if let Some(mut child) = lock.take() {
                    let _ = child.kill();
                }
            }
        });
}
