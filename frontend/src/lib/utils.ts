import { getLanguage, translateMessage, number } from "./i18n";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function time(seconds: number) {
  return new Date(seconds * 1000).toISOString().slice(11, 19);
}
export function date(value: string) {
  return new Intl.DateTimeFormat(getLanguage(), {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value.includes("T") ? value : value + "T12:00:00"));
}
export function bytes(value: number) {
  return value > 1024 ** 3
    ? `${number(value / 1024 ** 3, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} GB`
    : `${number(value / 1024 ** 2, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} MB`;
}
export const labels: Record<string, string> = {
  validate_upload: "Validando grabación",
  commercial: "Proveedor comercial",
  db: "Base de datos",
  media: "Multimedia",
  transcripts: "Archivos de transcripción",
  exports: "Exportaciones",
  models: "Modelos",
  auth: "Autenticación",
  pending_validation: "Pendiente de tu validación",
  registered: "Sin grabación",
  uploaded: "Cargada",
  queued: "En cola",
  preparing_audio: "Preparando audio",
  downloading_model: "Descargando modelo",
  loading_model: "Cargando modelo",
  transcribing: "Transcribiendo",
  transcribed: "Transcrita",
  in_review: "En revisión",
  analyzing: "Analizando",
  completed: "Completada",
  failed: "Fallida",
  cancelled: "Cancelada",
  interrupted: "Interrumpida",
  blocked: "Bloqueado",
  starting: "Iniciando",
  running: "En ejecución",
  detected: "Detectado",
  unclear: "Por aclarar",
  proposed: "Propuesto",
  validated: "Validado",
  rejected: "Rechazado",
  high: "Alta",
  medium: "Media",
  low: "Baja",
  unspecified: "Sin indicar",
  fact: "Hecho",
  proposal: "Propuesta",
  inference: "Inferencia",
  economy: "Económico",
  balanced: "Equilibrado",
  quality: "Calidad",
  objective: "Objetivo",
  context: "Contexto",
  problems: "Problemas",
  needs: "Necesidades",
  decisions: "Decisiones",
  commitments: "Compromisos",
  risks: "Riesgos",
  next_steps: "Próximos pasos",
};
export const label = (value: string) =>
  translateMessage(labels[value] ?? value);

// Provider status contains diagnostic codes, never account or meeting content.
export function providerStatus(code: string) {
  const messages: Record<string, string> = {
    subscription_sharing_usage_limit_exceeded:
      "Cuota de ChatGPT alcanzada; revisa Uso y reanuda manualmente",
    subscription_sharing_user_not_eligible:
      "La cuenta no es elegible para compartir el plan de ChatGPT.",
    subscription_sharing_route_not_supported:
      "El plan de ChatGPT no permite esta operación o capacidad.",
    subscription_sharing_unsupported_capability:
      "El plan de ChatGPT no permite esta operación o capacidad.",
    chatpass_v2_scope_not_authorized:
      "El permiso del plan ya no está disponible",
    subscription_sharing_usage_unavailable:
      "El uso de ChatGPT no está disponible temporalmente. Reintenta más tarde.",
    refresh_failed: "No se pudo renovar la sesión; revisa la conexión",
  };
  if (
    [
      "invalid_grant",
      "invalid_refresh_token",
      "refresh_token_expired",
      "refresh_token_reused",
      "refresh_token_invalidated",
      "refresh_token_invalid",
      "token_expired",
      "subscription_sharing_invalid_user",
    ].includes(code)
  )
    return (
      translateMessage(
        "La sesión de ChatGPT expiró o fue revocada. Vuelve a conectar la cuenta.",
      ) +
      " (" +
      code +
      ")"
    );
  return messages[code]
    ? translateMessage(messages[code]) + " (" + code + ")"
    : translateMessage(code);
}

export function actorLabel(actor?: {
  id?: string;
  label?: string;
  kind?: string;
}) {
  if (
    actor?.kind === "local" &&
    actor.id === "local-owner" &&
    actor.label === "Usuario local"
  )
    return translateMessage("Usuario local");
  return (
    actor?.label ??
    translateMessage("Registro anterior sin identidad verificada")
  );
}
