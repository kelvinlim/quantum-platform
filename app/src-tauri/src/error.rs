use serde::Serialize;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("{0}")]
    Msg(String),
    #[error("sidecar is not running")]
    SidecarDown,
    #[error("sidecar RPC error: {0}")]
    Rpc(String),
    #[error(transparent)]
    Io(#[from] std::io::Error),
}

impl AppError {
    pub fn msg(text: impl Into<String>) -> Self {
        Self::Msg(text.into())
    }
}

impl Serialize for AppError {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(&self.to_string())
    }
}

pub type AppResult<T> = Result<T, AppError>;
