import { t, useI18n, translateMessage, countLabel, number } from "../lib/i18n";
import { useEffect, useRef, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Download,
  FileText,
  Headphones,
  LoaderCircle,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
  Upload,
  Video,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import {
  Badge,
  ConfirmDelete,
  Empty,
  Loading,
  PageHeader,
  TextField,
  useAction,
  useData,
} from "../components/shared";
import { api, patch, post, remove } from "../lib/api";
import { bytes, date, label, time, actorLabel } from "../lib/utils";
import type {
  Analysis,
  AnalysisInput,
  Artifact,
  Job,
  Meeting,
  Segment,
  Transcript,
} from "../types";
import { CriterionActions } from "../components/criterion-actions";
import { RequirementTable } from "./requirements";

const active = (job: Job) =>
  ["running", "queued", "blocked"].includes(job.status);
function JobCard({ job }: { job: Job }) {
  useI18n();
  const action = useAction();
  return (
    <section className="job-card">
      <div className="job-card-heading">
        <span className="round-icon">
          {job.status === "running" ? (
            <LoaderCircle className="spin" size={20} />
          ) : (
            <Headphones size={20} />
          )}
        </span>
        <div>
          <h3>
            {job.kind === "transcribe"
              ? t("Transcripción local")
              : job.kind === "validate_upload"
                ? t("Validando grabación")
                : t("Análisis de requisitos")}
          </h3>
          <p>
            {label(job.stage)}{" "}
            {job.cancel_requested ? t("· Cancelación solicitada") : ""}
          </p>
        </div>
        <Badge value={job.status} />
      </div>
      {job.progress !== null && (
        <>
          <progress max={1} value={job.progress} />
          <small>
            {number(Math.round(job.progress * 100))}
            {t("% de audio o bloques completados")}
          </small>
        </>
      )}
      {job.progress === null && job.status === "running" && (
        <div className="indeterminate">
          <span />
        </div>
      )}
      {job.error && (
        <div className="error-box">{translateMessage(job.error)}</div>
      )}
      {active(job) && (
        <div className="job-card-actions">
          <Button
            size="sm"
            variant="outline"
            disabled={action.busy || job.cancel_requested}
            onClick={() =>
              void action.run(
                () => post("/jobs/" + job.id + "/cancel"),
                t("Cancelación solicitada"),
              )
            }
          >
            <Square size={13} />
            {t("Cancelar trabajo")}
          </Button>
        </div>
      )}
    </section>
  );
}

export function AnalysisButton({ meeting }: { meeting: Meeting }) {
  useI18n();
  const [open, setOpen] = useState(false);
  const input = useData<AnalysisInput>(
    "/meetings/" + meeting.id + "/analysis-input",
    false,
    open,
  );
  const [consent, setConsent] = useState(false);
  const action = useAction();
  const navigate = useNavigate();
  const blocked = meeting.jobs.find(
    (j) => j.status === "blocked" && j.kind === "analyze",
  );
  const pending = meeting.jobs.some((j) => active(j) && j.id !== blocked?.id);
  return (
    <>
      <Button
        disabled={!meeting.transcript_revision || pending}
        onClick={() => {
          setConsent(false);
          setOpen(true);
        }}
      >
        <Sparkles size={17} />
        {blocked ? t("Revisar y reanudar análisis") : t("Analizar requisitos")}
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={t("Revisa exactamente qué se analizará")}
        description={t(
          "Esta autorización aplica solo a la entrada que ves a continuación.",
        )}
      >
        {input.data ? (
          <div className="form-stack">
            <div className="notice">
              <ShieldCheck size={18} />
              <span>
                {input.data.snapshot.provider === "mock"
                  ? t("Proveedor Mock: simulación local, sin envío externo.")
                  : t(
                      "Se enviará únicamente este texto y contexto a ChatGPT mediante tu plan. El audio permanece local.",
                    )}
              </span>
            </div>
            <div className="inline-meta">
              <Badge value={input.data.snapshot.provider} />
              <span>
                {t("Modelo:") + " "}
                {input.data.snapshot.model ?? t("No seleccionado")}
              </span>
              <span>
                {t("Revisión") + " "}
                {input.data.snapshot.revision}
              </span>
            </div>
            <TextField label={t("Contexto y glosario")}>
              <textarea
                rows={3}
                readOnly
                value={
                  input.data.snapshot.context +
                  "\n" +
                  Object.entries(input.data.snapshot.glossary)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join("\n")
                }
              />
            </TextField>
            <TextField label={t("Transcripción revisada")}>
              <textarea
                rows={9}
                readOnly
                value={input.data.snapshot.segments
                  .map((s) => `[${time(s.start)}] ${s.text}`)
                  .join("\n")}
              />
            </TextField>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              {t(
                "Autorizo este análisis con la entrada y el proveedor indicados.",
              )}
            </label>
            <Button
              disabled={!consent || action.busy}
              onClick={() =>
                void action.run(async () => {
                  const path = blocked
                    ? "/jobs/" + blocked.id + "/retry"
                    : "/meetings/" + meeting.id + "/analyze";
                  await post(path, {
                    input_hash: input.data.input_hash,
                    consent,
                  });
                  setOpen(false);
                  navigate("/meetings/" + meeting.id);
                }, t("Análisis en cola"))
              }
            >
              <Sparkles size={16} />
              {t("Confirmar análisis")}
            </Button>
          </div>
        ) : (
          <Loading error={input.error} />
        )}
      </Dialog>
    </>
  );
}

export function MeetingPage() {
  useI18n();
  const { id } = useParams();
  const query = useData<Meeting>("/meetings/" + id, true);
  const action = useAction();
  const [file, setFile] = useState<File | null>(null);
  const navigate = useNavigate();
  if (!query.data) return <Loading error={query.error} />;
  const meeting = query.data;
  const latest = meeting.jobs[0];
  const busy = meeting.jobs.some(active);
  return (
    <>
      <PageHeader
        title={meeting.title}
        description={
          date(meeting.date) +
          " · " +
          label(meeting.profile) +
          " · " +
          (meeting.language ?? t("Idioma automático"))
        }
        actions={
          <>
            <Badge value={meeting.status} />
            <ConfirmDelete
              title={t("Eliminar reunión")}
              description={t(
                "Se eliminarán la grabación, transcripción, análisis, requisitos y exportaciones de esta reunión.",
              )}
              onConfirm={async () => {
                await remove("/meetings/" + id + "?confirm=true");
                navigate("/meetings");
              }}
            />
          </>
        }
      />
      <div className="pipeline">
        <div className="done">
          <span>1</span>
          {t("Grabación")}
        </div>
        <i />
        <div className={meeting.transcript_revision ? "done" : ""}>
          <span>2</span>
          {t("Transcripción")}
        </div>
        <i />
        <div className={meeting.active_analysis_id ? "done" : ""}>
          <span>3</span>
          {t("Análisis")}
        </div>
        <i />
        <div>
          <span>4</span>
          {t("Validación humana")}
        </div>
      </div>
      <div className="two-columns">
        <section className="panel padded">
          <div className="section-heading">
            <h2>{t("Grabación original")}</h2>
            <Video size={19} />
          </div>
          {meeting.media ? (
            <>
              <div className="file-card">
                <span className="round-icon">
                  <Video size={23} />
                </span>
                <div>
                  <strong>{meeting.media.original_name}</strong>
                  <small>
                    {time(meeting.media.duration)} · {bytes(meeting.media.size)}
                  </small>
                </div>
                <ConfirmDelete
                  title={t("Eliminar solo la grabación")}
                  description={t(
                    "La grabación se eliminará. Las transcripciones, análisis y evidencia textual se conservarán; ya no podrás reproducir el audio.",
                  )}
                  onConfirm={() =>
                    remove("/meetings/" + id + "/media?confirm=true")
                  }
                />
              </div>
              <p className="muted">
                {t(
                  "Tu grabación se conserva en un volumen local. No se envía a ChatGPT.",
                )}
              </p>
              {!meeting.transcript_revision && (
                <Button
                  disabled={busy || action.busy}
                  onClick={() =>
                    void action.run(
                      () => post("/meetings/" + id + "/transcribe"),
                      t("Transcripción en cola"),
                    )
                  }
                >
                  <Play size={16} />
                  {latest &&
                  ["failed", "interrupted", "cancelled"].includes(latest.status)
                    ? t("Reintentar transcripción")
                    : t("Iniciar transcripción")}
                </Button>
              )}
            </>
          ) : (
            <div className="form-stack">
              <p>
                {meeting.transcript_revision
                  ? t(
                      "La grabación fue eliminada. Su evidencia textual sigue disponible.",
                    )
                  : t("Carga la grabación para continuar.")}
              </p>
              {!meeting.transcript_revision && (
                <>
                  <input
                    aria-label={t("Adjuntar grabación")}
                    type="file"
                    accept=".mp4,.m4a,.mp3,.wav"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                  <Button
                    disabled={!file || action.busy}
                    onClick={() =>
                      void action.run(async () => {
                        const body = new FormData();
                        body.append("file", file!);
                        await api("/meetings/" + id + "/upload", {
                          method: "POST",
                          body,
                        });
                      }, t("Grabación cargada"))
                    }
                  >
                    <Upload size={16} />
                    {t("Cargar archivo")}
                  </Button>
                </>
              )}
            </div>
          )}
        </section>
        <section className="panel padded">
          <h2>{t("Continúa donde lo dejaste")}</h2>
          <p>
            {t(
              "Revisa la transcripción antes de solicitar el análisis. Las decisiones finales siempre son tuyas.",
            )}
          </p>
          <div className="form-stack">
            <Button variant="outline" asChild>
              <Link to={"/meetings/" + id + "/transcript"}>
                <FileText size={17} />
                {t("Abrir transcripción")}
                <ArrowRight size={16} />
              </Link>
            </Button>
            {meeting.transcript_revision > 0 && (
              <AnalysisButton meeting={meeting} />
            )}
            <Button variant="outline" asChild>
              <Link to={"/meetings/" + id + "/results"}>
                <Sparkles size={17} />
                {t("Resultados y exportaciones")}
                <ArrowRight size={16} />
              </Link>
            </Button>
          </div>
        </section>
      </div>
      {meeting.jobs.length > 0 && (
        <>
          <h2 className="section-spaced">{t("Historial de procesamiento")}</h2>
          <div className="job-list">
            {meeting.jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

type Draft = { revised_text: string; reviewed: boolean; doubtful: boolean };
export function TranscriptPage() {
  useI18n();
  const { id } = useParams();
  const [params] = useSearchParams();
  const query = useData<Transcript>("/meetings/" + id + "/transcript", true);
  const meeting = useData<Meeting>("/meetings/" + id, true);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [search, setSearch] = useState("");
  const [current, setCurrent] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  const action = useAction();
  const dirty = Object.keys(drafts).length > 0;
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const click = (e: MouseEvent) => {
      const anchor = (e.target as Element).closest("a");
      if (
        dirty &&
        anchor &&
        anchor.pathname !== location.pathname &&
        !window.confirm(
          t("Hay correcciones sin guardar. ¿Salir y descartarlas?"),
        )
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", guard);
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", guard);
      document.removeEventListener("click", click, true);
    };
  }, [dirty]);
  useEffect(() => {
    if (params.get("segment") && query.data) {
      const s = query.data.segments.find((s) => s.id === params.get("segment"));
      if (s) {
        document
          .getElementById("segment-" + s.id)
          ?.scrollIntoView({ block: "center" });
        if (video.current) video.current.currentTime = s.start;
      }
    }
  }, [params, query.data?.complete]);
  if (!query.data || !meeting.data)
    return <Loading error={query.error ?? meeting.error} />;
  const transcript = query.data;
  function draft(segment: Segment): Draft {
    return (
      drafts[segment.id] ?? {
        revised_text: segment.revised_text ?? segment.original_text,
        reviewed: segment.reviewed,
        doubtful: segment.doubtful,
      }
    );
  }
  function update(segment: Segment, value: Partial<Draft>) {
    setDrafts((old) => ({
      ...old,
      [segment.id]: { ...draft(segment), ...value },
    }));
  }
  async function save() {
    let revision = transcript.revision;
    for (const [segment_id, value] of Object.entries(drafts)) {
      const result = await patch<{ revision: number }>(
        "/transcript-segments/" + segment_id,
        { ...value, revision },
      );
      revision = result.revision;
      setDrafts((old) => {
        const next = { ...old };
        delete next[segment_id];
        return next;
      });
    }
    return revision;
  }
  const filtered = transcript.segments.filter((s) =>
    (draft(s).revised_text + " " + s.original_text)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        title={meeting.data.title}
        description={t(
          "Escucha, comprueba y corrige. El texto original permanece conservado.",
        )}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to={"/meetings/" + id}>
                <ArrowLeft size={16} />
                {t("Reunión")}
              </Link>
            </Button>
            <Button
              disabled={!dirty || action.busy}
              onClick={() => void action.run(save, t("Correcciones guardadas"))}
            >
              {dirty
                ? t("Guardar") +
                  " " +
                  countLabel("changes", Object.keys(drafts).length)
                : t("Cambios guardados")}
              <Check size={16} />
            </Button>
          </>
        }
      />
      <div className="transcript-layout">
        <aside className="player-panel panel padded">
          <h2>{t("Escucha el contexto")}</h2>
          {meeting.data.media ? (
            <video
              ref={video}
              controls
              preload="metadata"
              src={"/api/meetings/" + id + "/media"}
              onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
            />
          ) : (
            <div className="notice">
              {t("La grabación no está disponible.")}
            </div>
          )}
          <div className="player-time">
            {time(current)}{" "}
            <span>/ {time(meeting.data.media?.duration ?? 0)}</span>
          </div>
          <p>
            {t(
              "Selecciona una marca de tiempo para ir al audio de ese segmento.",
            )}
          </p>
          <div className="download-formats">
            {["txt", "json", "srt", "vtt"].map((format) => (
              <a
                key={format}
                href={
                  "/api/meetings/" +
                  id +
                  "/transcript/download?format=" +
                  format
                }
              >
                <Download size={13} />
                {format.toUpperCase()}
              </a>
            ))}
          </div>
          <div className="subtle-divider" />
          {transcript.complete && !dirty ? (
            <AnalysisButton meeting={meeting.data} />
          ) : (
            <p className="notice">
              {dirty
                ? t("Guarda los cambios antes de analizar.")
                : t(
                    "El análisis se habilitará cuando termine la transcripción.",
                  )}
            </p>
          )}
          <small>
            {t("Revisión") + " "}
            {transcript.revision} ·{" "}
            {countLabel("segments", transcript.segments.length)}
          </small>
        </aside>
        <section>
          <div className="toolbar">
            <div className="search-field">
              <Search size={16} />
              <input
                aria-label={t("Buscar en transcripción")}
                placeholder={t("Buscar en la transcripción…")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {dirty && (
              <span className="unsaved">{t("Cambios sin guardar")}</span>
            )}
          </div>
          {!transcript.segments.length ? (
            <Empty
              title={
                transcript.complete
                  ? t("No se detectó voz")
                  : t("La transcripción aparecerá aquí")
              }
              description={
                transcript.complete
                  ? t(
                      "La grabación no produjo segmentos de voz. Comprueba el audio original.",
                    )
                  : t(
                      "Inicia o espera la transcripción local desde la reunión.",
                    )
              }
            />
          ) : (
            <div className="segments">
              {filtered.map((segment) => {
                const value = draft(segment);
                return (
                  <article
                    id={"segment-" + segment.id}
                    key={segment.id}
                    className={
                      "segment panel " +
                      (current >= segment.start && current < segment.end
                        ? "segment-active "
                        : "") +
                      (value.doubtful ? "segment-doubtful" : "")
                    }
                  >
                    <div className="segment-header">
                      <button
                        className="timestamp"
                        disabled={!meeting.data?.media}
                        onClick={() => {
                          if (video.current) {
                            video.current.currentTime = segment.start;
                            void video.current.play().catch(() => {});
                          }
                        }}
                      >
                        <Play size={12} />
                        {time(segment.start)} – {time(segment.end)}
                      </button>
                      <div className="segment-checks">
                        <label>
                          <input
                            type="checkbox"
                            disabled={!transcript.complete}
                            checked={value.reviewed}
                            onChange={(e) =>
                              update(segment, { reviewed: e.target.checked })
                            }
                          />
                          {t("Revisado")}
                        </label>
                        <label>
                          <input
                            type="checkbox"
                            disabled={!transcript.complete}
                            checked={value.doubtful}
                            onChange={(e) =>
                              update(segment, { doubtful: e.target.checked })
                            }
                          />
                          {t("Por comprobar")}
                        </label>
                      </div>
                    </div>
                    <textarea
                      aria-label={
                        t("Texto del segmento") + " " + time(segment.start)
                      }
                      disabled={!transcript.complete}
                      value={value.revised_text}
                      rows={Math.min(
                        7,
                        Math.max(2, Math.ceil(value.revised_text.length / 95)),
                      )}
                      onChange={(e) =>
                        update(segment, {
                          revised_text: e.target.value,
                          reviewed: false,
                        })
                      }
                    />
                    {value.revised_text !== segment.original_text && (
                      <details>
                        <summary>{t("Ver texto original")}</summary>
                        <p>{segment.original_text}</p>
                      </details>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </>
  );
}

const resultTabs = [
  ["summary", "Resumen"],
  ["requirements", "Requisitos"],
  ["stories", "Historias"],
  ["criteria", "Criterios"],
  ["business_rules", "Reglas"],
  ["questions", "Preguntas"],
  ["processes", "Procesos"],
  ["conceptual_model", "Modelo conceptual"],
  ["backlog", "Backlog"],
];
export function ResultsPage() {
  useI18n();
  const { id } = useParams();
  const meeting = useData<Meeting>("/meetings/" + id, true);
  const query = useData<Analysis[]>("/meetings/" + id + "/analyses", true);
  const exports = useData<Artifact[]>("/meetings/" + id + "/exports");
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState("summary");
  const action = useAction();
  if (!query.data || !meeting.data)
    return <Loading error={query.error ?? meeting.error} />;
  const runs = query.data;
  const run =
    runs.find((r) => r.id === selected) ??
    runs.find((r) => r.active) ??
    runs[0];
  return (
    <>
      <PageHeader
        title={meeting.data.title}
        description={t(
          "Hallazgos con evidencia. Revisión y aprobación bajo tu control.",
        )}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to={"/meetings/" + id + "/transcript"}>
                <FileText size={16} />
                {t("Transcripción")}
              </Link>
            </Button>
            {run && (
              <Button
                disabled={!run.active || action.busy}
                onClick={() =>
                  void action.run(
                    () => post("/meetings/" + id + "/export"),
                    t("Paquete Markdown generado"),
                  )
                }
              >
                <Download size={16} />
                {t("Generar exportación")}
              </Button>
            )}
          </>
        }
      />
      {!run ? (
        <Empty
          title={t("Una buena especificación empieza por escuchar")}
          description={t(
            "Revisa la transcripción e inicia un análisis para obtener resultados estructurados.",
          )}
          action={
            <Button asChild>
              <Link to={"/meetings/" + id + "/transcript"}>
                {t("Revisar transcripción")}
                <ArrowRight size={16} />
              </Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="version-bar">
            <TextField label={t("Versión de análisis")}>
              <select
                value={run.id}
                onChange={(e) => setSelected(e.target.value)}
              >
                {runs.map((r, i) => (
                  <option key={r.id} value={r.id}>
                    {date(r.created_at)} · {r.id.slice(0, 8)} · {r.provider}
                    {r.active ? " " + t("· ACTIVA") : ""}
                    {" " + t("· versión") + " "}
                    {runs.length - i}
                  </option>
                ))}
              </select>
            </TextField>
            <span className="muted">
              {t("Transcripción · revisión") + " "}
              {run.input_snapshot.revision}
            </span>
            {!run.active && (
              <Button
                variant="outline"
                disabled={action.busy}
                onClick={() =>
                  void action.run(
                    () => post("/analysis-runs/" + run.id + "/activate"),
                    t("Versión activada"),
                  )
                }
              >
                {t("Usar esta versión")}
              </Button>
            )}
          </div>
          {run.provider === "mock" && (
            <div className="notice">
              {t(
                "SIMULACIÓN · Estos resultados permiten probar el flujo. No representan un análisis real de IA.",
              )}
            </div>
          )}
          <div className="tabs result-tabs">
            {resultTabs.map(([key, title]) => (
              <button
                key={key}
                className={tab === key ? "active" : ""}
                onClick={() => setTab(key)}
              >
                {translateMessage(title)}
                {key === "requirements" && (
                  <span className="tab-count">{run.requirements.length}</span>
                )}
              </button>
            ))}
          </div>
          <ResultContent run={run} tab={tab} />
          <section className="section-spaced">
            <h2>{t("Exportaciones conservadas")}</h2>
            <p className="muted">
              {t(
                "Cada paquete es una copia independiente de los datos revisados al momento de exportar.",
              )}
            </p>
            {exports.data?.length ? (
              <div className="panel">
                {exports.data.map((artifact) => (
                  <details className="artifact" key={artifact.id}>
                    <summary>
                      <span>
                        {date(artifact.created_at)} · {artifact.id.slice(0, 8)}
                      </span>
                      <a
                        onClick={(e) => e.stopPropagation()}
                        href={"/api/exports/" + artifact.id + "/download"}
                      >
                        <Download size={15} />
                        {t("Descargar ZIP")}
                      </a>
                    </summary>
                    <div className="artifact-files">
                      {artifact.files.map((file) => (
                        <a
                          key={file}
                          href={
                            "/api/exports/" +
                            artifact.id +
                            "/download?file=" +
                            encodeURIComponent(file)
                          }
                        >
                          {file}
                          <Download size={13} />
                        </a>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <p className="muted">{t("Todavía no hay exportaciones.")}</p>
            )}
          </section>
        </>
      )}
    </>
  );
}

function criterionStatus(status: string) {
  return status === "validated"
    ? t("Validado")
    : status === "rejected"
      ? t("Rechazado")
      : t("Pendiente de tu validación");
}

function ResultContent({ run, tab }: { run: Analysis; tab: string }) {
  useI18n();
  const result = run.original_result;
  const criteria: NonNullable<Analysis["criteria"]> =
    run.criteria ??
    result.criteria.map((criterion) => ({
      ...criterion,
      id: criterion.code,
      status: "pending_validation",
      revision: 0,
      original: criterion,
      revisions: [],
    }));
  const references = (codes: string[]) =>
    codes.map((code) => run.code_mapping?.[code] ?? code).join(", ");
  if (tab === "requirements")
    return <RequirementTable requirements={run.requirements} />;
  if (tab === "summary")
    return (
      <div className="summary-grid">
        {Object.entries(result.summary).map(([key, value]) => (
          <section
            className={
              "panel padded " + (key === "objective" ? "summary-objective" : "")
            }
            key={key}
          >
            <h3>{label(key)}</h3>
            {Array.isArray(value) ? (
              value.length ? (
                <ul>
                  {value.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">{t("Sin evidencia suficiente.")}</p>
              )
            ) : (
              <p className="preserve">
                {value || t("Sin evidencia suficiente.")}
              </p>
            )}
          </section>
        ))}
      </div>
    );
  if (tab === "stories")
    return (
      <div className="result-cards">
        {result.stories.map((story) => (
          <section className="panel padded" key={story.code}>
            <span className="code">{story.code}</span>
            <h3>{story.text}</h3>
            <p className="muted">
              {t("Requisitos de origen:") + " "}
              {references(story.requirements)}
            </p>
          </section>
        ))}
      </div>
    );
  if (tab === "criteria")
    return (
      <div className="result-cards">
        {criteria.map((c) => (
          <section className="panel padded" key={c.code}>
            <span className="code">
              {c.code} · {c.story_code}
            </span>
            <p>
              <span className={"badge badge-" + c.status}>
                {criterionStatus(c.status)}
              </span>
            </p>
            <CriterionActions
              criterion={c}
              active={run.active}
              references={references(c.requirements)}
            />
            <dl className="criterion">
              <dt>{t("Dado")}</dt>
              <dd>{c.given}</dd>
              <dt>{t("Cuando")}</dt>
              <dd>{c.when}</dd>
              <dt>{t("Entonces")}</dt>
              <dd>{c.then}</dd>
            </dl>
            <p className="muted">
              {t("Requisitos de origen:") + " "}
              {references(c.requirements)}
            </p>
            {c.revisions.length > 0 && (
              <>
                <details>
                  <summary>{t("Texto original generado")}</summary>
                  <dl className="criterion">
                    <dt>{t("Dado")}</dt>
                    <dd>{c.original.given}</dd>
                    <dt>{t("Cuando")}</dt>
                    <dd>{c.original.when}</dd>
                    <dt>{t("Entonces")}</dt>
                    <dd>{c.original.then}</dd>
                  </dl>
                </details>
                <details>
                  <summary>
                    {t("Historial de revisiones (")}
                    {c.revision})
                  </summary>
                  {c.revisions.map((revision, index) => (
                    <section key={index}>
                      <p>
                        {t("Revisión") + " "}
                        {index + 1} · {revision.created_at}
                      </p>
                      <p>{revision.observations}</p>
                      <p>{actorLabel(revision.actor)}</p>
                      <p>
                        {t("Estado anterior:")}{" "}
                        {criterionStatus(revision.before.status)}
                        {" " + t("· Estado posterior:") + " "}
                        {criterionStatus(revision.after.status)}
                      </p>
                      <dl className="criterion">
                        <dt>{t("Dado anterior")}</dt>
                        <dd>{revision.before.given}</dd>
                        <dt>{t("Cuando anterior")}</dt>
                        <dd>{revision.before.when}</dd>
                        <dt>{t("Entonces anterior")}</dt>
                        <dd>{revision.before.then}</dd>
                        <dt>{t("Dado revisado")}</dt>
                        <dd>{revision.after.given}</dd>
                        <dt>{t("Cuando revisado")}</dt>
                        <dd>{revision.after.when}</dd>
                        <dt>{t("Entonces revisado")}</dt>
                        <dd>{revision.after.then}</dd>
                      </dl>
                    </section>
                  ))}
                </details>
              </>
            )}
          </section>
        ))}
      </div>
    );
  if (tab === "backlog")
    return (
      <div className="panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>{t("MÓDULO")}</th>
              <th>{t("HISTORIA")}</th>
              <th>{t("REQUISITOS")}</th>
              <th>{t("PRIORIDAD")}</th>
              <th>{t("DEPENDENCIAS")}</th>
            </tr>
          </thead>
          <tbody>
            {result.backlog.map((item) => (
              <tr key={item.code}>
                <td className="code">{item.code}</td>
                <td>{item.module}</td>
                <td>{item.story_code}</td>
                <td>{references(item.requirements)}</td>
                <td>
                  <Badge value={item.priority} />
                </td>
                <td>{item.dependencies.join(", ") || t("No indicadas")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  const notes =
    result[
      tab as "business_rules" | "questions" | "processes" | "conceptual_model"
    ];
  return notes?.length ? (
    <div className="result-cards">
      {notes.map((note, i) => (
        <section className="panel padded" key={i}>
          <p className="preserve">{note.text}</p>
          {note.evidence.map((e, j) => (
            <blockquote key={j}>
              <p>“{e.quote}”</p>
              <small>
                {t("Segmento") + " "}
                {e.segment_id}
              </small>
            </blockquote>
          ))}
        </section>
      ))}
    </div>
  ) : (
    <Empty
      title={t("La evidencia marca el alcance")}
      description={t(
        "La reunión no aportó información suficiente para esta sección. No se completan vacíos con suposiciones.",
      )}
    />
  );
}
