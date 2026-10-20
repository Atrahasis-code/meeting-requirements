import { afterEach, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import {
  countLabel,
  getLanguage,
  number,
  setLanguage,
  t,
  translateMessage,
} from "./i18n";
import { english } from "./i18n/messages";
import { LanguageSelector } from "../components/language-selector";
import { ProjectEditor } from "../pages/projects";
import { RequirementTable } from "../pages/requirements";
import { date } from "./utils";
import { api } from "./api";
import type { Requirement } from "../types";

afterEach(() => {
  cleanup();
  act(() => setLanguage("es"));
  localStorage.removeItem("mra-language");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it("defaults to Spanish and persists a deliberate English selection with document metadata", () => {
  expect(getLanguage()).toBe("es");
  render(<LanguageSelector />);
  fireEvent.change(
    screen.getByRole("combobox", { name: "Idioma de la interfaz" }),
    { target: { value: "en" } },
  );
  expect(
    screen.getByRole("combobox", { name: "Interface language" }),
  ).toHaveValue("en");
  expect(localStorage.getItem("mra-language")).toBe("en");
  expect(document.documentElement.lang).toBe("en");
  expect(t("Nueva reunión")).toBe("New meeting");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "es" } });
  expect(document.documentElement.lang).toBe("es");
  expect(t("Nueva reunión")).toBe("Nueva reunión");
});
it("updates from another tab and falls back to Spanish for an unsupported stored value", () => {
  render(<LanguageSelector />);
  act(() =>
    window.dispatchEvent(
      new StorageEvent("storage", { key: "mra-language", newValue: "en" }),
    ),
  );
  expect(
    screen.getByRole("combobox", { name: "Interface language" }),
  ).toHaveValue("en");
  act(() =>
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: "mra-language",
        newValue: "not-supported",
      }),
    ),
  );
  expect(
    screen.getByRole("combobox", { name: "Idioma de la interfaz" }),
  ).toHaveValue("es");
});
it("still changes language when browser storage is unavailable", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("storage disabled");
  });
  render(<LanguageSelector />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "en" } });
  expect(
    screen.getByRole("combobox", { name: "Interface language" }),
  ).toHaveValue("en");
});
it("localizes plurals, dates, numbers and interpolation without interpreting inserted text", () => {
  setLanguage("en");
  expect(countLabel("requirements", 1)).toBe("1 requirement");
  expect(countLabel("requirements", 2)).toBe("2 requirements");
  expect(countLabel("segments", 0)).toBe("0 segments");
  expect(
    translateMessage("No se pudo completar la operación (503). ".trim()),
  ).toBe("Could not complete the operation (503).");
  expect(date("2026-10-20")).toBe(
    new Intl.DateTimeFormat("en", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date("2026-10-20T12:00:00")),
  );
  expect(number(1234.5)).toBe(new Intl.NumberFormat("en").format(1234.5));
  expect(
    t("No se pudo completar la operación ({status}).", {
      status: "<img src=x>",
    }),
  ).toContain("<img src=x>");
  setLanguage("es");
  expect(countLabel("requirements", 1)).toBe("1 requisito");
  expect(countLabel("requirements", 2)).toBe("2 requisitos");
});
it("preserves an unsaved project draft and does not send requests when language changes", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <LanguageSelector />
        <ProjectEditor />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Nuevo proyecto" }));
  fireEvent.change(screen.getByLabelText("Nombre del proyecto"), {
    target: { value: "Mi borrador sin guardar" },
  });
  act(() => setLanguage("en"));
  expect(screen.getByLabelText("Project name")).toHaveValue(
    "Mi borrador sin guardar",
  );
  expect(screen.getByRole("button", { name: "Save project" })).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Project name"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save project" }));
  expect(await screen.findByText("Enter a name")).toBeVisible();
});
it("does not translate requirement text even if it matches an application message", () => {
  setLanguage("en");
  const requirement: Requirement = {
    id: "r",
    project_id: "p",
    analysis_id: "a",
    code: "RF-001",
    kind: "functional",
    title: "Nueva reunión",
    description: "Texto original",
    actor: "Persona",
    module: "Proyectos",
    priority: "high",
    status: "detected",
    interpretation: "fact",
    observations: "",
    evidence: [],
    original: { description: "Texto original" },
    questions: [],
    dependencies: [],
    revisions: [],
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <RequirementTable requirements={[requirement]} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const table = screen.getByRole("table");
  expect(within(table).getByText("Nueva reunión")).toBeVisible();
  expect(within(table).getByText("Proyectos")).toBeVisible();
  expect(within(table).getByText("High")).toBeVisible();
  expect(within(table).getByText("Detected")).toBeVisible();
});
it("translates known API errors and network failures but preserves unknown diagnostics", async () => {
  setLanguage("en");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        detail: "El criterio cambió; revisa la última versión antes de editar",
      }),
    }),
  );
  await expect(api("/criteria/test")).rejects.toThrow("The criterion changed");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
  );
  await expect(api("/projects")).rejects.toThrow("Network error");
  expect(translateMessage("provider-specific diagnostic 123")).toBe(
    "provider-specific diagnostic 123",
  );
});
it("provides nonempty English translations with matching interpolation parameters", () => {
  for (const [source, translation] of Object.entries(english)) {
    expect(translation.trim(), source).not.toBe("");
    const params = (text: string) =>
      [...text.matchAll(/\{([a-zA-Z]+)\}/g)].map((m) => m[1]).sort();
    expect(params(translation), source).toEqual(params(source));
  }
});

