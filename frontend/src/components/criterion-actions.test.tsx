import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CriterionActions } from "./criterion-actions";
import type { AcceptanceCriterion } from "../types";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const criterion: AcceptanceCriterion = {
  id: "criterion",
  code: "CA-001",
  story_code: "HU-001",
  given: "Dado original",
  when: "Cuando original",
  then: "Entonces original",
  requirements: ["RF-001"],
  status: "validated",
  revision: 2,
  original: {
    code: "CA-001",
    story_code: "HU-001",
    given: "Dado original",
    when: "Cuando original",
    then: "Entonces original",
    requirements: ["RF-001"],
  },
  revisions: [],
};
function mount(active = true) {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <CriterionActions
        criterion={criterion}
        active={active}
        references="RF-002"
      />
    </QueryClientProvider>,
  );
}
it("cancels edits without submitting and requires a rejection reason", async () => {
  const fetcher = vi.fn(async (_input: unknown, _options?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () => ({ edit_criteria: true, review_criteria: true }),
  }));
  vi.stubGlobal("fetch", fetcher);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Editar CA-001" }));
  expect(
    screen.getByRole("button", { name: "Guardar revisión" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Entonces"), {
    target: { value: "Resultado revisado" },
  });
  expect(
    screen.getByRole("button", { name: "Guardar revisión" }),
  ).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(
    fetcher.mock.calls.every(
      (call) => call.length === 1 || !(call[1] as RequestInit)?.method,
    ),
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Rechazar CA-001" }));
  expect(
    screen.getByRole("button", { name: "Confirmar rechazo" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Motivo del rechazo (obligatorio)"), {
    target: { value: "Falta precisar el resultado" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar rechazo" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  const calls = fetcher.mock.calls as unknown as [string, RequestInit][];
  const body = JSON.parse(
    calls.find((call) => call[0].endsWith("/validate"))![1].body as string,
  );
  expect(body).toEqual({
    revision: 2,
    status: "rejected",
    observations: "Falta precisar el resultado",
  });
});
it("keeps the draft and modal open after a conflict", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: unknown, options?: RequestInit) => ({
      ok: !(options as RequestInit)?.method,
      status: (options as RequestInit)?.method ? 409 : 200,
      json: async () =>
        (options as RequestInit)?.method
          ? { detail: "El criterio cambió" }
          : String(input).endsWith("/capabilities")
            ? { edit_criteria: true, review_criteria: true }
            : { ...criterion, revision: 3, then: "Versión vigente" },
    })),
  );
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Editar CA-001" }));
  fireEvent.change(screen.getByLabelText("Entonces"), {
    target: { value: "Mi borrador" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Guardar revisión" }));
  await screen.findByText("Versión vigente");
  expect(screen.getByLabelText("Entonces")).toHaveValue("Mi borrador");
  expect(screen.getByRole("dialog")).toBeVisible();
  fireEvent.click(
    screen.getByRole("button", { name: "Cargar revisión vigente" }),
  );
  expect(screen.getByLabelText("Entonces")).toHaveValue("Versión vigente");
});
it("historical criteria are read only", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: unknown, _options?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => ({ edit_criteria: true, review_criteria: true }),
    })),
  );
  mount(false);
  expect(screen.getByRole("button", { name: "Editar CA-001" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Rechazar CA-001" }),
  ).toBeDisabled();
});
it("renders adversarial criterion text without executing markup", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ edit_criteria: true, review_criteria: true }),
    })),
  );
  const bad = {
    ...criterion,
    given: '<img src="https://attacker.invalid" onerror="fetch(\"/auth\")">',
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CriterionActions criterion={bad} active references="RF-002" />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Rechazar CA-001" }));
  expect(screen.getByText(bad.given)).toBeVisible();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
