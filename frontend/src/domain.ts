import type { Asset, Issue, Message, Priority, Proposal, Snapshot, Workspace } from "./types";

export type Tone = "error" | "warning" | "success" | "secondary" | "primary";
export type ReviewFilter = "all" | "open" | "assessed";

export function previewWorkspace(snapshot: Snapshot): Workspace {
  return {
    snapshot_id: snapshot.snapshot_id,
    data_as_of: snapshot.data_as_of,
    units: snapshot.units,
    assets: snapshot.assets,
    issues: snapshot.signals.map((signal) => ({
      ...signal,
      assessment: null,
      assessment_history: [],
      proposals: [],
    })),
  };
}

export function issuePriority(issue: Issue): Priority {
  return issue.assessment?.priority ?? issue.priority;
}

export function pendingProposal(issue?: Issue): Proposal | undefined {
  return issue?.proposals.find((proposal) => proposal.status === "pending_review");
}

export function rankedIssues(
  issues: Issue[],
  assets: readonly Asset[],
  unit: string,
  review: ReviewFilter,
): Issue[] {
  const byId = new Map(assets.map((asset) => [asset.asset_id, asset]));
  return issues
    .filter(
      (issue) =>
        (unit === "all" || byId.get(issue.asset_id)?.unit_id === unit) &&
        (review === "all" ||
          (review === "open"
            ? issue.assessment === null || !!pendingProposal(issue)
            : !!issue.assessment)),
    )
    .toSorted(
      (a, b) =>
        issuePriority(a).localeCompare(issuePriority(b)) ||
        (byId.get(a.asset_id)?.criticality ?? "C").localeCompare(
          byId.get(b.asset_id)?.criticality ?? "C",
        ) ||
        a.issue_id.localeCompare(b.issue_id),
    );
}

export function condition(issue?: Issue): { label: string; tone: Tone } {
  if (!issue) return { label: "Unassessed", tone: "secondary" };
  if (!issue.assessment) return { label: "Signal", tone: "warning" };
  return {
    needs_attention: { label: "Needs attention", tone: "error" as const },
    watch: { label: "Watch", tone: "warning" as const },
    uncertain: { label: "Uncertain", tone: "secondary" as const },
  }[issue.assessment.condition];
}

export function reviewState(issue?: Issue): { label: string; tone: Tone } | null {
  const latest = issue?.proposals[0];
  if (!latest) return null;
  if (latest.status === "pending_review") return { label: "Awaiting review", tone: "primary" };
  if (latest.status === "approved") return { label: "Draft approved", tone: "success" };
  return { label: "Proposal rejected", tone: "secondary" };
}

export function priorityTone(priority: Priority): Tone {
  return ({ P1: "error", P2: "warning", P3: "secondary", P4: "secondary" } as const)[priority];
}

export const quickActions = {
  investigate: (issue: Issue) =>
    `Investigate the ${issue.asset_id} issue "${issue.title}" and save your assessment.`,
  propose: (issue: Issue) =>
    `Propose work for the ${issue.asset_id} issue based on your assessment.`,
  report: (asset: Asset) => `Create a condition report for ${asset.asset_id}.`,
};

export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: iso.startsWith("2026") ? undefined : "numeric",
    timeZone: "UTC",
  });
}

export function formatMoment(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function messageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .filter((block) => block?.type === "text" && typeof block.text === "string")
    .map((block) => block.text)
    .join("\n")
    .trim();
}

export function artifacts(messages: Message[]): { url: string; label: string; image: boolean }[] {
  const seen = new Set<string>();
  return messages.flatMap((message) => {
    if (message.type !== "tool" || message.name !== "publish_artifact") return [];
    try {
      const item = JSON.parse(messageText(message.content));
      if (typeof item.url !== "string") return [];
      const url = new URL(item.url);
      if (
        url.protocol !== "https:" ||
        !url.hostname.endsWith("--dl.smithbox.dev") ||
        seen.has(item.url)
      )
        return [];
      seen.add(item.url);
      const image = item.content_type?.startsWith("image/") ?? false;
      return [{ url: item.url, label: image ? "Evidence chart" : "Condition report", image }];
    } catch {
      return [];
    }
  });
}

export function errorText(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  if (/401|403|unauthoriz|forbidden/i.test(text))
    return "This key cannot access the agent. Check the LangSmith workspace key.";
  return text;
}

export function writeAssetUrl(asset: string): void {
  const url = new URL(location.href);
  url.searchParams.set("asset", asset);
  history.replaceState(null, "", url);
}
