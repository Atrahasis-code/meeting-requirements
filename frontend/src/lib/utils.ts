import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function time(seconds: number) {
  return new Date(seconds * 1000).toISOString().slice(11, 19);
}
export function date(value: string) {
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value.includes("T") ? value : value + "T12:00:00"));
}
export function bytes(value: number) {
  return value > 1024 ** 3
    ? `${(value / 1024 ** 3).toFixed(1)} GB`
    : `${(value / 1024 ** 2).toFixed(1)} MB`;
}
export const labels: Record<string, string> = {
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
export const label = (value: string) => labels[value] ?? value;
