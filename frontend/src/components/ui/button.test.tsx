import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Button } from "./button";
import { Dialog } from "./dialog";
afterEach(cleanup);
it("performs the requested action and respects disabled state", () => {
  const action = vi.fn();
  const view = render(<Button onClick={action}>Guardar cambios</Button>);
  fireEvent.click(screen.getByRole("button"));
  expect(action).toHaveBeenCalledOnce();
  view.rerender(
    <Button disabled onClick={action}>
      Guardar cambios
    </Button>,
  );
  fireEvent.click(screen.getByRole("button"));
  expect(action).toHaveBeenCalledOnce();
});
it("provides an accessible confirmation dialog", () => {
  render(
    <Dialog
      open
      onOpenChange={() => {}}
      title="Eliminar reunión"
      description="Se eliminarán sus archivos"
    >
      <Button>Confirmar</Button>
    </Dialog>,
  );
  expect(
    screen.getByRole("dialog", { name: "Eliminar reunión" }),
  ).toBeVisible();
  expect(screen.getByText("Se eliminarán sus archivos")).toBeVisible();
});
