import { t, translateMessage } from "./i18n";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
type UploadHandler = (meeting: string, file: File) => Promise<unknown>;
let uploadHandler: UploadHandler | undefined;
export function installUploadHandler(handler: UploadHandler) {
  uploadHandler = handler;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const upload = path.match(/^\/meetings\/([^/]+)\/upload$/);
  if (uploadHandler && upload && options.body instanceof FormData) {
    const file = options.body.get("file");
    if (!(file instanceof File)) throw new Error(t("Selecciona una grabación"));
    return (await uploadHandler(upload[1], file)) as T;
  }
  const headers = new Headers(options.headers);
  const csrf = document.cookie
    .split("; ")
    .find((item) => item.startsWith("mra_csrf="))
    ?.slice(9);
  if (csrf && options.method && !["GET", "HEAD"].includes(options.method))
    headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      t("Error de red. Comprueba la conexión y vuelve a intentarlo."),
    );
  }
  if (!response.ok) {
    const error: { detail?: unknown } = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      typeof error.detail === "string"
        ? translateMessage(error.detail)
        : t("No se pudo completar la operación ({status}).", {
            status: response.status,
          }),
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const remove = (path: string) => api<void>(path, { method: "DELETE" });
