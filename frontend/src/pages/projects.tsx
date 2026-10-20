import { LocalizedForm } from "../components/localized-form";
import { t, useI18n, countLabel, number } from "../lib/i18n";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  FileCheck2,
  FolderKanban,
  Plus,
  Search,
  UploadCloud,
  Video,
  Waves,
  Pencil,
  Clock3,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import {
  Badge,
  ConfirmDelete,
  Empty,
  Loading,
  PageHeader,
  SectionTitle,
  TextField,
  useAction,
  useData,
} from "../components/shared";
import { api, patch, post, remove } from "../lib/api";
import { bytes, date, label, time } from "../lib/utils";
import type {
  DashboardData,
  Meeting,
  Preferences,
  Project,
  Requirement,
} from "../types";
import { RequirementTable } from "./requirements";

const projectSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Escribe un nombre")
    .max(200, "El texto no puede superar 200 caracteres."),
  description: z
    .string()
    .max(10000, "El texto no puede superar 10000 caracteres."),
  context: z.string().max(30000, "El texto no puede superar 30000 caracteres."),
  glossary_text: z.string(),
});
type ProjectForm = z.infer<typeof projectSchema>;
export function ProjectEditor({ project }: { project?: Project }) {
  useI18n();
  const [open, setOpen] = useState(false);
  const action = useAction();
  const navigate = useNavigate();
  const form = useForm<ProjectForm>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: project?.name ?? "",
      description: project?.description ?? "",
      context: project?.context ?? "",
      glossary_text: Object.entries(project?.glossary ?? {})
        .map(([k, v]) => `${k} = ${v}`)
        .join("\n"),
    },
  });
  async function submit(values: ProjectForm) {
    const glossary: Record<string, string> = {};
    for (const line of values.glossary_text
      .split("\n")
      .filter((x) => x.trim())) {
      const separator = line.indexOf("=");
      if (separator < 1)
        throw new Error(
          t("Usa un término = definición por línea en el glosario."),
        );
      glossary[line.slice(0, separator).trim()] = line
        .slice(separator + 1)
        .trim();
    }
    const body = {
      name: values.name,
      description: values.description,
      context: values.context,
      glossary,
    };
    const result = project
      ? await patch<Project>("/projects/" + project.id, body)
      : await post<Project>("/projects", body);
    setOpen(false);
    navigate("/projects/" + result.id);
    return result;
  }
  return (
    <>
      <Button
        variant={project ? "outline" : "default"}
        onClick={() => setOpen(true)}
      >
        {project ? <Pencil size={16} /> : <Plus size={16} />}{" "}
        {project ? t("Editar proyecto") : t("Nuevo proyecto")}
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={
          project ? t("Editar proyecto") : t("Un espacio para tus requisitos")
        }
        description={t(
          "El contexto y el glosario acompañarán únicamente los análisis que autorices.",
        )}
      >
        <LocalizedForm
          onSubmit={form.handleSubmit(
            (v) => void action.run(() => submit(v), t("Proyecto guardado")),
          )}
          className="form-stack"
        >
          <TextField
            label={t("Nombre del proyecto")}
            error={form.formState.errors.name?.message}
          >
            <input
              {...form.register("name")}
              placeholder={t("Ej. Portal de solicitudes")}
            />
          </TextField>
          <TextField
            label={t("Descripción")}
            error={form.formState.errors.description?.message}
          >
            <textarea {...form.register("description")} rows={2} />
          </TextField>
          <TextField
            label={t("Contexto de negocio")}
            error={form.formState.errors.context?.message}
          >
            <textarea
              {...form.register("context")}
              rows={3}
              placeholder={t("Objetivos, alcance y conocimientos relevantes…")}
            />
          </TextField>
          <TextField label={t("Glosario · término = definición")}>
            <textarea
              {...form.register("glossary_text")}
              rows={3}
              placeholder={t("CRM = Gestión de relaciones con clientes")}
            />
          </TextField>
          <Button disabled={action.busy}>{t("Guardar proyecto")}</Button>
        </LocalizedForm>
      </Dialog>
    </>
  );
}

