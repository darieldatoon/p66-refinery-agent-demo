import { GroupedTabs } from "@langchain/macaw-components/GroupedTabs";
import { Select } from "@langchain/macaw-components/Select";
import { Text } from "@langchain/macaw-components/Text";
import { cn } from "@langchain/macaw-components/utils/cn";
import {
  condition,
  issuePriority,
  priorityTone,
  rankedIssues,
  reviewState,
  type ReviewFilter,
} from "../domain";
import type { Workspace } from "../types";
import { Mono, ToneBadge } from "./ui";

export function IssueQueue({
  workspace,
  selected,
  unit,
  review,
  onUnitChange,
  onReviewChange,
  onSelect,
}: {
  workspace: Workspace;
  selected: string;
  unit: string;
  review: ReviewFilter;
  onUnitChange: (unit: string) => void;
  onReviewChange: (review: ReviewFilter) => void;
  onSelect: (assetId: string) => void;
}) {
  const issues = rankedIssues(workspace.issues, workspace.assets, unit, review);
  const names = new Map(workspace.assets.map((asset) => [asset.asset_id, asset.name]));
  return (
    <div className="flex min-h-0 flex-col gap-space-3">
      <div className="flex flex-col gap-space-2">
        <GroupedTabs<ReviewFilter>
          size="sm"
          value={review}
          onChange={onReviewChange}
          options={[
            { value: "all", display: "All" },
            { value: "open", display: "Needs action" },
            { value: "assessed", display: "Assessed" },
          ]}
        />
        <Select
          size="sm"
          aria-label="Process unit"
          hideSearch
          value={unit}
          onChange={(value) => onUnitChange(value ?? "all")}
          options={[
            { value: "all", label: "All units" },
            ...workspace.units.map((item) => ({
              value: item.unit_id,
              label: `${item.unit_id} · ${item.name}`,
            })),
          ]}
        />
      </div>
      <ol className="flex flex-col gap-space-2" aria-label="Issues by priority">
        {issues.map((issue) => {
          const active = issue.asset_id === selected;
          const state = condition(issue);
          const reviewed = reviewState(issue);
          const priority = issuePriority(issue);
          return (
            <li key={issue.issue_id}>
              <button
                type="button"
                aria-pressed={active}
                onClick={() => onSelect(issue.asset_id)}
                className={cn(
                  "flex w-full flex-col gap-space-2 rounded-lg border p-space-3 text-left transition-colors duration-normal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
                  active
                    ? "border-brand bg-selected"
                    : "border-muted bg-surface-level-2 hover:bg-surface-level-2-hover",
                )}
              >
                <span className="flex items-center gap-space-2">
                  <ToneBadge tone={priorityTone(priority)}>{priority}</ToneBadge>
                  <Mono className="text-primary">{issue.asset_id}</Mono>
                  <Text variant="xs" color="tertiary" as="span" className="truncate">
                    {names.get(issue.asset_id)}
                  </Text>
                </span>
                <Text variant="sm" weight="semibold" as="span">
                  {issue.title}
                </Text>
                <span className="flex flex-wrap gap-space-1">
                  <ToneBadge tone={state.tone}>{state.label}</ToneBadge>
                  {reviewed && <ToneBadge tone={reviewed.tone}>{reviewed.label}</ToneBadge>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      {!issues.length && (
        <Text variant="sm" color="tertiary">
          No issues match these filters.
        </Text>
      )}
    </div>
  );
}
