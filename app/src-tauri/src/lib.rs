mod commands;
mod error;
mod sidecar;

use sidecar::Sidecar;
use std::sync::Mutex;
use tauri::Manager;

pub struct AppState {
    pub sidecar: Mutex<Option<Sidecar>>,
    pub repo_root: std::path::PathBuf,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let repo_root = sidecar::discover_repo_root();
            let spawned = Sidecar::spawn(&repo_root, app.handle().clone()).ok();
            app.manage(AppState {
                sidecar: Mutex::new(spawned),
                repo_root,
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::sidecar_alive,
            commands::start_sidecar,
            commands::list_experiments,
            commands::pick_experiment_file,
            commands::status_get,
            commands::doctor_run,
            commands::session_start,
            commands::session_stop,
            commands::session_advance,
            commands::session_end_phase,
            commands::session_checklist_set,
            commands::session_abort,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
