use crate::error::{AppError, AppResult};
use crate::sidecar::Sidecar;
use crate::AppState;
use serde::Serialize;
use serde_json::{json, Value};
use std::fs;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;

#[derive(Debug, Serialize)]
pub struct ExperimentInfo {
    pub id: String,
    pub name: String,
    pub path: String,
}

fn sidecar(state: &State<AppState>) -> AppResult<Sidecar> {
    let guard = state
        .sidecar
        .lock()
        .map_err(|_| AppError::msg("sidecar lock poisoned"))?;
    guard.clone().ok_or(AppError::SidecarDown)
}

#[tauri::command]
pub fn sidecar_alive(state: State<AppState>) -> bool {
    sidecar(&state).map(|s| s.is_alive()).unwrap_or(false)
}

#[tauri::command]
pub fn start_sidecar(state: State<AppState>, app: AppHandle) -> AppResult<bool> {
    {
        let guard = state
            .sidecar
            .lock()
            .map_err(|_| AppError::msg("sidecar lock poisoned"))?;
        if let Some(existing) = guard.as_ref() {
            if existing.is_alive() {
                return Ok(true);
            }
        }
    }
    let handle = Sidecar::spawn(&state.repo_root, app)?;
    let mut guard = state
        .sidecar
        .lock()
        .map_err(|_| AppError::msg("sidecar lock poisoned"))?;
    *guard = Some(handle);
    Ok(true)
}

#[tauri::command]
pub fn list_experiments(state: State<AppState>) -> AppResult<Vec<ExperimentInfo>> {
    let dir = state.repo_root.join("experiments");
    let mut out = Vec::new();
    if !dir.is_dir() {
        return Ok(out);
    }
    let mut entries: Vec<_> = fs::read_dir(&dir)?.filter_map(|e| e.ok()).collect();
    entries.sort_by_key(|e| e.file_name());
    for entry in entries {
        let path = entry.path();
        let ext = path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or_default()
            .to_ascii_lowercase();
        if !matches!(ext.as_str(), "yaml" | "yml" | "json") {
            continue;
        }
        let text = fs::read_to_string(&path).unwrap_or_default();
        let id = parse_yaml_scalar(&text, "id").unwrap_or_else(|| {
            path.file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("unknown")
                .to_string()
        });
        let name = parse_yaml_scalar(&text, "name").unwrap_or_else(|| id.clone());
        out.push(ExperimentInfo {
            id,
            name,
            path: path.display().to_string(),
        });
    }
    Ok(out)
}

#[tauri::command]
pub fn pick_experiment_file(app: AppHandle) -> AppResult<Option<String>> {
    let (tx, rx) = std::sync::mpsc::channel();
    app.dialog()
        .file()
        .add_filter("Experiment", &["yaml", "yml", "json"])
        .pick_file(move |file| {
            let path = file.map(|f| f.to_string());
            let _ = tx.send(path);
        });
    Ok(rx.recv().ok().flatten())
}

#[tauri::command]
pub fn status_get(state: State<AppState>) -> AppResult<Value> {
    sidecar(&state)?.request("status.get", json!({}))
}

#[tauri::command]
pub fn doctor_run(state: State<AppState>) -> AppResult<Value> {
    sidecar(&state)?.request("doctor.run", json!({}))
}

#[tauri::command]
pub fn session_start(
    state: State<AppState>,
    participant_id: String,
    session_id: String,
    experiment_id: Option<String>,
    experiment_path: Option<String>,
    mock: Option<bool>,
) -> AppResult<Value> {
    let mut params = json!({
        "participant_id": participant_id,
        "session_id": session_id,
        "mock": mock.unwrap_or(true),
        "sessions_root": state.repo_root.join("sessions").to_string_lossy(),
    });
    if let Some(path) = experiment_path.filter(|s| !s.is_empty()) {
        params["experiment_path"] = json!(path);
    } else if let Some(id) = experiment_id.filter(|s| !s.is_empty()) {
        params["experiment_id"] = json!(id);
    }
    sidecar(&state)?.request("session.start", params)
}

#[tauri::command]
pub fn session_stop(state: State<AppState>) -> AppResult<Value> {
    sidecar(&state)?.request("session.stop", json!({}))
}

#[tauri::command]
pub fn session_advance(state: State<AppState>) -> AppResult<Value> {
    sidecar(&state)?.request("session.advance", json!({}))
}

#[tauri::command]
pub fn session_end_phase(state: State<AppState>) -> AppResult<Value> {
    sidecar(&state)?.request("session.end_phase", json!({}))
}

#[tauri::command]
pub fn session_checklist_set(
    state: State<AppState>,
    item_id: String,
    checked: bool,
) -> AppResult<Value> {
    sidecar(&state)?.request(
        "session.checklist_set",
        json!({"item_id": item_id, "checked": checked}),
    )
}

#[tauri::command]
pub fn session_abort(state: State<AppState>, reason: Option<String>) -> AppResult<Value> {
    sidecar(&state)?.request(
        "session.abort",
        json!({"reason": reason.unwrap_or_else(|| "operator abort".into())}),
    )
}

fn parse_yaml_scalar(text: &str, key: &str) -> Option<String> {
    let prefix = format!("{key}:");
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix(&prefix) {
            let value = rest.trim().trim_matches('"').trim_matches('\'');
            if !value.is_empty() {
                return Some(value.to_string());
            }
        }
    }
    None
}
