import { LocalizedForm } from "../components/localized-form";
import { t, useI18n, getLanguage, translateMessage } from "../lib/i18n";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Check,
  ExternalLink,
  Link2,
  LogOut,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import {
  Loading,
  PageHeader,
  TextField,
  useAction,
  useData,
} from "../components/shared";
import { patch, post } from "../lib/api";
import { bytes, label, providerStatus } from "../lib/utils";
import type { AuthStatus, Preferences } from "../types";
const schema = z.object({
  profile: z.string(),
  provider: z.string(),
  model: z.string(),
  language: z.string(),
});
type Values = z.infer<typeof schema>;
export function SettingsPage() {
  useI18n();
  const settings = useData<Preferences>("/settings");
  const connection = useData<AuthStatus>("/auth/chatgpt/status", true);
  const [params] = useSearchParams();
  if (!settings.data || !connection.data)
    return <Loading error={settings.error ?? connection.error} />;
  return (
    <>
      <PageHeader
        title={t("Configuración")}
        description={t(
          "Rendimiento local, conexión y consumo bajo tu control.",
        )}
      />
      {params.get("connection") === "failed" && (
        <div className="error-box" role="alert">
          {t(
            "No se pudo completar la conexión. Revisa los permisos de tu cuenta y vuelve a intentarlo. No se ha usado una API key.",
          )}
        </div>
      )}
      <SettingsForm preferences={settings.data} connection={connection.data} />
    </>
  );
}
function SettingsForm({
  preferences,
  connection,
}: {
  preferences: Preferences;
  connection: AuthStatus;
}) {
  useI18n();
  const action = useAction();
  const [confirmed, setConfirmed] = useState(connection.credits_zero_confirmed);
  const models = useData<{ slug: string; display_name: string }[]>(
    "/providers/chatgpt/models",
    false,
    connection.connected && connection.plan_authorized,
  );
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      profile: preferences.profile,
      provider: preferences.provider,
      model: preferences.model ?? "",
      language: preferences.language ?? "auto",
    },
  });
  useEffect(
    () => setConfirmed(connection.credits_zero_confirmed),
    [connection.credits_zero_confirmed],
  );
  async function connect(path = "/auth/chatgpt/start") {
    const result = await post<{ redirect: string }>(path);
    window.location.assign(result.redirect);
  }
  return (
    <div className="settings-layout">
      <section className="panel padded form-stack">
        <div className="section-heading">
          <h2>{t("Conexión con ChatGPT")}</h2>
          <Link2 size={20} />
        </div>
        <div className="connection-card">
          <span
            className={"status-dot " + (connection.connected ? "online" : "")}
          />
          <div>
            <strong>
              {connection.connected
                ? t("Cuenta conectada")
                : t("Conecta tu suscripción")}
            </strong>
            <small>
              {connection.email ?? t("Autenticación oficial. Sin API keys.")}
            </small>
          </div>
        </div>
        {connection.accounts.length > 0 && (
          <TextField label={t("Cuenta activa")}>
            <select
              value={connection.account_id ?? ""}
              onChange={(e) =>
                void action.run(() =>
                  post("/auth/chatgpt/select", { account_id: e.target.value }),
                )
              }
            >
              {!connection.account_id && (
                <option value="">{t("Selecciona una cuenta")}</option>
              )}
              {connection.accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.email} · {a.id.slice(0, 8)}
                  {!a.connected ? " " + t("· desconectada") : ""}
                </option>
              ))}
            </select>
          </TextField>
        )}
        <p>
          {t(
            "El acceso utiliza tu plan de ChatGPT cuando la cuenta y el entorno son elegibles. No se importan sesiones de otras aplicaciones.",
          )}
        </p>
        <div className="filter-group">
          <Button
            disabled={action.busy}
            onClick={() => void action.run(() => connect())}
          >
            <Link2 size={16} />
            {connection.connected
              ? t("Volver a autorizar")
              : t("Conectar con ChatGPT")}
          </Button>
          {connection.connected && (
            <>
              <Button
                variant="outline"
                disabled={action.busy}
                onClick={() =>
                  void action.run(() => connect("/auth/chatgpt/add-account"))
                }
              >
                {t("Otra cuenta")}
              </Button>
              <Button
                variant="ghost"
                disabled={action.busy}
                onClick={() =>
                  void action.run(async () => {
                    const result = await post<{
                      remote_revocation_confirmed: boolean;
                    }>("/auth/chatgpt/disconnect");
                    if (!result.remote_revocation_confirmed)
                      throw new Error(
                        t(
                          "Sesión local cerrada. No se confirmó la revocación remota; desconecta la aplicación en Configuración de ChatGPT.",
                        ),
                      );
                  }, t("Sesión desconectada"))
                }
              >
                <LogOut size={15} />
                {t("Desconectar")}
              </Button>
            </>
          )}
        </div>
        {connection.connected && !connection.plan_authorized && (
          <div className="error-box">
            {t(
              "La identidad está conectada, pero no se concedió permiso para utilizar el plan. Vuelve a autorizar; no se habilitarán análisis reales.",
            )}
          </div>
        )}
        {connection.error && (
          <div className="error-box">
            {t("Estado del proveedor:") + " "}
            {providerStatus(connection.error)}
          </div>
        )}
        <div className="subtle-divider" />
        <h3>{t("Protección del consumo")}</h3>
        <p>
          {t(
            "Antes de analizar, configura para esta aplicación un límite de créditos de",
          ) + " "}
          <strong>{t("cero")}</strong>
          {" " +
            t(
              "en ChatGPT. Esta aplicación no puede verificar ese límite remotamente.",
            )}
        </p>
        <a
          className="external-link"
          target="_blank"
          rel="noreferrer"
          href={connection.usage_url}
        >
          {t("Abrir controles de uso de ChatGPT")}
          <ExternalLink size={14} />
        </a>
        <label className="checkbox-label">
          <input
            disabled={!connection.connected}
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          {t(
            "Confirmo que configuré el límite de créditos de esta aplicación en cero.",
          )}
        </label>
        <Button
          variant="outline"
          disabled={!connection.connected || action.busy}
          onClick={() =>
            void action.run(
              () =>
                post("/auth/chatgpt/usage-policy", {
                  confirmed_zero_credits: confirmed,
                }),
              t("Confirmación manual registrada"),
            )
          }
        >
          <Check size={16} />
          {t("Guardar confirmación")}
          {connection.quota_blocked
            ? " " + t("y desbloquear reintento manual")
            : ""}
        </Button>
        {connection.quota_blocked && (
          <div className="notice">
            {t(
              "Cuota o límite alcanzado. Los trabajos pendientes se conservan. Revisa Uso y reanuda el análisis manualmente cuando corresponda; no se presupone una hora de restablecimiento.",
            )}
          </div>
        )}
        <div className="verification-note">
          <ShieldCheck size={18} />
          <p>
            {connection.inference_verified
              ? t("Se completó al menos una inferencia real con esta conexión.")
              : t(
                  "La conexión OAuth no demuestra acceso a un modelo. La integración se verificará al completar un análisis real autorizado.",
                )}
            {connection.inference_verified && connection.last_inference_at && (
              <span>
                {" "}
                {t("Última verificación:")}{" "}
                {new Date(connection.last_inference_at * 1000).toLocaleString(
                  getLanguage(),
                )}{" "}
                · {connection.last_inference_model}.
              </span>
            )}
          </p>
        </div>
      </section>
      <div className="form-stack">
        <LocalizedForm
          className="panel padded form-stack"
          onSubmit={form.handleSubmit(
            (v) =>
              void action.run(
                () =>
                  patch("/settings", {
                    ...v,
                    model: v.model || null,
                    language: v.language === "auto" ? null : v.language,
                  }),
                t("Preferencias guardadas"),
              ),
          )}
        >
          <div className="section-heading">
            <h2>{t("Procesamiento")}</h2>
            <SlidersHorizontal size={20} />
          </div>
          <TextField label={t("Proveedor de análisis")}>
            <select {...form.register("provider")}>
              <option value="chatgpt">
                {t("ChatGPT · suscripción autorizada")}
              </option>
              <option disabled value="claude">
                {t("Claude · OAuth para terceros no habilitado")}
              </option>
              <option disabled value="grok">
                {t("Grok · OAuth no disponible para esta aplicación")}
              </option>
              <option value="mock">
                {t("Mock · simulación explícita sin conexión")}
              </option>
            </select>
          </TextField>
          <TextField label={t("Modelo de ChatGPT")}>
            <select {...form.register("model")}>
              <option value="">{t("Selecciona un modelo de tu cuenta")}</option>
              {models.data?.map((m) => (
                <option key={m.slug} value={m.slug}>
                  {m.display_name}
                </option>
              ))}
              {preferences.model &&
                !models.data?.some((m) => m.slug === preferences.model) && (
                  <option value={preferences.model}>
                    {preferences.model}
                    {" " + t("· guardado")}
                  </option>
                )}
            </select>
          </TextField>
          {models.error && (
            <p className="field-error">
              {translateMessage(models.error.message)}
            </p>
          )}
          <TextField label={t("Perfil predeterminado")}>
            <select {...form.register("profile")}>
              <option value="economy">{t("Económico · base · 2 hilos")}</option>
              <option value="balanced">
                {t("Equilibrado · small · 3 hilos")}
              </option>
              <option value="quality">
                {t("Calidad · medium · mayor memoria")}
              </option>
            </select>
          </TextField>
          <TextField label={t("Idioma de transcripción")}>
            <select {...form.register("language")}>
              <option value="es">{t("Español")}</option>
              <option value="en">{t("Inglés")}</option>
              <option value="auto">{t("Detección automática")}</option>
            </select>
          </TextField>
          <p className="muted">
            {t(
              "CPU · INT8 · un trabajo pesado simultáneo. Los límites de memoria y CPU se ajustan en .env y se aplican recreando los contenedores.",
            )}
          </p>
          <Button disabled={action.busy}>{t("Guardar preferencias")}</Button>
        </LocalizedForm>
        <section className="panel padded">
          <h2>{t("Almacenamiento local")}</h2>
          <p>
            {t("Límite por archivo:") + " "}
            {bytes(preferences.max_upload_bytes)}
          </p>
          <dl className="storage-list">
            {Object.entries(preferences.storage).map(([name, path]) => (
              <div key={name}>
                <dt>{label(name)}</dt>
                <dd>{path}</dd>
              </div>
            ))}
          </dl>
          <small>
            {t(
              "Volúmenes Docker persistentes. Las rutas corresponden al interior de los contenedores.",
            )}
          </small>
          {preferences.test_mode && (
            <div className="notice">
              {t(
                "Entorno de pruebas: transcripción simulada habilitada por configuración de Compose.",
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
