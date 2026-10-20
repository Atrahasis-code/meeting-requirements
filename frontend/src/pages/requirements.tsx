import { t, useI18n, countLabel } from "../lib/i18n";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, ExternalLink, Pencil, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import {
  Badge,
  Empty,
  Loading,
  TextField,
  useAction,
  useData,
} from "../components/shared";
import { patch, post } from "../lib/api";
import { date, label, time } from "../lib/utils";
import type { Requirement } from "../types";

export function RequirementTable({
  requirements,
}: {
  requirements: Requirement[];
}) {
  useI18n();
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [module, setModule] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const filtered = requirements.filter(
    (r) =>
      (!status || r.status === status) &&
      (!priority || r.priority === priority) &&
      (!module || r.module === module),
  );
  return (
    <>
      <div className="toolbar">
        <div className="filter-group">
          <select
            aria-label={t("Filtrar estado")}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">{t("Todos los estados")}</option>
            {["detected", "unclear", "proposed", "validated", "rejected"].map(
              (v) => (
                <option key={v} value={v}>
                  {label(v)}
                </option>
              ),
            )}
          </select>
          <select
            aria-label={t("Filtrar prioridad")}
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          >
            <option value="">{t("Todas las prioridades")}</option>
            {["high", "medium", "low", "unspecified"].map((v) => (
              <option key={v} value={v}>
                {label(v)}
              </option>
            ))}
          </select>
          <select
            aria-label={t("Filtrar módulo")}
            value={module}
            onChange={(e) => setModule(e.target.value)}
          >
            <option value="">{t("Todos los módulos")}</option>
            {[...new Set(requirements.map((r) => r.module))].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </div>
        <span className="muted">
          {countLabel("requirements", filtered.length)}
        </span>
      </div>
      {requirements.length ? (
        <div className="panel table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("REQUISITO")}</th>
                <th>{t("MÓDULO")}</th>
                <th>{t("PRIORIDAD")}</th>
                <th>{t("ESTADO")}</th>
                <th>{t("EVIDENCIA")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id}>
                  <td>
                    <button
                      className="requirement-link"
                      onClick={() => setSelected(r.id)}
                    >
                      <span className="code">{r.code}</span>
                      <strong>{r.title}</strong>
                    </button>
                  </td>
                  <td>{r.module}</td>
                  <td>
                    <Badge value={r.priority} />
                  </td>
                  <td>
                    <Badge value={r.status} />
                  </td>
                  <td>{countLabel("references", r.evidence.length)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title={t("Requisitos con respaldo, no suposiciones")}
          description={t(
            "Aquí aparecerán los hallazgos del análisis activo. Cada uno conservará su evidencia y necesitará validación humana.",
          )}
        />
      )}
      {selected && (
        <RequirementEditor id={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

const schema = z.object({
  title: z.string().trim().min(1).max(300),
  description: z.string().trim().min(1).max(10000),
  observations: z.string().max(10000),
  priority: z.string(),
});
type Values = z.infer<typeof schema>;
function RequirementEditor({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  useI18n();
  const query = useData<Requirement>("/requirements/" + id);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={query.data?.code ?? t("Requisito")}
      description={t(
        "Revisa el alcance y su evidencia. La aprobación es siempre manual.",
      )}
    >
      {query.data ? (
        <RequirementForm key={query.data.id} requirement={query.data} />
      ) : (
        <Loading error={query.error} />
      )}
    </Dialog>
  );
}
function RequirementForm({ requirement: r }: { requirement: Requirement }) {
  useI18n();
  const action = useAction();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: r.title,
      description: r.description,
      observations: r.observations,
      priority: r.priority,
    },
  });
  return (
    <div className="form-stack">
      <div className="inline-meta">
        <Badge value={r.status} />
        <Badge value={r.interpretation} />
        <span>
          {r.actor} · {r.module}
        </span>
      </div>
      <form
        className="form-stack"
        onSubmit={form.handleSubmit(
          (v) =>
            void action.run(
              () => patch("/requirements/" + r.id, v),
              t("Cambios guardados"),
            ),
        )}
      >
        <TextField label={t("Título")}>
          <input {...form.register("title")} />
        </TextField>
        <TextField label={t("Descripción")}>
          <textarea rows={4} {...form.register("description")} />
        </TextField>
        <TextField label={t("Prioridad sugerida")}>
          <select {...form.register("priority")}>
            {["high", "medium", "low", "unspecified"].map((v) => (
              <option key={v} value={v}>
                {label(v)}
              </option>
            ))}
          </select>
        </TextField>
        <TextField label={t("Observaciones")}>
          <textarea rows={2} {...form.register("observations")} />
        </TextField>
        <Button variant="outline" disabled={action.busy}>
          <Pencil size={15} />
          {t("Guardar cambios")}
        </Button>
      </form>
      <h3>{t("Evidencia de la reunión")}</h3>
      {r.evidence.map((e) => (
        <blockquote key={e.id}>
          <p>“{e.quote}”</p>
          <Link
            to={
              "/meetings/" +
              r.meeting_id +
              "/transcript?segment=" +
              e.segment_id
            }
          >
            {time(e.start)} – {time(e.end)}
            <ExternalLink size={13} />
          </Link>
        </blockquote>
      ))}
      {r.questions.length > 0 && (
        <>
          <h3>{t("Preguntas pendientes")}</h3>
          <ul>
            {r.questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </>
      )}
      <details>
        <summary>{t("Texto generado inicialmente")}</summary>
        <p className="preserve">{r.original.description}</p>
      </details>
      <details>
        <summary>
          {t("Historial de modificaciones (")}
          {r.revisions?.length ?? 0})
        </summary>
        {r.revisions?.map((v) => (
          <div key={v.id} className="history-item">
            <strong>{date(v.created_at)}</strong>
            <p>{String(v.after.description ?? "")}</p>
            <small>
              {t("Estado:") + " "}
              {label(String(v.after.status ?? ""))}
            </small>
            <small>
              {t("Autor:")}{" "}
              {String(
                (v.after._actor as { label?: string } | undefined)?.label ??
                  t("Registro anterior sin identidad verificada"),
              )}
            </small>
          </div>
        ))}
      </details>
      <div className="dialog-actions">
        <Button
          variant="outline"
          disabled={action.busy}
          onClick={() =>
            void action.run(
              () =>
                post("/requirements/" + r.id + "/validate", {
                  status: "rejected",
                }),
              t("Requisito rechazado"),
            )
          }
        >
          <X size={15} />
          {t("Rechazar")}
        </Button>
        <Button
          disabled={action.busy}
          onClick={() =>
            void action.run(
              () =>
                post("/requirements/" + r.id + "/validate", {
                  status: "validated",
                }),
              t("Requisito validado manualmente"),
            )
          }
        >
          <Check size={16} />
          {t("Validar requisito")}
        </Button>
      </div>
    </div>
  );
}
