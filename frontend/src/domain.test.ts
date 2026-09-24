import { describe, expect, it } from "vitest";
import snapshot from "../public/snapshot.json";
import { artifacts, conditionLabel, messageText, previewWorkspace, rankedIssues } from "./domain";
import type { Assessment, Snapshot } from "./types";

const workspace = previewWorkspace(snapshot as Snapshot);

describe("workspace evidence and status", () => {
  it("shows the actual fixture without inventing healthy assets or unit faults", () => {
    expect(workspace.assets).toHaveLength(40);
    expect(workspace.issues).toHaveLength(4);
    expect(workspace.issues.some((issue) => issue.asset_id === "K-401")).toBe(false);
    expect(conditionLabel()).toBe("Unassessed");
    expect(conditionLabel(workspace.issues[0])).toBe("Signal detected");
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
    expect(rankedIssues(issues, "all", units, "all")[0]).toBe(assessed);
    expect(rankedIssues(issues, "all", units, "assessed")).toEqual([assessed]);
    expect(rankedIssues(issues, "all", units, "pending")).toEqual([]);
    expect(
      rankedIssues(issues, "HDT", units, "all").every((item) => units.get(item.asset_id) === "HDT"),
    ).toBe(true);
    expect(conditionLabel(assessed)).toBe("Needs attention");
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
