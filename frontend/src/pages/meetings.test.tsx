import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ResultsPage } from "./meetings";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it.each([
  ["pending_validation", "Pendiente de tu validación"],
  ["validated", "Validado"],
  ["rejected", "Rechazado"],
])(
  "shows persisted codes, original criteria and status %s",
  async (status, statusLabel) => {
    const generated = {
      summary: {},
      stories: [
        {
          code: "HU-001",
          text: "Como usuario, quiero consultar solicitudes, para conocer su estado.",
          requirements: ["RF-001"],
        },
      ],
      criteria: [
        {
          code: "CA-001",
          story_code: "HU-001",
          given: "Original dado",
          when: "Original cuando",
          then: "Original entonces",
          requirements: ["RF-001"],
        },
      ],
      business_rules: [],
      questions: [],
      processes: [],
      conceptual_model: [],
      backlog: [
        {
          code: "BL-001",
          module: "Portal",
          story_code: "HU-001",
          requirements: ["RF-001"],
          priority: "unspecified",
          status: "proposed",
          dependencies: [],
        },
      ],
    };
    const analysis = {
      id: "version-two",
      provider: "mock",
      active: true,
      created_at: "2026-10-19T12:00:00Z",
      input_snapshot: { revision: 1 },
      requirements: [],
      code_mapping: { "RF-001": "RF-002" },
      original_result: generated,
      criteria: [
        {
          ...generated.criteria[0],
          id: "criterion",
          status,
          revision: 1,
          given: "Dado revisado",
          when: "Cuando revisado",
          then: "Entonces verificable",
          original: generated.criteria[0],
          revisions: [
            {
              created_at: "2026-10-19T20:00:00Z",
              before: {
                ...generated.criteria[0],
                status: "pending_validation",
              },
              after: {
                given: "Dado revisado",
                when: "Cuando revisado",
                then: "Entonces verificable",
                status: "pending_validation",
              },
              observations: "Revisión solicitada",
            },
          ],
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input) => {
        const url = String(input);
        const data = url.endsWith("/analyses")
          ? [analysis]
          : url.endsWith("/exports")
            ? []
            : {
                id: "meeting",
                title: "Versión sintética",
                jobs: [],
                transcript_revision: 1,
              };
        return { ok: true, status: 200, json: async () => data };
      }),
    );
    const cache = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={cache}>
        <MemoryRouter initialEntries={["/meetings/meeting/results"]}>
          <Routes>
            <Route path="/meetings/:id/results" element={<ResultsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByRole("heading", { name: "Versión sintética" });
    fireEvent.click(screen.getByRole("button", { name: "Historias" }));
    expect(screen.getByText("Requisitos de origen: RF-002")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Backlog" }));
    expect(screen.getByRole("cell", { name: "RF-002" })).toBeVisible();
    expect(generated.stories[0].requirements).toEqual(["RF-001"]);
    fireEvent.click(screen.getByRole("button", { name: "Criterios" }));
    expect(screen.getAllByText("Entonces verificable")[0]).toBeVisible();
    expect(screen.getByText(statusLabel)).toBeVisible();
    expect(screen.getByText("Requisitos de origen: RF-002")).toBeVisible();
    fireEvent.click(screen.getByText("Texto original generado"));
    expect(screen.getAllByText("Original entonces")[0]).toBeVisible();
    expect(generated.criteria[0].then).toBe("Original entonces");
  },
);
