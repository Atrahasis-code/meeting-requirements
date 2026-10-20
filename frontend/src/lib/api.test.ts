import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
afterEach(() => vi.unstubAllGlobals());
it("surfaces the actual API validation error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        detail: "Cambió la entrada; autoriza nuevamente",
      }),
    }),
  );
  await expect(api("/meetings/123/analyze")).rejects.toThrow(
    "Cambió la entrada",
  );
});
it("handles empty successful responses", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 204 }));
  await expect(
    api("/projects/123", { method: "DELETE" }),
  ).resolves.toBeUndefined();
});