export function Dashboard() {
  useI18n();
  const query = useData<DashboardData>("/dashboard", true);
  if (!query.data) return <Loading error={query.error} />;
  const data = query.data;
  return (
    <>
      <PageHeader
        title={t("Vista general")}
        description={t(
          "Transforma conversaciones en requisitos claros, revisables y conectados con su origen.",
        )}
      />
      <section className="overview-grid">
        <section className="intro-card" aria-labelledby="workflow-title">
          <h2 id="workflow-title">{t("De la grabación a los requisitos")}</h2>
          <ol className="workflow-list">
            <li>
              <UploadCloud size={20} />
              <div>
                <strong>{t("Carga y transcribe")}</strong>
                <p>{t("Procesa el audio en tu entorno, a tu ritmo.")}</p>
              </div>
            </li>
            <li>
              <Pencil size={20} />
              <div>
                <strong>{t("Revisa la conversación")}</strong>
                <p>{t("Corrige el texto y conserva siempre su original.")}</p>
              </div>
            </li>
            <li>
              <FileCheck2 size={20} />
              <div>
                <strong>{t("Analiza y valida")}</strong>
                <p>
                  {t(
                    "Autoriza el análisis y revisa cada hallazgo con su evidencia.",
                  )}
                </p>
              </div>
            </li>
          </ol>
          <Button asChild>
            <Link to="/meetings/new">
              {t("Procesar una reunión") + " "}
              <ArrowUpRight size={17} />
            </Link>
          </Button>
        </section>
        <div className="stats-grid">
          {[
            {
              Icon: FolderKanban,
              count: data.project_count,
              title: t("Proyectos activos"),
              caption: t("Contexto que se conserva"),
            },
            {
              Icon: Video,
              count: data.meeting_count,
              title: t("Reuniones registradas"),
              caption: t("Tu historial de conversaciones"),
            },
            {
              Icon: FileCheck2,
              count: data.pending_requirements,
              title: t("Por validar"),
              caption: t("Tu criterio cierra el ciclo"),
            },
            {
              Icon: Clock3,
              count: data.jobs.length,
              title: t("Trabajos pendientes"),
              caption: t("Procesamiento secuencial"),
            },
          ].map(({ Icon, count, title, caption }) => (
            <div
              className="stat-card"
              role="group"
              aria-label={title}
              key={title}
            >
              <Icon size={20} />
              <strong>{number(count)}</strong>
              <span>{title}</span>
              <small>{caption}</small>
            </div>
          ))}
        </div>
      </section>
      <SectionTitle title={t("Proyectos recientes")} to="/projects" />
      {data.projects.length ? (
        <div className="project-grid">
          {data.projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      ) : (
        <div className="panel">
          <Empty
            title={t("El primer proyecto empieza aquí")}
            description={t(
              "Agrupa reuniones, contexto de negocio y requisitos en un mismo lugar.",
            )}
            action={<ProjectEditor />}
          />
        </div>
      )}
      <SectionTitle title={t("En tu mesa de trabajo")} to="/meetings" />
      {data.jobs.length ? (
        <div className="panel">
          {data.jobs.map((job) => (
            <Link
              className="job-row"
              to={"/meetings/" + job.meeting_id}
              key={job.id}
            >
              <span className="round-icon">
                <Waves size={19} />
              </span>
              <div>
                <strong>
                  {job.kind === "transcribe"
                    ? t("Transcripción local")
                    : t("Análisis de requisitos")}
                </strong>
                <small>{label(job.stage)}</small>
              </div>
              <Badge value={job.status} />
              <ArrowRight size={17} />
            </Link>
          ))}
        </div>
      ) : (
        <div className="quiet-row">
          <span className="status-dot online" />
          {t("Todo en orden. No hay trabajos en cola.")}
          <span>{t("El procesamiento comienza cuando tú lo decides.")}</span>
        </div>
      )}
    </>
  );
}

function ProjectCard({ project }: { project: Project }) {
  useI18n();
  return (
    <Link to={"/projects/" + project.id} className="project-card">
      <div className="project-card-top">
        <span className="project-icon">
          <FolderKanban size={21} />
        </span>
        <ArrowUpRight size={18} />
      </div>
      <h3>{project.name}</h3>
      <p>
        {project.description ||
          t("Un nuevo espacio para organizar decisiones y requisitos.")}
      </p>
      <div className="project-card-footer">
        <span>
          {countLabel("glossary", Object.keys(project.glossary).length)}
        </span>
        <span>{date(project.updated_at)}</span>
      </div>
    </Link>
  );
}

export function Projects() {
  useI18n();
  const query = useData<Project[]>("/projects");
  const [search, setSearch] = useState("");
  return (
    <>
      <PageHeader
        title={t("Proyectos")}
        description={t(
          "El contexto de cada producto, reunido en un solo lugar.",
        )}
        actions={<ProjectEditor />}
      />
      <div className="toolbar">
        <div className="search-field">
          <Search size={17} />
          <input
            aria-label={t("Buscar proyecto")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("Buscar un proyecto…")}
          />
        </div>
        <span className="muted">
          {countLabel("projects", query.data?.length ?? 0)}
        </span>
      </div>
      {!query.data ? (
        <Loading error={query.error} />
      ) : query.data.length ? (
        <div className="project-grid">
          {query.data
            .filter((p) =>
              (p.name + " " + p.description)
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
        </div>
      ) : (
        <Empty
          title={t("Dale contexto a tus reuniones")}
          description={t("Crea un proyecto para comenzar.")}
          action={<ProjectEditor />}
        />
      )}
    </>
  );
}

export function MeetingTable({ meetings }: { meetings: Meeting[] }) {
  useI18n();
  return (
    <div className="panel table-scroll">
      <table>
        <thead>
          <tr>
            <th>{t("REUNIÓN")}</th>
            <th>{t("FECHA")}</th>
            <th>{t("GRABACIÓN")}</th>
            <th>{t("ESTADO")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {meetings.map((meeting) => (
            <tr key={meeting.id}>
              <td>
                <Link className="table-title" to={"/meetings/" + meeting.id}>
                  <span className="round-icon">
                    <Video size={17} />
                  </span>
                  {meeting.title}
                </Link>
              </td>
              <td>{date(meeting.date)}</td>
              <td>
                {meeting.media ? (
                  <>
                    <span>{time(meeting.media.duration)}</span>
                    <small>{bytes(meeting.media.size)}</small>
                  </>
                ) : (
                  t("Sin archivo")
                )}
              </td>
              <td>
                <Badge value={meeting.status} />
              </td>
              <td>
                <Link
                  className="icon-button"
                  aria-label={t("Abrir") + " " + meeting.title}
                  to={"/meetings/" + meeting.id}
                >
                  <ArrowUpRight size={18} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Meetings() {
  useI18n();
  const query = useData<Meeting[]>("/meetings", true);
  const [search, setSearch] = useState("");
  return (
    <>
      <PageHeader
        title={t("Reuniones")}
        description={t(
          "Del archivo original a decisiones que puedes rastrear.",
        )}
        actions={
          <Button asChild>
            <Link to="/meetings/new">
              <Plus size={16} />
              {t("Nueva reunión")}
            </Link>
          </Button>
        }
      />
      <div className="toolbar">
        <div className="search-field">
          <Search size={17} />
          <input
            aria-label={t("Buscar reunión")}
            placeholder={t("Buscar una reunión…")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      {!query.data ? (
        <Loading error={query.error} />
      ) : query.data.length ? (
        <MeetingTable
          meetings={query.data.filter((m) =>
            m.title.toLowerCase().includes(search.toLowerCase()),
          )}
        />
      ) : (
        <Empty
          title={t("Tu próxima conversación empieza aquí")}
          description={t(
            "Registra una reunión y selecciona una grabación para procesar.",
          )}
          action={
            <Button asChild>
              <Link to="/meetings/new">{t("Nueva reunión")}</Link>
            </Button>
          }
        />
      )}
    </>
  );
}

export function ProjectDetail() {
  useI18n();
  const { id } = useParams();
  const query = useData<Project>("/projects/" + id);
  const meetings = useData<Meeting[]>("/meetings?project_id=" + id, true);
  const requirements = useData<Requirement[]>(
    "/projects/" + id + "/requirements",
  );
  const [tab, setTab] = useState("meetings");
  const navigate = useNavigate();
  if (!query.data) return <Loading error={query.error} />;
  const project = query.data;
  return (
    <>
      <PageHeader
        title={project.name}
        description={project.description}
        actions={
          <>
            <ProjectEditor project={project} />
            <Button asChild>
              <Link to={"/meetings/new?project=" + id}>
                <Plus size={16} />
                {t("Añadir reunión")}
              </Link>
            </Button>
            <ConfirmDelete
              title={t("Eliminar proyecto")}
              description={t(
                "Se eliminarán todas sus reuniones, requisitos, versiones y archivos. Esta operación no se puede deshacer.",
              )}
              onConfirm={async () => {
                await remove("/projects/" + id + "?confirm=true");
                navigate("/projects");
              }}
            />
          </>
        }
      />
      <div className="tabs">
        {[
          ["meetings", t("Reuniones")],
          ["requirements", t("Requisitos")],
          ["context", t("Contexto y glosario")],
        ].map(([key, title]) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
          >
            {title}
          </button>
        ))}
      </div>
      {tab === "meetings" ? (
        meetings.data?.length ? (
          <MeetingTable meetings={meetings.data} />
        ) : (
          <Empty
            title={t("Un proyecto, muchas conversaciones")}
            description={t(
              "Añade la primera reunión para comenzar a capturar requisitos.",
            )}
          />
        )
      ) : tab === "requirements" ? (
        <RequirementTable requirements={requirements.data ?? []} />
      ) : (
        <div className="two-columns">
          <section className="panel padded">
            <h2>{t("Contexto de negocio")}</h2>
            <p className="preserve">
              {project.context || t("Añade contexto desde Editar proyecto.")}
            </p>
          </section>
          <section className="panel padded">
            <h2>{t("Glosario")}</h2>
            {Object.entries(project.glossary).map(([term, definition]) => (
              <div className="glossary-row" key={term}>
                <strong>{term}</strong>
                <p>{definition}</p>
              </div>
            ))}
            {!Object.keys(project.glossary).length && (
              <p className="muted">{t("No hay términos registrados.")}</p>
            )}
          </section>
        </div>
      )}
    </>
  );
}

const meetingSchema = z.object({
  project_id: z.string().min(1, "Selecciona un proyecto"),
  title: z
    .string()
    .trim()
    .min(1, "Escribe un título")
    .max(200, "El texto no puede superar 200 caracteres."),
  date: z.string().min(1, "Indica la fecha"),
  profile: z.enum(["economy", "balanced", "quality"]),
  language: z.string(),
});
type MeetingForm = z.infer<typeof meetingSchema>;
export function NewMeeting() {
  useI18n();
  const projects = useData<Project[]>("/projects");
  const preferences = useData<Preferences>("/settings");
  const [params] = useSearchParams();
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const action = useAction();
  const navigate = useNavigate();
  const form = useForm<MeetingForm>({
    resolver: zodResolver(meetingSchema),
    defaultValues: {
      project_id: params.get("project") ?? "",
      title: "",
      date: new Date().toLocaleDateString("en-CA"),
      profile: "balanced",
      language: "es",
    },
  });
  useEffect(() => {
    if (preferences.data) {
      form.setValue(
        "profile",
        preferences.data.profile as MeetingForm["profile"],
      );
      form.setValue("language", preferences.data.language ?? "auto");
    }
  }, [preferences.data, form]);
  const profile = form.watch("profile");
  async function submit(values: MeetingForm) {
    if (!file) throw new Error(t("Selecciona una grabación."));
    if (file.size > (preferences.data?.max_upload_bytes ?? 4294967296))
      throw new Error(t("El archivo excede el límite configurado."));
    const meeting = draft
      ? { id: draft }
      : await post<Meeting>("/meetings", {
          ...values,
          language: values.language === "auto" ? null : values.language,
        });
    setDraft(meeting.id);
    const body = new FormData();
    body.append("file", file);
    await api("/meetings/" + meeting.id + "/upload", { method: "POST", body });
    navigate("/meetings/" + meeting.id);
    return meeting;
  }
  return (
    <>
      <PageHeader
        title={t("Una nueva reunión")}
        description={t(
          "Selecciona la grabación y su contexto. El procesamiento comenzará solo cuando lo indiques.",
        )}
      />
      <div className="new-meeting-grid">
        <LocalizedForm
          className="panel padded form-stack"
          onSubmit={form.handleSubmit(
            (v) => void action.run(() => submit(v), t("Grabación cargada")),
          )}
        >
          <div className="section-number">
            01 <h2>{t("El contexto")}</h2>
          </div>
          <TextField
            label={t("Proyecto")}
            error={form.formState.errors.project_id?.message}
          >
            <select {...form.register("project_id")}>
              <option value="">{t("Seleccionar proyecto")}</option>
              {projects.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </TextField>
          {projects.data?.length === 0 && (
            <Link to="/projects">{t("Crea un proyecto para continuar →")}</Link>
          )}
          <div className="two-columns">
            <TextField
              label={t("Título")}
              error={form.formState.errors.title?.message}
            >
              <input
                {...form.register("title")}
                placeholder={t("Ej. Descubrimiento del portal")}
              />
            </TextField>
            <TextField
              label={t("Fecha")}
              error={form.formState.errors.date?.message}
            >
              <input type="date" {...form.register("date")} />
            </TextField>
          </div>
          <div className="section-number">
            02 <h2>{t("La grabación")}</h2>
          </div>
          <label className="upload-zone">
            <UploadCloud size={31} />
            <strong>{file ? file.name : t("Selecciona una grabación")}</strong>
            <span>
              {file
                ? bytes(file.size)
                : t("MP4, M4A, MP3 o WAV · hasta") +
                  " " +
                  bytes(preferences.data?.max_upload_bytes ?? 4294967296)}
            </span>
            <input
              aria-label={t("Grabación")}
              type="file"
              required={!draft}
              accept=".mp4,.m4a,.mp3,.wav"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <div className="section-number">
            03 <h2>{t("La transcripción")}</h2>
          </div>
          <div className="two-columns">
            <TextField label={t("Perfil de rendimiento")}>
              <select {...form.register("profile")}>
                <option value="economy">
                  {t("Económico · base · 2 hilos")}
                </option>
                <option value="balanced">
                  {t("Equilibrado · small · 3 hilos")}
                </option>
                <option value="quality">
                  {t("Calidad · medium · 3 hilos")}
                </option>
              </select>
            </TextField>
            <TextField label={t("Idioma")}>
              <select {...form.register("language")}>
                <option value="es">{t("Español")}</option>
                <option value="en">{t("Inglés")}</option>
                <option value="auto">{t("Detección automática")}</option>
              </select>
            </TextField>
          </div>
          {profile === "quality" && (
            <p className="notice">
              {t(
                "El modelo medium consume más memoria. Puede requerir aumentar WORKER_MEM_LIMIT antes de usarlo.",
              )}
            </p>
          )}
          {draft && (
            <p className="notice">
              {t(
                "La reunión ya está registrada. Si la carga falla puedes reintentar aquí o abrirla desde Reuniones.",
              )}
            </p>
          )}
          <Button disabled={action.busy}>
            {action.busy
              ? t("Enviando y validando grabación…")
              : t("Guardar reunión")}
            <ArrowRight size={17} />
          </Button>
        </LocalizedForm>
        <aside className="guide-card">
          <span className="round-icon">
            <Waves size={23} />
          </span>
          <h2>{t("Tú marcas el ritmo.")}</h2>
          <ol>
            <li>
              <strong>{t("Carga")}</strong>
              <p>{t("El archivo se valida y se guarda en tu equipo.")}</p>
            </li>
            <li>
              <strong>{t("Transcribe")}</strong>
              <p>{t("Inicia el procesamiento local cuando sea oportuno.")}</p>
            </li>
            <li>
              <strong>{t("Revisa y analiza")}</strong>
              <p>
                {t("Corrige el texto antes de autorizar su envío a ChatGPT.")}
              </p>
            </li>
          </ol>
          <div className="subtle-divider" />
          <p>
            {t(
              "Un solo trabajo pesado a la vez. Sin GPU dedicada y sin cambios automáticos en WSL2.",
            )}
          </p>
        </aside>
      </div>
    </>
  );
}
