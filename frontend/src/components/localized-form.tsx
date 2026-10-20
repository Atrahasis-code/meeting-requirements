import { useEffect, useRef, type ComponentProps } from "react";
import { t, useI18n } from "../lib/i18n";

type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
function isControl(target: EventTarget | null): target is Control {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLSelectElement ||
    target instanceof HTMLTextAreaElement
  );
}
function localize(control: Control) {
  control.setCustomValidity("");
  if (control.validity.valid) return;
  control.setCustomValidity(
    control.validity.valueMissing
      ? t("Completa este campo.")
      : control instanceof HTMLInputElement &&
          control.type === "email" &&
          control.validity.typeMismatch
        ? t("Introduce un correo electrónico válido.")
        : t("Introduce un valor válido."),
  );
}

// Native validation bubbles otherwise use the browser's language, even after
// the interface language changes. Do not submit, reset drafts or report errors
// merely because the preference changed.
export function LocalizedForm({
  onInvalidCapture,
  onInputCapture,
  ...props
}: ComponentProps<"form">) {
  const { locale } = useI18n();
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    for (const element of form.current?.elements ?? []) {
      if (isControl(element) && element.validity.customError) localize(element);
    }
  }, [locale]);
  return (
    <form
      {...props}
      ref={form}
      onInvalidCapture={(event) => {
        if (isControl(event.target)) localize(event.target);
        onInvalidCapture?.(event);
      }}
      onInputCapture={(event) => {
        if (isControl(event.target)) event.target.setCustomValidity("");
        onInputCapture?.(event);
      }}
    />
  );
}
