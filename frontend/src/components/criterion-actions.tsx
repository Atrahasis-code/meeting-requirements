import { LocalizedForm } from "./localized-form";
import { t, useI18n, translateMessage } from "../lib/i18n";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api, patch, post } from "../lib/api";
import type { AcceptanceCriterion } from "../types";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { useData, TextField } from "./shared";

type Fields = {
  given: string;
  when: string;
  then: string;
  observations: string;
};
const values = (c: AcceptanceCriterion): Fields => ({
  given: c.given,
  when: c.when,
  then: c.then,
  observations: "",
});
export function CriterionActions({
  criterion,
  active,
  references,
}: {
  criterion: AcceptanceCriterion;
  active: boolean;
  references: string;
}) {
  useI18n();
  const [mode, setMode] = useState<"edit" | "validated" | "rejected" | null>(
    null,
  );
  const [base, setBase] = useState(criterion);
  const [draft, setDraft] = useState<Fields>(values(criterion));
  const [latest, setLatest] = useState<AcceptanceCriterion | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const cache = useQueryClient();
  const caps = useData<{ edit_criteria: boolean; review_criteria: boolean }>(
    "/capabilities",
  );
  const canEdit = caps.data?.edit_criteria ?? true;
  const canReview = caps.data?.review_criteria ?? true;
  const dirty = ["given", "when", "then"].some(
    (k) =>
      draft[k as keyof Fields].trim() !== base[k as "given" | "when" | "then"],
  );
  function open(next: typeof mode) {
    setBase(criterion);
    setDraft(values(criterion));
    setLatest(null);
    setError("");
    setMode(next);
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      if (mode === "edit")
        await patch("/criteria/" + base.id, {
          revision: base.revision,
          ...draft,
        });
      else
        await post("/criteria/" + base.id + "/validate", {
          revision: base.revision,
          status: mode,
          observations: draft.observations,
        });
      await cache.invalidateQueries();
      setMode(null);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : t("No se pudo guardar el criterio"),
      );
      if (e instanceof ApiError && e.status === 409) {
        try {
          setLatest(await api<AcceptanceCriterion>("/criteria/" + base.id));
        } catch {
          /* Keep the user's draft. */
        }
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="dialog-actions">
        <Button
          variant="outline"
          disabled={!active || !canEdit}
          onClick={() => open("edit")}
        >
          {t("Editar") + " "}
          {criterion.code}
        </Button>
        <Button
          disabled={!active || !canReview || criterion.status === "validated"}
          onClick={() => open("validated")}
        >
          {t("Validar") + " "}
          {criterion.code}
        </Button>
        <Button
          variant="outline"
          disabled={!active || !canReview || criterion.status === "rejected"}
          onClick={() => open("rejected")}
        >
          {t("Rechazar") + " "}
          {criterion.code}
        </Button>
      </div>
      {!active && (
        <p className="muted">
          {t("Activa esta versión para modificar sus criterios.")}
        </p>
      )}
      <Dialog
        open={mode !== null}
        onOpenChange={(v) => {
          if (!v && !busy) setMode(null);
        }}
        title={`${mode === "edit" ? t("Editar") : mode === "rejected" ? t("Rechazar") : t("Validar")} ${base.code}`}
        description={t(
          "Revisión {revision}. Esta decisión es independiente de los requisitos RF/RN.",
          { revision: base.revision },
        )}
      >
        <LocalizedForm
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <p>
            {t("Requisitos relacionados:") + " "}
            {references}
          </p>
          {mode === "edit" ? (
            (
              Object.entries({
                given: t("Dado"),
                when: t("Cuando"),
                then: t("Entonces"),
              }) as ["given" | "when" | "then", string][]
            ).map(([key, label]) => (
              <TextField key={key} label={label}>
                <textarea
                  required
                  maxLength={10000}
                  value={draft[key]}
                  onChange={(e) =>
                    setDraft({ ...draft, [key]: e.target.value })
                  }
                />
              </TextField>
            ))
          ) : (
            <dl className="criterion">
              <dt>{t("Dado")}</dt>
              <dd>{base.given}</dd>
              <dt>{t("Cuando")}</dt>
              <dd>{base.when}</dd>
              <dt>{t("Entonces")}</dt>
              <dd>{base.then}</dd>
            </dl>
          )}
          <TextField
            label={
              mode === "rejected"
                ? t("Motivo del rechazo (obligatorio)")
                : t("Observaciones")
            }
          >
            <textarea
              required={mode === "rejected"}
              maxLength={10000}
              value={draft.observations}
              onChange={(e) =>
                setDraft({ ...draft, observations: e.target.value })
              }
            />
          </TextField>
          <details>
            <summary>{t("Original generado")}</summary>
            <dl className="criterion">
              <dt>{t("Dado")}</dt>
              <dd>{base.original.given}</dd>
              <dt>{t("Cuando")}</dt>
              <dd>{base.original.when}</dd>
              <dt>{t("Entonces")}</dt>
              <dd>{base.original.then}</dd>
            </dl>
          </details>
          {mode === "edit" && (
            <p>
              {t("Guardar un cambio deja el criterio pendiente de validación.")}
            </p>
          )}
          {error && <p role="alert">{translateMessage(error)}</p>}
          {latest && (
            <section>
              <h3>
                {t("Versión vigente · revisión") + " "}
                {latest.revision}
              </h3>
              <p>{latest.given}</p>
              <p>{latest.when}</p>
              <p>{latest.then}</p>
              <p>
                {t(
                  "Tu borrador permanece en el formulario. Cargar la revisión vigente lo sustituirá.",
                )}
              </p>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setBase(latest);
                  setDraft(values(latest));
                  setLatest(null);
                  setError("");
                }}
              >
                {t("Cargar revisión vigente")}
              </Button>
            </section>
          )}
          <div className="dialog-actions">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => setMode(null)}
            >
              {t("Cancelar")}
            </Button>
            <Button
              type="submit"
              disabled={
                busy ||
                !!latest ||
                (mode === "edit" &&
                  (!dirty ||
                    ![draft.given, draft.when, draft.then].every((v) =>
                      v.trim(),
                    ))) ||
                (mode === "rejected" && !draft.observations.trim())
              }
            >
              {busy
                ? t("Guardando…")
                : mode === "edit"
                  ? t("Guardar revisión")
                  : mode === "rejected"
                    ? t("Confirmar rechazo")
                    : t("Confirmar validación")}
            </Button>
          </div>
        </LocalizedForm>
      </Dialog>
    </>
  );
}
