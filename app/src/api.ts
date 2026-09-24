import { invoke } from "@tauri-apps/api/core";
import type {
  DoctorResult,
  ExperimentInfo,
  SessionStartResult,
  StatusSnapshot,
} from "./types";

export const isTauri = () =>
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

export const api = {
  sidecarAlive: () => invoke<boolean>("sidecar_alive"),
  startSidecar: () => invoke<boolean>("start_sidecar"),
  listExperiments: () => invoke<ExperimentInfo[]>("list_experiments"),
  pickExperiment: () => invoke<string | null>("pick_experiment_file"),
  status: () => invoke<StatusSnapshot>("status_get"),
  doctor: () => invoke<DoctorResult>("doctor_run"),
  startSession: (params: {
    participantId: string;
    sessionId: string;
    experimentId?: string | null;
    experimentPath?: string | null;
    mock?: boolean;
  }) =>
    invoke<SessionStartResult>("session_start", {
      participantId: params.participantId,
      sessionId: params.sessionId,
      experimentId: params.experimentId ?? null,
      experimentPath: params.experimentPath ?? null,
      mock: params.mock ?? true,
    }),
  stopSession: () => invoke<{ ok: boolean; session_dir: string; session_status: string }>(
    "session_stop",
  ),
  advance: () => invoke<{ ok: boolean; stage: unknown; complete: boolean }>("session_advance"),
  endPhase: () => invoke<{ ok: boolean; stage: unknown; complete: boolean }>("session_end_phase"),
  setChecklist: (itemId: string, checked: boolean) =>
    invoke<{ ok: boolean; stage: unknown }>("session_checklist_set", { itemId, checked }),
  abort: (reason: string) => invoke<unknown>("session_abort", { reason }),
};
