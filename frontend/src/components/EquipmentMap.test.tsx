import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import snapshot from "../../public/snapshot.json";
import { previewWorkspace } from "../domain";
import type { Snapshot } from "../types";
import { EquipmentMap } from "./EquipmentMap";

afterEach(cleanup);

it("exposes every asset to selection and labels unassessed equipment", () => {
  const onSelect = vi.fn();
  render(
    <EquipmentMap
      workspace={previewWorkspace(snapshot as Snapshot)}
      selected="P-101A"
      onSelect={onSelect}
    />,
  );
  expect(screen.getAllByRole("button")).toHaveLength(40);
  fireEvent.click(screen.getByRole("button", { name: /K-401,.*Unassessed/ }));
  expect(onSelect).toHaveBeenCalledWith("K-401");
  expect(screen.getByRole("button", { name: /P-101A,.*Signal/ }).getAttribute("aria-pressed")).toBe(
    "true",
  );
});
