import type { Issue, Message, Snapshot, Workspace } from "./types";

export function previewWorkspace(snapshot: Snapshot): Workspace {
  const { signals, ...rest } = snapshot;
  return {
    ...rest,
    selected_asset: null,
    issues: signals.map((signal) => ({
      ...signal,
      assessment: null,
      assessment_history: [],
      proposals: [],
    })),
  };
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

export function rankedIssues(
  issues: Issue[],
  unit: string,
  assetUnits: ReadonlyMap<string, string>,
  review: string,
): Issue[] {
  return issues
    .filter(
      (issue) =>
        (unit === "all" || assetUnits.get(issue.asset_id) === unit) &&
        (review === "all" ||
          (review === "pending"
            ? issue.proposals.some((p) => p.status === "pending_review")
            : issue.assessment !== null)),
    )
    .toSorted(
      (a, b) =>
        (a.assessment?.priority ?? a.priority).localeCompare(
          b.assessment?.priority ?? b.priority,
        ) || a.issue_id.localeCompare(b.issue_id),
    );
}

export function conditionLabel(issue?: Issue): string {
  if (!issue?.assessment) return issue ? "Signal detected" : "Unassessed";
  return { needs_attention: "Needs attention", watch: "Watch", uncertain: "Uncertain" }[
    issue.assessment.condition
  ];
}

export function errorText(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  if (/401|403|unauthoriz|forbidden/i.test(text))
    return "This key cannot access the agent. Check the LangSmith workspace key in connection settings.";
  return text;
}

export function writeAssetUrl(asset: string): void {
  const url = new URL(location.href);
  url.searchParams.set("asset", asset);
  history.replaceState(null, "", url);
}
