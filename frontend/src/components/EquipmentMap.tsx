import { Text } from "@langchain/macaw-components/Text";
import { cn } from "@langchain/macaw-components/utils/cn";
import { condition, type Tone } from "../domain";
import type { Issue, Workspace } from "../types";
import { EquipmentGlyph, Mono } from "./ui";

const markerClass: Record<Tone, string> = {
  error: "bg-error-strong",
  warning: "bg-warning-strong",
  success: "bg-success-strong",
  primary: "bg-brand",
  secondary: "bg-surface-level-4",
};

export function EquipmentMap({
  workspace,
  selected,
  onSelect,
}: {
  workspace: Workspace;
  selected: string;
  onSelect: (assetId: string) => void;
}) {
  const issues = new Map<string, Issue>(workspace.issues.map((issue) => [issue.asset_id, issue]));
  return (
    <div className="flex flex-col gap-space-4">
      <div className="flex flex-wrap gap-x-space-3 gap-y-space-1 text-xxs text-secondary">
        <Legend tone="warning" label="Signal or watch" />
        <Legend tone="error" label="Needs attention" />
        <Legend tone="secondary" label="Unassessed" />
      </div>
      {workspace.units.map((unit) => (
        <section key={unit.unit_id} aria-label={unit.name} className="flex flex-col gap-space-2">
          <div className="flex items-baseline gap-space-2">
            <Text variant="sm" weight="semibold" as="h3">
              {unit.unit_id}
            </Text>
            <Text variant="xs" color="tertiary" as="span">
              {unit.name}
            </Text>
          </div>
          <div className="grid grid-cols-4 gap-space-1">
            {workspace.assets
              .filter((asset) => asset.unit_id === unit.unit_id)
              .toSorted((a, b) => a.asset_id.localeCompare(b.asset_id))
              .map((asset) => {
                const issue = issues.get(asset.asset_id);
                const state = condition(issue);
                const active = asset.asset_id === selected;
                return (
                  <button
                    key={asset.asset_id}
                    type="button"
                    aria-label={`${asset.asset_id}, ${asset.name}, ${state.label}`}
                    aria-pressed={active}
                    title={asset.name}
                    onClick={() => onSelect(asset.asset_id)}
                    className={cn(
                      "relative flex flex-col items-center gap-space-1 rounded-md border px-space-1 py-space-2 transition-colors duration-normal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
                      active
                        ? "border-brand bg-selected text-primary"
                        : "border-transparent text-tertiary hover:bg-surface-level-2-hover hover:text-primary",
                      issue && !active && "text-primary",
                    )}
                  >
                    <EquipmentGlyph type={asset.equipment_type} className="h-6 w-8" />
                    <Mono className="text-xxs">{asset.asset_id}</Mono>
                    {issue && (
                      <span
                        aria-hidden
                        className={cn(
                          "absolute right-space-1 top-space-1 size-2 rounded-full",
                          markerClass[state.tone],
                        )}
                      />
                    )}
                  </button>
                );
              })}
          </div>
        </section>
      ))}
      <Text variant="xs" color="tertiary">
        Grouped by process unit. Not a piping diagram.
      </Text>
    </div>
  );
}

function Legend({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className="inline-flex items-center gap-space-1">
      <span aria-hidden className={cn("size-2 rounded-full", markerClass[tone])} />
      {label}
    </span>
  );
}
