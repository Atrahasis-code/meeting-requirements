import { Languages } from "lucide-react";
import { useI18n } from "../lib/i18n";

export function LanguageSelector({ className = "" }: { className?: string }) {
  const { locale, t, setLanguage } = useI18n();
  return (
    <label className={"language-selector " + className}>
      <Languages size={17} aria-hidden="true" />
      <span className="sr-only">{t("Idioma de la interfaz")}</span>
      <select
        value={locale}
        onChange={(event) =>
          setLanguage(event.target.value === "en" ? "en" : "es")
        }
      >
        <option value="es" lang="es">
          Español
        </option>
        <option value="en" lang="en">
          English
        </option>
      </select>
    </label>
  );
}
