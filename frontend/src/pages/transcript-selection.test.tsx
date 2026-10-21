import { afterEach, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AnalysisButton, TranscriptPage } from "./meetings";
import { setLanguage } from "../lib/i18n";

const baseSegments = [
  {
    id: "one",
    start: 0,
    end: 10,
    original_text: "Necesidad relevante",
    revised_text: null,
    reviewed: true,
    discarded: false,
    doubtful: true,
    detection: {},
  },
  {
    id: "two",
    start: 10,
    end: 20,
    original_text: "Ruido descartado",
    revised_text: null,
    reviewed: false,
    discarded: true,
    doubtful: false,
    detection: {},
  },
  {
    id: "three",
    start: 20,
    end: 30,
    original_text: "Texto pendiente",
    revised_text: null,
    reviewed: false,
    discarded: false,
    doubtful: false,
    detection: {},
  },
];
const meeting = {
  id: "meeting",
  title: "Revisión sintética",
  jobs: [],
  transcript_revision: 1,
  media: null,
};
const entry = (included = true) => ({
  input_hash: "authorized-hash",
  snapshot: {
    provider: "mock",
    model: null,
    context: "Contexto",
    glossary: {},
    revision: 1,
    selection_policy: "reviewed_only_v1",
    selection_summary: {
      total: 3,
      reviewed: included ? 1 : 0,
      discarded: 1,
      pending: included ? 1 : 2,
      included: included ? 1 : 0,
    },
    segments: included
      ? [
          {
            id: "one",
            start: 0,
            end: 10,
            text: "Necesidad relevante",
            doubtful: true,
          },
        ]
      : [],
  },
});
function setup({ conflict = false, empty = false, english = false } = {}) {
  if (english) setLanguage("en");
  const segments = structuredClone(baseSegments);
  const requests: { url: string; body: Record<string, unknown> }[] = [];
  let revision = 1;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input, options) => {
      const url = String(input);
      if (options?.method === "PATCH") {
        const body = JSON.parse(options.body);
        requests.push({ url, body });
        if (conflict)
          return {
            ok: false,
            status: 409,
            json: async () => ({
              detail: "La transcripción cambió; recarga antes de guardar",
            }),
          };
        const segment = segments.find((s) => url.endsWith(s.id))!;
        Object.assign(segment, body);
        revision++;
        return {
          ok: true,
          status: 200,
          json: async () => ({ segment, revision }),
        };
      }
      const data = url.endsWith("/transcript")
        ? { revision, complete: true, segments }
        : url.endsWith("analysis-input")
          ? entry(!empty)
          : meeting;
      return { ok: true, status: 200, json: async () => data };
    }),
  );
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return { requests, cache };
}
function editor() {
  const data = setup();
  render(
    <QueryClientProvider client={data.cache}>
      <MemoryRouter initialEntries={["/meetings/meeting/transcript"]}>
        <Routes>
          <Route path="/meetings/:id/transcript" element={<TranscriptPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return data;
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  act(() => setLanguage("es"));
});
it("filters reversible decisions without a doubtful checkbox; edits require a new decision", async () => {
  const { requests } = editor();
  const first = await screen.findByRole("group", {
    name: "Selección del bloque 00:00:00",
  });
  expect(within(first).getByLabelText("Revisado")).toBeChecked();
  fireEvent.click(within(first).getByLabelText("Descartado"));
  expect(screen.getByText("Descartados: 2")).toBeInTheDocument();
  expect(
    screen.queryByRole("checkbox", { name: "Por comprobar" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText("Guarda los cambios antes de analizar."),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Filtrar bloques"), {
    target: { value: "discarded" },
  });
  expect(screen.queryByDisplayValue("Texto pendiente")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Texto del segmento 00:00:00"), {
    target: { value: "Corrección humana" },
  });
  expect(
    screen.queryByDisplayValue("Corrección humana"),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Filtrar bloques"), {
    target: { value: "pending" },
  });
  const pending = screen.getByRole("group", {
    name: "Selección del bloque 00:00:00",
  });
  expect(
    within(pending).getByRole("radio", { name: "Pendiente" }),
  ).toBeChecked();
  expect(
    within(pending).getByRole("radio", { name: "Revisado" }),
  ).not.toBeChecked();
  expect(
    within(pending).getByRole("radio", { name: "Descartado" }),
  ).not.toBeChecked();
  fireEvent.click(within(pending).getByLabelText("Revisado"));
  fireEvent.click(screen.getByRole("button", { name: "Guardar 1 cambio" }));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0].body).not.toHaveProperty("doubtful");
  expect(requests[0].body).toMatchObject({
    revised_text: "Corrección humana",
    reviewed: true,
    discarded: false,
    revision: 1,
  });
});
it("preserves a draft on 409 and allows an explicit reload before retrying", async () => {
  const { cache, requests } = setup({ conflict: true });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/meetings/meeting/transcript"]}>
        <Routes>
          <Route path="/meetings/:id/transcript" element={<TranscriptPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const text = await screen.findByLabelText("Texto del segmento 00:00:00");
  fireEvent.change(text, { target: { value: "Mi borrador" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar 1 cambio" }));
  await screen.findByRole("alert");
  expect(text).toHaveValue("Mi borrador");
  expect(
    screen.getByRole("button", { name: "Guardar 1 cambio" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Cargar revisión vigente" }),
  );
  await waitFor(() =>
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
  );
  expect(text).toHaveValue("Mi borrador");
  expect(requests).toHaveLength(1);
});
it.each([false, true])(
  "previews only included text and translates all new selection controls (English=%s)",
  async (english) => {
    const { cache } = setup({ english });
    render(
      <QueryClientProvider client={cache}>
        <MemoryRouter>
          <AnalysisButton meeting={meeting as never} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: english ? "Analyze requirements" : "Analizar requisitos",
      }),
    );
    await screen.findByText(english ? "Discarded: 1" : "Descartados: 1");
    expect(
      screen.getByLabelText(
        english ? "Reviewed transcript" : "Transcripción revisada",
      ),
    ).toHaveValue("[00:00:00] Necesidad relevante");
    expect(screen.queryByText("Ruido descartado")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: english ? "Confirm analysis" : "Confirmar análisis",
      }),
    ).toBeDisabled();
  },
);
it("blocks an empty selection and provides a link to review", async () => {
  const { cache } = setup({ empty: true });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <AnalysisButton meeting={meeting as never} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Analizar requisitos" }));
  await screen.findByText(
    "Marca como revisado al menos un bloque con texto antes de analizar",
  );
  fireEvent.click(
    screen.getByLabelText(
      "Autorizo este análisis con la entrada y el proveedor indicados.",
    ),
  );
  expect(
    screen.getByRole("button", { name: "Confirmar análisis" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("link", { name: "Abrir transcripción" }),
  ).toHaveAttribute("href", "/meetings/meeting/transcript");
});
