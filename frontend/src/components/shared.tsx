import { t, useI18n, translateMessage } from "../lib/i18n";
import {
  createContext,
  useContext,
  useState,
  useId,
  isValidElement,
  cloneElement,
  type ReactNode,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  FolderOpen,
  Trash2,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { label } from "../lib/utils";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
const ToastContext = createContext<(message: string, error?: boolean) => void>(
  () => {},
);
export function Notifications({ children }: { children: ReactNode }) {
  useI18n();
  const [toast, setToast] = useState<{
    message: string;
    error: boolean;
  } | null>(null);
  return (
    <ToastContext.Provider
      value={(message, error = false) => setToast({ message, error })}
    >
      {children}
      {toast && (
        <div
          className={"toast " + (toast.error ? "toast-error" : "")}
          role={toast.error ? "alert" : "status"}
        >
          {toast.error ? <AlertCircle size={18} /> : <Check size={18} />}
          <span>{translateMessage(toast.message)}</span>
          <button aria-label={t("Cerrar aviso")} onClick={() => setToast(null)}>
            <X size={18} />
          </button>
        </div>
      )}
    </ToastContext.Provider>
  );
}
export function useAction() {
  useI18n();
  const notify = useContext(ToastContext);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: async (operation: () => Promise<unknown>) => operation(),
    onSuccess: () => cache.invalidateQueries(),
    onError: (e: Error) => notify(e.message, true),
  });
  return {
    busy: mutation.isPending,
    run: (operation: () => Promise<unknown>, message?: string) =>
      mutation
        .mutateAsync(operation)
        .then((result) => {
          if (message) notify(message);
          return result;
        })
        .catch(() => undefined),
  };
}
export function useData<T>(path: string, poll = false, enabled = true) {
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path),
    refetchInterval: poll ? 2000 : false,
    enabled,
  });
}
export function Badge({ value }: { value: string }) {
  useI18n();
  return <span className={"badge badge-" + value}>{label(value)}</span>;
}
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  useI18n();
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="heading-actions">{actions}</div>
    </header>
  );
}
export function Loading({ error }: { error?: Error | null }) {
  useI18n();
  return error ? (
    <div className="error-box" role="alert">
      <AlertCircle />
      {translateMessage(error.message)}
    </div>
  ) : (
    <div className="loading" role="status" aria-live="polite">
      <span>{t("Cargando el espacio de trabajo…")}</span>
      <div className="loading-skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  useI18n();
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true">
        <FolderOpen size={24} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ConfirmDelete({
  title,
  description,
  onConfirm,
}: {
  title: string;
  description: string;
  onConfirm: () => Promise<unknown>;
}) {
  useI18n();
  const [open, setOpen] = useState(false);
  const action = useAction();
  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label={title}
        onClick={() => setOpen(true)}
      >
        <Trash2 size={17} />
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={title}
        description={description}
      >
        <div className="dialog-actions">
          <Button variant="outline" onClick={() => setOpen(false)}>
            {t("Conservar datos")}
          </Button>
          <Button
            variant="destructive"
            disabled={action.busy}
            onClick={() =>
              void action
                .run(onConfirm, t("Eliminación completada"))
                .then(() => setOpen(false))
            }
          >
            {t("Confirmar eliminación")}
          </Button>
        </div>
      </Dialog>
    </>
  );
}
export function TextField({
  label: caption,
  children,
  error,
}: {
  label: string;
  children: ReactNode;
  error?: string;
}) {
  useI18n();
  const generatedId = useId();
  const child = isValidElement<{
    id?: string;
    "aria-describedby"?: string;
    "aria-invalid"?: boolean;
  }>(children)
    ? children
    : null;
  const id = child?.props.id ?? generatedId;
  const errorId = id + "-error";
  return (
    <div className="field">
      <label htmlFor={id}>{caption}</label>
      {child
        ? cloneElement(child, {
            id,
            "aria-invalid": !!error || child.props["aria-invalid"],
            "aria-describedby":
              [child.props["aria-describedby"], error ? errorId : undefined]
                .filter(Boolean)
                .join(" ") || undefined,
          })
        : children}
      {error && (
        <small id={errorId} className="field-error">
          {translateMessage(error)}
        </small>
      )}
    </div>
  );
}
export function SectionTitle({
  title,
  to,
  label: linkLabel = t("Ver todos"),
}: {
  title: string;
  to?: string;
  label?: string;
}) {
  useI18n();
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {to && (
        <Link to={to}>
          {linkLabel}
          <ArrowUpRight size={15} />
        </Link>
      )}
    </div>
  );
}
