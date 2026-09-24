import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, isTauri } from "./api";
import type {
  DeviceState,
  DoctorResult,
  EventLine,
  ExperimentInfo,
  PlanStage,
  StageView,
  StatusSnapshot,
} from "./types";

function formatRemaining(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${m}:${r.toFixed(1).padStart(4, "0")}`;
}

function collectEnabled(collect: StageView["collect"] | undefined, key: string): boolean {
  if (!collect) return false;
  const spec = collect[key];
  if (typeof spec === "boolean") return spec;
  return Boolean(spec?.enabled);
}

function DeviceChip({ name, info }: { name: string; info?: DeviceState }) {
  const state = info?.state ?? (info?.platform_supported === false ? "unsupported" : "disconnected");
  return (
    <span className="chip" title={info?.backend ?? ""}>
      <span className={`dot ${state}`} />
      {name}
      {info?.platform_supported === false ? " (n/a)" : ""}
    </span>
  );
}

export default function App() {
  const tauri = isTauri();
  const [participant, setParticipant] = useState("P001");
  const [session, setSession] = useState("S001");
  const [experiments, setExperiments] = useState<ExperimentInfo[]>([]);
  const [experimentId, setExperimentId] = useState("painting_session_simplified");
  const [experimentPath, setExperimentPath] = useState<string | null>(null);
  const [mock, setMock] = useState(true);
  const [status, setStatus] = useState<StatusSnapshot | null>(null);
  const [plan, setPlan] = useState<PlanStage[]>([]);
  const [events, setEvents] = useState<EventLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [doctor, setDoctor] = useState<DoctorResult | null>(null);
  const [busy, setBusy] = useState(false);

  const stage = status?.stage ?? null;
  const devices = status?.devices ?? {};
  const active = Boolean(status?.session);

  const refresh = useCallback(async () => {
    if (!tauri) return;
    try {
      const snap = await api.status();
      setStatus(snap);
    } catch (err) {
      setError(String(err));
    }
  }, [tauri]);

  useEffect(() => {
    if (!tauri) return;
    let unsubs: Array<() => void> = [];
    (async () => {
      try {
        await api.startSidecar();
        setExperiments(await api.listExperiments());
        await refresh();
      } catch (err) {
        setError(String(err));
      }
      unsubs.push(
        await listen<EventLine>("sidecar-event", (ev) => {
          setEvents((prev) => [...prev.slice(-199), ev.payload]);
          void refresh();
        }),
      );
      unsubs.push(
        await listen<StageView>("stage-status", (ev) => {
          setStatus((prev) =>
            prev ? { ...prev, stage: ev.payload } : prev,
          );
        }),
      );
      unsubs.push(
        await listen<DeviceState & { device?: string }>("device-status", () => {
          void refresh();
        }),
      );
      unsubs.push(
        await listen<{ message?: string }>("sidecar-error", (ev) => {
          setError(ev.payload.message ?? JSON.stringify(ev.payload));
        }),
      );
    })();
    const timer = window.setInterval(() => void refresh(), 250);
    return () => {
      window.clearInterval(timer);
      unsubs.forEach((fn) => fn());
    };
  }, [refresh, tauri]);

  const onStart = async () => {
    setBusy(true);
    setError(null);
    setEvents([]);
    try {
      const result = await api.startSession({
        participantId: participant,
        sessionId: session,
        experimentId: experimentPath ? null : experimentId,
        experimentPath,
        mock,
      });
      setPlan(result.plan?.stages ?? []);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const onStop = async () => {
    setBusy(true);
    try {
      await api.stopSession();
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const onDoctor = async () => {
    try {
      setDoctor(await api.doctor());
    } catch (err) {
      setError(String(err));
    }
  };

  const onPhase = async () => {
    if (!stage) return;
    try {
      if (stage.button === "end_phase") await api.endPhase();
      else await api.advance();
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  };

  const onCheck = async (id: string, checked: boolean) => {
    try {
      await api.setChecklist(id, checked);
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  };

  const progress = useMemo(() => {
    if (!stage || stage.total === 0) return "";
    if (stage.trial_index && stage.trial_count) {
      return `${stage.block_label ?? "Trial"} ${stage.trial_index} / ${stage.trial_count}`;
    }
    return `Stage ${Math.min(stage.index + 1, stage.total)} / ${stage.total}`;
  }, [stage]);

  if (!tauri) {
    return (
      <div className="app">
        <div className="topbar">
          <div className="brand">Quantum Platform {__APP_VERSION__}</div>
        </div>
        <div className="col">
          <p className="note">
            This operator UI talks to the Rust host over Tauri IPC. Open it with
            {" "}
            <code>cd app && npm run tauri dev</code>
            . For a headless dry-run, use{" "}
            <code>qp run --config experiments/painting_session_simplified.yaml --mock --auto-press</code>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Quantum Platform {__APP_VERSION__}</div>
        <div className="devices">
          {["thermal", "rgb", "verity", "gaze"].map((name) => (
            <DeviceChip key={name} name={name} info={devices[name]} />
          ))}
        </div>
      </header>

      <div className="main">
        <aside className="col">
          <h2>Session</h2>
          <label htmlFor="participant">Participant</label>
          <input
            id="participant"
            value={participant}
            disabled={active}
            onChange={(e) => setParticipant(e.target.value)}
          />
          <label htmlFor="session">Session</label>
          <input
            id="session"
            value={session}
            disabled={active}
            onChange={(e) => setSession(e.target.value)}
          />
          <label htmlFor="experiment">Experiment</label>
          <select
            id="experiment"
            disabled={active}
            value={experimentId}
            onChange={(e) => {
              setExperimentId(e.target.value);
              setExperimentPath(null);
            }}
          >
            {experiments.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.name}
              </option>
            ))}
            {experiments.length === 0 ? (
              <option value="painting_session_simplified">painting_session_simplified</option>
            ) : null}
          </select>
          <div className="row">
            <button
              type="button"
              disabled={active}
              onClick={async () => {
                const path = await api.pickExperiment();
                if (path) setExperimentPath(path);
              }}
            >
              Open YAML…
            </button>
          </div>
          {experimentPath ? <p className="note">Using {experimentPath}</p> : null}
          <label>
            <input
              type="checkbox"
              checked={mock}
              disabled={active}
              onChange={(e) => setMock(e.target.checked)}
            />{" "}
            Mock devices (Phase 1 dry-run)
          </label>
          <div className="row">
            <button type="button" className="primary" disabled={active || busy} onClick={() => void onStart()}>
              Start
            </button>
            <button type="button" disabled={!active || busy} onClick={() => void onStop()}>
              Stop
            </button>
          </div>
          <div className="row">
            <button type="button" onClick={() => void onDoctor()}>
              Doctor
            </button>
            <button
              type="button"
              className="danger"
              disabled={!active}
              onClick={() => void api.abort("operator abort").then(refresh)}
            >
              Abort
            </button>
          </div>
          {status?.session?.session_dir ? (
            <p className="note">Writing {status.session.session_dir}</p>
          ) : null}
          {error ? <p className="err">{error}</p> : null}
          {doctor ? (
            <div className="note">
              <p>
                Python {doctor.python} on {doctor.platform}. Thermal supported:{" "}
                {doctor.thermal_supported ? "yes" : "no"}
              </p>
              <ul>
                {doctor.sdks.map((sdk) => (
                  <li key={sdk.name}>
                    {sdk.name}: {sdk.importable ? "importable" : "missing"}
                    {sdk.platform_supported ? "" : " (unsupported OS)"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>

        <section className="col">
          <div className="banner">
            <div className="note">{progress || "No session"}</div>
            <h1>{stage?.label ?? (active ? "Waiting" : "Armed when you press Start")}</h1>
            {stage?.stimulus?.painting_id ? (
              <div className="note">
                {stage.stimulus.painting_id}
                {stage.stimulus.condition ? ` · ${stage.stimulus.condition}` : ""}
              </div>
            ) : null}
            {stage?.duration_s != null ? (
              <div className="countdown">{formatRemaining(stage.remaining_s)}</div>
            ) : (
              <div className="waiting">{stage ? "Waiting on operator" : ""}</div>
            )}
            <div className="badges">
              {stage?.constraints.allow_nuc === false ? <span className="badge nuc">NO NUC</span> : null}
              {stage?.constraints.allow_talk === false ? <span className="badge talk">DO NOT TALK</span> : null}
              {stage?.constraints.allow_operator_in_fov === false ? (
                <span className="badge fov">STAY OUT OF FOV</span>
              ) : null}
              {(["thermal", "rgb", "verity", "gaze"] as const)
                .filter((k) => collectEnabled(stage?.collect, k))
                .map((k) => (
                  <span key={k} className="chip">
                    {k}
                  </span>
                ))}
            </div>
            {stage && stage.button !== "hidden" ? (
              <button
                type="button"
                className={`phase-btn ${stage.button === "end_phase" ? "end" : ""}`}
                disabled={!stage.button_enabled}
                onClick={() => void onPhase()}
              >
                {stage.button_label ?? (stage.button === "end_phase" ? "End phase" : "Continue / Next phase")}
              </button>
            ) : (
              <p className="note">Timer-owned stage — no operator press required.</p>
            )}
          </div>

          <div className="reminders">
            <h2>Reminders</h2>
            {(stage?.reminders ?? []).map((rem, i) => (
              <div key={`${rem.text}-${i}`} className={`reminder ${rem.tone ?? "info"}`}>
                {rem.text}
              </div>
            ))}
          </div>
          <div className="checklist">
            <h2>Checklist</h2>
            {(stage?.checklist ?? []).map((item) => (
              <div key={item.id} className="check-item">
                <label>
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={(e) => void onCheck(item.id, e.target.checked)}
                  />
                  {item.text}
                </label>
              </div>
            ))}
            {stage && stage.checklist.length === 0 ? <p className="note">No checklist for this stage.</p> : null}
          </div>
        </section>

        <aside className="col">
          <h2>Stages</h2>
          <ol className="stage-list">
            {(plan.length ? plan : []).map((item, i) => {
              const done = stage ? i < stage.index || stage.complete : false;
              const current = stage?.stage_id === item.id;
              return (
                <li key={item.id} className={current ? "current" : done ? "done" : ""}>
                  {item.label}
                  {item.trial_index && item.trial_count
                    ? ` (${item.trial_index}/${item.trial_count})`
                    : ""}
                </li>
              );
            })}
          </ol>
        </aside>
      </div>

      <div className="log">
        {events.length === 0 ? <div>events.jsonl will appear here</div> : null}
        {events.map((ev, i) => (
          <div key={`${ev.ts_ns ?? ev.ts}-${i}`}>
            {ev.ts.toFixed(3)} {ev.name}
            {ev.stage_id ? ` ${ev.stage_id}` : ""}
          </div>
        ))}
      </div>
    </div>
  );
}
