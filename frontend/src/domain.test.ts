import { describe, expect, it } from "vitest";
import snapshot from "../public/snapshot.json";
import {
  artifacts,
  condition,
  messageText,
  previewWorkspace,
  quickActions,
  rankedIssues,
  reviewState,
} from "./domain";
import type { Assessment, Snapshot } from "./types";

const workspace = previewWorkspace(snapshot as Snapshot);

describe("workspace evidence and status", () => {
  it("shows the actual fixture without inventing healthy assets or unit faults", () => {
    expect(workspace.assets).toHaveLength(40);
    expect(workspace.issues).toHaveLength(4);
    expect(workspace.issues.some((issue) => issue.asset_id === "K-401")).toBe(false);
    expect(condition().label).toBe("Unassessed");
    expect(condition(workspace.issues[0]).label).toBe("Signal");
  });

  it("puts the critical pump first and keeps quick actions in plain language", () => {
    const ranked = rankedIssues(workspace.issues, workspace.assets, "all", "all");
    expect(ranked.map((issue) => issue.asset_id)).toEqual(["P-101A", "C-301", "E-205", "P-102B"]);
    expect(quickActions.investigate(ranked[0])).not.toMatch(/record_issue_assessment|get_issue/);
  });

  it("ranks by saved assessment and keeps work review separate from condition", () => {
    const issue = workspace.issues[0];
    const assessment: Assessment = {
      assessment_id: "a1",
      issue_id: issue.issue_id,
      condition: "needs_attention",
      priority: "P1",
      summary: "Evidence needs review",
      recommendation: "Inspect this equipment",
      uncertainty: "Cause unconfirmed",
      evidence_ids: [issue.evidence[0].reference_id],
      assessed_at: "2026-09-24T00:00:00Z",
      thread_id: issue.thread_id,
    };
    const assessed = {
      ...issue,
      assessment,
      assessment_history: [assessment],
      proposals: [
        {
          status: "rejected" as const,
          proposal_id: "p1",
          issue_id: issue.issue_id,
          request: {
            asset_id: issue.asset_id,
            title: "Inspect",
            priority: "P2" as const,
            justification: "Review evidence",
            tasks: ["Inspect"],
          },
          created_at: assessment.assessed_at,
          thread_id: issue.thread_id,
          review: {
            action: "reject" as const,
            reason: "Revise scope",
            reviewed_at: assessment.assessed_at,
            actor: "workspace_operator" as const,
          },
        },
      ],
    };
    const issues = [...workspace.issues.slice(1), assessed];
    const units = new Map(workspace.assets.map((asset) => [asset.asset_id, asset.unit_id]));
    const assets = workspace.assets;
    expect(rankedIssues(issues, assets, "all", "all")[0]).toBe(assessed);
    expect(rankedIssues(issues, assets, "all", "assessed")).toEqual([assessed]);
    expect(rankedIssues(issues, assets, "all", "open")).not.toContain(assessed);
    expect(
      rankedIssues(issues, assets, "HDT", "all").every(
        (item) => units.get(item.asset_id) === "HDT",
      ),
    ).toBe(true);
    expect(condition(assessed).label).toBe("Needs attention");
    expect(reviewState(assessed)?.label).toBe("Proposal rejected");
    expect(issues[issues.length - 1]).toBe(assessed);
  });
});

describe("agent messages", () => {
  it("renders text blocks without exposing reasoning or arbitrary JSON blocks", () => {
    expect(
      messageText([
        { type: "reasoning", reasoning: "private" },
        { type: "text", text: "The answer" },
      ]),
    ).toBe("The answer");
    expect(messageText({ unexpected: "value" })).toBe("");
  });

  it("uses exact signed artifact URLs from the publishing tool only", () => {
    const url = "https://demo--dl.smithbox.dev/report.html?signature=abc%2Bdef&expires=123";
    const tool = {
      type: "tool",
      name: "publish_artifact",
      content: JSON.stringify({ url, content_type: "text/html" }),
    };
    expect(
      artifacts([
        tool,
        tool,
        { type: "ai", content: JSON.stringify({ url: "https://invented.example/report" }) },
      ]),
    ).toEqual([{ url, label: "Condition report", image: false }]);
    for (const invalid of [
      "http://demo--dl.smithbox.dev/report",
      "https://demo--dl.smithbox.dev.evil.test/report",
      "javascript:alert(1)",
    ]) {
      expect(artifacts([{ ...tool, content: JSON.stringify({ url: invalid }) }])).toEqual([]);
    }
  });
});
