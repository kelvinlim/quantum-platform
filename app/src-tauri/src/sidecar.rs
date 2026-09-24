use crate::error::{AppError, AppResult};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Emitter};

struct Pending {
    tx: Sender<Value>,
}

struct Inner {
    child: Child,
    stdin: ChildStdin,
    next_id: u64,
    pending: HashMap<u64, Pending>,
}

#[derive(Clone)]
pub struct Sidecar {
    inner: Arc<Mutex<Inner>>,
}

impl Sidecar {
    pub fn spawn(repo_root: &Path, app: AppHandle) -> AppResult<Self> {
        let python = find_python(repo_root)?;
        let src = repo_root.join("src");
        let mut cmd = Command::new(&python);
        cmd.args(["-m", "quantum_platform", "serve"])
            .current_dir(repo_root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONPATH", pythonpath_with(&src));

        let mut child = cmd.spawn().map_err(|err| {
            AppError::msg(format!(
                "failed to spawn sidecar ({python}): {err}",
                python = python.display()
            ))
        })?;
        let stdin = child.stdin.take().ok_or_else(|| AppError::msg("sidecar stdin missing"))?;
        let stdout = child.stdout.take().ok_or_else(|| AppError::msg("sidecar stdout missing"))?;
        let stderr = child.stderr.take().ok_or_else(|| AppError::msg("sidecar stderr missing"))?;

        let inner = Arc::new(Mutex::new(Inner {
            child,
            stdin,
            next_id: 1,
            pending: HashMap::new(),
        }));

        let reader_inner = inner.clone();
        let reader_app = app.clone();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                let Ok(line) = line else { break };
                if line.trim().is_empty() {
                    continue;
                }
                match serde_json::from_str::<Value>(&line) {
                    Ok(msg) => dispatch_line(&reader_inner, &reader_app, msg),
                    Err(err) => {
                        let _ = reader_app.emit(
                            "sidecar-error",
                            json!({"code": "bad_ndjson", "message": err.to_string(), "line": line}),
                        );
                    }
                }
            }
        });

        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(line) = line {
                    if !line.trim().is_empty() {
                        eprintln!("[sidecar] {line}");
                    }
                }
            }
        });

        Ok(Self { inner })
    }

    pub fn request(&self, method: &str, params: Value) -> AppResult<Value> {
        let (id, rx) = {
            let mut inner = self.inner.lock().map_err(|_| AppError::msg("sidecar lock poisoned"))?;
            let id = inner.next_id;
            inner.next_id += 1;
            let (tx, rx) = mpsc::channel();
            inner.pending.insert(id, Pending { tx });
            let msg = json!({
                "jsonrpc": "2.0",
                "id": id,
                "method": method,
                "params": params,
            });
            let line = serde_json::to_string(&msg).map_err(|e| AppError::msg(e.to_string()))?;
            inner
                .stdin
                .write_all(line.as_bytes())
                .and_then(|_| inner.stdin.write_all(b"\n"))
                .and_then(|_| inner.stdin.flush())
                .map_err(|e| AppError::msg(format!("sidecar stdin write failed: {e}")))?;
            (id, rx)
        };
        match rx.recv_timeout(Duration::from_secs(30)) {
            Ok(value) => {
                if let Some(err) = value.get("error") {
                    let message = err
                        .get("message")
                        .and_then(Value::as_str)
                        .unwrap_or("sidecar error");
                    return Err(AppError::Rpc(message.to_string()));
                }
                Ok(value.get("result").cloned().unwrap_or(Value::Null))
            }
            Err(_) => {
                if let Ok(mut inner) = self.inner.lock() {
                    inner.pending.remove(&id);
                }
                Err(AppError::msg(format!("timed out waiting for {method}")))
            }
        }
    }

    pub fn is_alive(&self) -> bool {
        match self.inner.lock() {
            Ok(mut inner) => inner.child.try_wait().ok().flatten().is_none(),
            Err(_) => false,
        }
    }
}

fn dispatch_line(inner: &Arc<Mutex<Inner>>, app: &AppHandle, msg: Value) {
    if let Some(id) = msg.get("id").and_then(Value::as_u64) {
        if let Ok(mut guard) = inner.lock() {
            if let Some(pending) = guard.pending.remove(&id) {
                let _ = pending.tx.send(msg);
                return;
            }
        }
    }
    let method = msg.get("method").and_then(Value::as_str).unwrap_or("");
    let params = msg.get("params").cloned().unwrap_or(Value::Null);
    let event = match method {
        "event.emit" => "sidecar-event",
        "device.status" => "device-status",
        "error" => "sidecar-error",
        "stage.status" => "stage-status",
        "stage.reminder" => "stage-reminder",
        _ => "sidecar-notification",
    };
    let _ = app.emit(event, params);
}

pub fn discover_repo_root() -> PathBuf {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    // app/src-tauri → repo root
    let from_manifest = manifest.join("../..");
    if from_manifest.join("experiments").is_dir() || from_manifest.join("src/quantum_platform").is_dir()
    {
        return from_manifest.canonicalize().unwrap_or(from_manifest);
    }
    if let Ok(cwd) = std::env::current_dir() {
        if cwd.join("experiments").is_dir() {
            return cwd;
        }
        if cwd.join("../experiments").is_dir() {
            return cwd.join("..").canonicalize().unwrap_or(cwd.join(".."));
        }
    }
    from_manifest
}

fn find_python(repo_root: &Path) -> AppResult<PathBuf> {
    if let Ok(path) = std::env::var("QUANTUM_PLATFORM_PYTHON") {
        return Ok(PathBuf::from(path));
    }
    for candidate in venv_python_candidates(repo_root) {
        if candidate.is_file() {
            return Ok(candidate);
        }
    }
    which::which("python3")
        .or_else(|_| which::which("python"))
        .map_err(|_| {
            AppError::msg(
                "python3 not found; create a repo .venv or set QUANTUM_PLATFORM_PYTHON",
            )
        })
}

fn venv_python_candidates(repo_root: &Path) -> Vec<PathBuf> {
    let venv = repo_root.join(".venv");
    if cfg!(windows) {
        vec![
            venv.join("Scripts").join("python.exe"),
            venv.join("Scripts").join("python3.exe"),
        ]
    } else {
        vec![
            venv.join("bin").join("python"),
            venv.join("bin").join("python3"),
        ]
    }
}

fn pythonpath_with(src: &Path) -> String {
    let extra = src.display().to_string();
    match std::env::var("PYTHONPATH") {
        Ok(existing) if !existing.is_empty() => format!("{extra}{sep}{existing}", sep = path_sep()),
        _ => extra,
    }
}

fn path_sep() -> &'static str {
    if cfg!(windows) {
        ";"
    } else {
        ":"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn venv_candidates_match_platform_layout() {
        let root = PathBuf::from("/repo");
        let candidates = venv_python_candidates(&root);
        let rendered: Vec<String> = candidates.iter().map(|p| p.to_string_lossy().replace('\\', "/")).collect();
        if cfg!(windows) {
            assert!(rendered.iter().any(|p| p.ends_with(".venv/Scripts/python.exe")));
        } else {
            assert!(rendered.iter().any(|p| p.ends_with(".venv/bin/python")));
        }
    }
}
