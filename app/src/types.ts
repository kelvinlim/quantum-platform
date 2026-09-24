export type DeviceState = {
  state?: string;
  backend?: string;
  platform_supported?: boolean;
  importable?: boolean;
  path?: string;
  samples?: number;
};

export type ChecklistItem = {
  id: string;
  text: string;
  checked: boolean;
};

export type Reminder = {
  text: string;
  when: string;
  at_s?: number;
  tone?: "info" | "warn" | "critical" | string;
};

export type StageView = {
  stage_id: string | null;
  label: string | null;
  kind: string | null;
  index: number;
  total: number;
  duration_s: number | null;
  remaining_s: number | null;
  elapsed_s: number;
  advance: string | null;
  end_signal: string | null;
  either_policy: string | null;
  button: "continue" | "end_phase" | "hidden";
  button_enabled: boolean;
  button_label: string | null;
  waiting_on_operator: boolean;
  timer_elapsed: boolean;
  paused: boolean;
  complete: boolean;
  checklist: ChecklistItem[];
  reminders: Reminder[];
  constraints: Record<string, boolean>;
  collect: Record<string, { enabled?: boolean; hz?: number } | boolean>;
  stimulus: {
    painting_id?: string;
    condition?: string;
    presentation?: string;
    cover?: string;
  } | null;
  trial_index: number | null;
  trial_count: number | null;
  block_label: string | null;
};

export type PlanStage = {
  id: string;
  label: string;
  kind: string;
  duration_s: number | null;
  advance: string;
  end_signal: string;
  block_label?: string | null;
  trial_index?: number | null;
  trial_count?: number | null;
};

export type SessionStartResult = {
  ok: boolean;
  session_dir: string;
  mock?: boolean;
  experiment_id?: string;
  plan?: {
    id: string;
    name: string;
    protocol_version?: string | null;
    stages: PlanStage[];
    resolved_order?: unknown[];
  };
  stage?: StageView;
};

export type StatusSnapshot = {
  sidecar: { ok: boolean; version: string; platform?: string };
  session: {
    active: boolean;
    participant_id: string;
    session_id: string;
    session_dir: string;
    mock?: boolean;
  } | null;
  stage: StageView | null;
  devices: Record<string, DeviceState>;
};

export type DoctorResult = {
  ok: boolean;
  sidecar_version: string;
  python: string;
  python_recommended?: string;
  platform: string;
  thermal_supported: boolean;
  notes: string[];
  sdks: Array<{
    name: string;
    import_name: string;
    importable: boolean;
    platform_supported: boolean;
    message: string;
  }>;
};

export type ExperimentInfo = {
  id: string;
  name: string;
  path: string;
};

export type EventLine = {
  name: string;
  ts: number;
  ts_ns?: number;
  stage_id?: string;
  label?: string;
  payload?: Record<string, unknown>;
};
