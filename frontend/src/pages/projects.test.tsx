import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { Dashboard, ProjectEditor } from "./projects";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("rejects a blank project name before sending data and submits a valid glossary", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ id: "project-id" }),
  });
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ProjectEditor />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Nuevo proyecto" }));
  fireEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));
  expect(await screen.findByText("Escribe un nombre")).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByPlaceholderText("Ej. Portal de solicitudes"), {
    target: { value: "Portal" },
  });
  fireEvent.change(
    screen.getByPlaceholderText("CRM = Gestión de relaciones con clientes"),
    { target: { value: "CRM = Clientes" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
    name: "Portal",
    glossary: { CRM: "Clientes" },
  });
});

it("shows each workspace metric with its correct numeric value", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        project_count: 2,
        meeting_count: 7,
        pending_requirements: 3,
        projects: [],
        jobs: [],
      }),
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const meetings = await screen.findByRole("group", {
    name: "Reuniones registradas",
  });
  expect(within(meetings).getByText("7")).toBeVisible();
  expect(
    within(screen.getByRole("group", { name: "Proyectos activos" })).getByText(
      "2",
    ),
  ).toBeVisible();
  expect(
    within(screen.getByRole("group", { name: "Por validar" })).getByText("3"),
  ).toBeVisible();
  expect(screen.queryByText("[object Object]")).not.toBeInTheDocument();
});
