import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import snapshot from "../../public/snapshot.json";
import { previewWorkspace } from "../domain";
import type { Snapshot, WorkInterrupt } from "../types";
import { AgentPanel } from "./AgentPanel";

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  getState: vi.fn(),
  submit: vi.fn(),
  respond: vi.fn(),
  stream: {} as Record<string, unknown>,
}));
vi.mock("../api", () => ({
  ASSISTANT: "refinery-reliability-agent",
  createClient: () => ({ threads: { create: mocks.create, getState: mocks.getState } }),
}));
vi.mock("@langchain/react", () => ({ useStream: () => mocks.stream }));
vi.mock("@langchain/macaw-components/Button", () => ({
  Button: ({ children, variant: _variant, color: _color, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));
vi.mock("@langchain/macaw-components/ThinkingState", () => ({
  ThinkingState: ({ label }: { label: string }) => <span>{label}</span>,
}));

const workspace = previewWorkspace(snapshot as Snapshot);
const issue = workspace.issues[0];
const asset = workspace.assets.find((asset) => asset.asset_id === issue.asset_id)!;
const onRefresh = vi.fn();
const panel = () => (
  <TooltipProvider>
    <AgentPanel
      apiKey="test-key-placeholder"
      asset={asset}
      issue={issue}
      onRefresh={onRefresh}
      onConnect={vi.fn()}
    />
  </TooltipProvider>
);

beforeEach(() => {
  vi.clearAllMocks();
  mocks.create.mockResolvedValue({ thread_id: issue.thread_id });
  mocks.getState.mockResolvedValue({
    values: { messages: [{ type: "ai", content: "Saved final answer" }] },
  });
  mocks.stream = {
    messages: [{ type: "ai", content: "Stale streamed answer" }],
    values: { messages: [] },
    isLoading: false,
    isThreadLoading: false,
    interrupt: undefined,
    submit: mocks.submit,
    respond: mocks.respond,
  };
});
afterEach(cleanup);

describe("authoritative chat and durable reviews", () => {
  it("loads the canonical thread and replaces stream projections with the saved final answer", async () => {
    render(panel());
    await screen.findByText("Saved final answer");
    expect(screen.queryByText("Stale streamed answer")).toBeNull();
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ threadId: issue.thread_id, ifExists: "do_nothing" }),
    );
    expect(mocks.getState).toHaveBeenCalledWith(issue.thread_id);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Investigate issue" }).hasAttribute("disabled"),
      ).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: "Investigate issue" }));
    expect(mocks.submit).toHaveBeenCalledWith(
      {
        messages: [
          expect.objectContaining({
            content: expect.stringMatching(/^Investigate the P-101A issue/),
          }),
        ],
      },
      expect.objectContaining({
        config: expect.objectContaining({
          configurable: { issue_id: issue.issue_id, asset_id: asset.asset_id },
        }),
      }),
    );
  });

  it.each(["approve", "reject"] as const)(
    "restores an interrupt and sends the explicit %s decision",
    async (action) => {
      const review: WorkInterrupt = {
        kind: "work_order_review",
        proposal: {
          proposal_id: "review-1",
          issue_id: issue.issue_id,
          status: "pending_review",
          thread_id: issue.thread_id,
          created_at: "2026-09-24T00:00:00Z",
          request: {
            asset_id: asset.asset_id,
            title: "Inspect bearing",
            priority: "P2",
            justification: "Rising vibration",
            tasks: ["Inspect bearing condition"],
          },
        },
      };
      mocks.stream.interrupt = { id: "interrupt-1", value: review };
      render(panel());
      await screen.findByRole("heading", { name: "Review proposed work" });
      expect(
        screen.getByRole("button", { name: "Investigate issue" }).hasAttribute("disabled"),
      ).toBe(true);
      fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Operator review note" },
      });
      fireEvent.click(
        screen.getByRole("button", {
          name: action === "approve" ? "Approve draft" : "Reject proposal",
        }),
      );
      expect(mocks.respond).toHaveBeenCalledWith(
        { action, reason: "Operator review note" },
        expect.objectContaining({ interruptId: "interrupt-1" }),
      );
    },
  );
});
