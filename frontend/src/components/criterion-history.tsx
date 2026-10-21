import { useId } from "react";
import { t, useI18n } from "../lib/i18n";
import type { AcceptanceCriterion } from "../types";

export function CriterionRevisionComparison({
  revision,
  revisionNumber,
  code,
}: {
  revision: AcceptanceCriterion["revisions"][number];
  revisionNumber: number;
  code: string;
}) {
  useI18n();
  const captionId = useId();
  const fields = ["given", "when", "then"] as const;
  return (
    <>
      <div
        className="criterion-history-scroll"
        role="region"
        aria-labelledby={captionId}
        tabIndex={0}
      >
        <table className="criterion-history-table">
          <caption id={captionId} className="sr-only">
            {t("Comparación de la revisión {revision} de {code}", {
              revision: revisionNumber,
              code,
            })}
          </caption>
          <colgroup span={3} />
          <colgroup span={3} />
          <thead>
            <tr>
              <th scope="colgroup" colSpan={3}>
                {t("Anterior")}
              </th>
              <th scope="colgroup" colSpan={3}>
                {t("Revisado")}
              </th>
            </tr>
            <tr>
              {(["before", "after"] as const).flatMap((side) =>
                (["Dado", "Cuando", "Entonces"] as const).map((label) => (
                  <th scope="col" key={side + label}>
                    {t(label)}
                  </th>
                )),
              )}
            </tr>
          </thead>
          <tbody>
            <tr>
              {(["before", "after"] as const).flatMap((side) =>
                fields.map((field) => (
                  <td key={side + field}>{revision[side][field]}</td>
                )),
              )}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="criterion-history-hint">
        {t("Desplázate horizontalmente para comparar ambas versiones.")}
      </p>
    </>
  );
}
