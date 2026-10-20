import { useSyncExternalStore } from "react";
import { english } from "./i18n/messages";

export type Locale = "es" | "en";
export type Message = keyof typeof english;
type Parameters = Record<string, string | number>;
const catalog: Record<string, string> = { ...english };
const preferenceKey = "mra-language";
const listeners = new Set<() => void>();
const supported = (value: unknown): value is Locale =>
  value === "es" || value === "en";
function savedLanguage(): Locale {
  try {
    const value = localStorage.getItem(preferenceKey);
    return supported(value) ? value : "es";
  } catch {
    return "es";
  }
}
let language: Locale = savedLanguage();
export const getLanguage = () => language;
export function t(message: Message, parameters: Parameters = {}): string {
  return renderMessage(message, parameters);
}
function renderMessage(message: string, parameters: Parameters = {}): string {
  const text = language === "en" ? (catalog[message] ?? message) : message;
  return text.replace(/\{([a-zA-Z]+)\}/g, (match, key: string) =>
    Object.prototype.hasOwnProperty.call(parameters, key)
      ? String(parameters[key])
      : match,
  );
}

// Additional application entrypoints can register their own static UI catalog.
// These messages are bundled only by the entrypoint that imports them.
export function registerMessages<const Catalog extends Record<string, string>>(
  messages: Catalog,
) {
  for (const [key, value] of Object.entries(messages)) {
    if (Object.hasOwn(catalog, key) && catalog[key] !== value)
      throw new Error("Conflicting UI translation: " + key);
    catalog[key] = value;
  }
  return (message: Message | keyof Catalog, parameters: Parameters = {}) =>
    renderMessage(String(message), parameters);
}

// Translate exact application messages only; never apply this to meeting data.
export function translateMessage(message: string): string {
  const key = Object.hasOwn(catalog, message)
    ? message
    : Object.keys(catalog).find((key) => catalog[key] === message);
  if (key !== undefined) return renderMessage(key);
  // Match only registered UI templates, in either language. Meeting content
  // never passes through this function; captured identifiers stay unchanged.
  for (const [source, english] of Object.entries(catalog)) {
    if (!source.includes("{")) continue;
    for (const template of [source, english]) {
      const names: string[] = [];
      const pattern = template
        .split(/(\{[a-zA-Z]+\})/g)
        .map((part) => {
          if (/^\{[a-zA-Z]+\}$/.test(part)) {
            names.push(part.slice(1, -1));
            return "([\\s\\S]+?)";
          }
          return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        })
        .join("");
      const match = message.match(new RegExp("^" + pattern + "$"));
      if (!match) continue;
      return renderMessage(
        source,
        Object.fromEntries(
          names.map((name, i) => {
            const value = match[i + 1];
            // Validation reasons are a fixed backend vocabulary. Preserve codes,
            // exception types and unknown diagnostics for troubleshooting.
            return [
              name,
              name === "diagnostic"
                ? value
                    .split("; ")
                    .map((reason) => {
                      const key = Object.hasOwn(catalog, reason)
                        ? reason
                        : Object.keys(catalog).find(
                            (key) => catalog[key] === reason,
                          );
                      return key === undefined ? reason : renderMessage(key);
                    })
                    .join("; ")
                : value,
            ];
          }),
        ),
      );
    }
  }
  return message;
}
function updateDocument() {
  if (typeof document === "undefined") return;
  document.documentElement.lang = language;
  document
    .querySelector('meta[name="description"]')
    ?.setAttribute(
      "content",
      language === "en"
        ? "Turn meetings into reviewable requirements with local transcription, evidence, and human validation."
        : "De reuniones a requisitos revisables: transcripción local, evidencia y validación humana.",
    );
}
export function setLanguage(value: Locale, persist = true) {
  if (!supported(value)) return;
  if (persist) {
    try {
      localStorage.setItem(preferenceKey, value);
    } catch {
      /* Session-only preference when storage is unavailable. */
    }
  }
  if (value === language) {
    updateDocument();
    return;
  }
  language = value;
  updateDocument();
  listeners.forEach((notify) => notify());
}
function onStorage(event: StorageEvent) {
  if (event.key === preferenceKey || event.key === null)
    setLanguage(supported(event.newValue) ? event.newValue : "es", false);
}
function subscribe(notify: () => void) {
  listeners.add(notify);
  if (listeners.size === 1 && typeof window !== "undefined")
    window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(notify);
    if (!listeners.size && typeof window !== "undefined")
      window.removeEventListener("storage", onStorage);
  };
}
export function useI18n() {
  const locale = useSyncExternalStore(
    subscribe,
    getLanguage,
    () => "es" as const,
  );
  return { locale, t, setLanguage };
}
export function number(value: number, options?: Intl.NumberFormatOptions) {
  return new Intl.NumberFormat(language, options).format(value);
}
const counts = {
  segments: { es: ["segmento", "segmentos"], en: ["segment", "segments"] },
  requirements: {
    es: ["requisito", "requisitos"],
    en: ["requirement", "requirements"],
  },
  references: {
    es: ["referencia", "referencias"],
    en: ["reference", "references"],
  },
  projects: { es: ["proyecto", "proyectos"], en: ["project", "projects"] },
  glossary: {
    es: ["término en glosario", "términos en glosario"],
    en: ["glossary term", "glossary terms"],
  },
  changes: { es: ["cambio", "cambios"], en: ["change", "changes"] },
} as const;
export function countLabel(kind: keyof typeof counts, count: number) {
  const singular = new Intl.PluralRules(language).select(count) === "one";
  return `${number(count)} ${counts[kind][language][singular ? 0 : 1]}`;
}
updateDocument();