it("retranslates rendered errors, diagnostics and parameterized notifications in both directions", () => {
  setLanguage("en");
  const processing = translateMessage(
    "Falló la etapa de procesamiento (ValueError). Reintenta o revisa la configuración.",
  );
  expect(processing).toBe(
    "Processing failed (ValueError). Retry or review the configuration.",
  );
  const invalid = translateMessage(
    "ChatGPT devolvió un análisis que no supera la validación: hay códigos de requisitos duplicados; faltan campos obligatorios. Se conservaron los resultados anteriores; la respuesta rechazada no se activó. Puedes revisar la entrada y reanudar manualmente.",
  );
  expect(invalid).toContain(
    "there are duplicate requirement codes; required fields are missing",
  );
  expect(translateMessage("El texto no puede superar 200 caracteres.")).toBe(
    "Text cannot exceed 200 characters.",
  );
  setLanguage("es");
  expect(translateMessage(processing)).toBe(
    "Falló la etapa de procesamiento (ValueError). Reintenta o revisa la configuración.",
  );
  expect(translateMessage(invalid)).toContain(
    "hay códigos de requisitos duplicados; faltan campos obligatorios",
  );
});

it("updates existing errors and notifications when language changes without dismissing a dialog", async () => {
  const { Notifications, Loading, useAction } =
    await import("../components/shared");
  function Failure() {
    const action = useAction();
    return (
      <button
        onClick={() =>
          void action.run(async () => {
            throw new Error(
              "Falló la etapa de procesamiento (ValueError). Reintenta o revisa la configuración.",
            );
          })
        }
      >
        Fail
      </button>
    );
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Notifications>
        <Failure />
        <Loading
          error={
            new Error(
              "Almacenamiento ocupado o no disponible; reintenta la operación",
            )
          }
        />
      </Notifications>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("Fail"));
  await screen.findByText(/Falló la etapa/);
  act(() => setLanguage("en"));
  expect(
    screen.getByText(
      "Processing failed (ValueError). Retry or review the configuration.",
    ),
  ).toBeVisible();
  expect(
    screen.getByText("Storage is busy or unavailable; retry the operation"),
  ).toBeVisible();
  act(() => setLanguage("es"));
  expect(screen.getByText(/Falló la etapa/)).toBeVisible();
});

it("localizes native required and email validation without clearing a draft", async () => {
  const { LocalizedForm } = await import("../components/localized-form");
  render(
    <LocalizedForm>
      <input aria-label="Email" type="email" required defaultValue="invalid" />
      <button>Submit</button>
    </LocalizedForm>,
  );
  const input = screen.getByLabelText("Email") as HTMLInputElement;
  fireEvent.invalid(input);
  expect(input.validationMessage).toBe(
    "Introduce un correo electrónico válido.",
  );
  act(() => setLanguage("en"));
  expect(input.validationMessage).toBe("Enter a valid email address.");
  expect(input.value).toBe("invalid");
  fireEvent.input(input, { target: { value: "" } });
  fireEvent.invalid(input);
  expect(input.validationMessage).toBe("Complete this field.");
  act(() => setLanguage("es"));
  expect(input.validationMessage).toBe("Completa este campo.");
  fireEvent.input(input, { target: { value: "test@example.invalid" } });
  expect(input.checkValidity()).toBe(true);
});

it("localizes storage labels and known OAuth states while preserving diagnostic identifiers", async () => {
  const { label, providerStatus, actorLabel } = await import("./utils");
  setLanguage("en");
  expect(label("transcripts")).toBe("Transcript files");
  expect(
    actorLabel({ id: "local-owner", kind: "local", label: "Usuario local" }),
  ).toBe("Local user");
  expect(
    actorLabel({ id: "real-user", kind: "user", label: "Usuario local" }),
  ).toBe("Usuario local");
  expect(label("validate_upload")).toBe("Validating recording");
  const status = providerStatus("refresh_token_expired");
  expect(status).toContain("Reconnect the account.");
  expect(status).toContain("(refresh_token_expired)");
  setLanguage("es");
  expect(providerStatus("refresh_token_expired")).toContain(
    "Vuelve a conectar la cuenta.",
  );
  expect(providerStatus("unknown_code")).toBe("unknown_code");
});

it("does not render Pydantic English errors or submitted input from a structured API validation error", async () => {
  setLanguage("es");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ msg: "Field required", input: "private draft" }],
      }),
    }),
  );
  await expect(api("/criteria/test")).rejects.toThrow(
    "La solicitud no es válida.",
  );
  setLanguage("en");
  await expect(api("/criteria/test")).rejects.toThrow(
    "The request is invalid.",
  );
});
