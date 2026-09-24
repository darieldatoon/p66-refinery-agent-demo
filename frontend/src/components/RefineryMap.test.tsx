import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import snapshot from "../../public/snapshot.json";
import { previewWorkspace } from "../domain";
import type { Snapshot } from "../types";
import { RefineryMap } from "./RefineryMap";

afterEach(cleanup);

it("exposes all assets to keyboard selection and labels unassessed equipment", () => {
  const onSelect = vi.fn();
  render(
    <RefineryMap
      workspace={previewWorkspace(snapshot as Snapshot)}
      selected="P-101A"
      onSelect={onSelect}
    />,
  );
  expect(screen.getAllByRole("button")).toHaveLength(40);
  const compressor = screen.getByRole("button", { name: /K-401,.*Unassessed/ });
  fireEvent.keyDown(compressor, { key: "Enter" });
  expect(onSelect).toHaveBeenCalledWith("K-401");
  expect(
    screen.getByRole("button", { name: /P-101A,.*Signal detected/ }).getAttribute("aria-pressed"),
  ).toBe("true");
});
