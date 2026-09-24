import type { ReactNode } from "react";
import { Badge } from "@langchain/macaw-components/Badge";
import { Banner } from "@langchain/macaw-components/Banner";
import { Button } from "@langchain/macaw-components/Button";
import { EmptyState } from "@langchain/macaw-components/EmptyState";
import { TabGroup, TabLabel, TabList, TabPanel, TabPanels } from "@langchain/macaw-components/Tabs";
import { Text } from "@langchain/macaw-components/Text";
import { cn } from "@langchain/macaw-components/utils/cn";
import { MagnifyingGlassIcon } from "@phosphor-icons/react/dist/ssr/MagnifyingGlass";
import { ClipboardTextIcon } from "@phosphor-icons/react/dist/ssr/ClipboardText";
import {
  condition,
  formatDay,
  formatMoment,
  issuePriority,
  priorityTone,
  reviewState,
  titleCase,
  type Tone,
} from "../domain";
import type { Asset, AssetDetail as Detail, Issue, Proposal } from "../types";
import { TrendChart } from "./TrendChart";
import { EquipmentGlyph, Mono, SectionHeading, ToneBadge } from "./ui";

const orderTone: Record<string, Tone> = {
  completed: "secondary",
  open: "primary",
  cancelled: "warning",
};

export function AssetDetail({
  asset,
  issue,
  detail,
  connected,
  onInvestigate,
}: {
  asset: Asset;
  issue?: Issue;
  detail?: Detail;
  connected: boolean;
  onInvestigate: () => void;
}) {
  const state = condition(issue);
  const reviewed = reviewState(issue);
  return (
    <section
      aria-label={`${asset.asset_id} details`}
      className="flex min-h-0 flex-col rounded-lg border border-muted bg-surface-level-2"
    >
      <header className="flex flex-wrap items-start gap-space-3 border-b border-muted p-space-5">
        <span className="flex size-12 items-center justify-center rounded-md bg-surface-level-3 text-secondary">
          <EquipmentGlyph type={asset.equipment_type} />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-space-1">
          <div className="flex flex-wrap items-baseline gap-x-space-2">
            <Text variant="h4" as="h2" weight="semibold" className="font-mono">
              {asset.asset_id}
            </Text>
            <Text variant="md" color="secondary" as="span">
              {asset.name}
            </Text>
          </div>
          <Text variant="xs" color="tertiary" as="span">
            {asset.unit_id} · {titleCase(asset.equipment_type)} · Criticality {asset.criticality}
          </Text>
        </div>
        <div className="flex flex-wrap gap-space-1">
          {issue && (
            <ToneBadge tone={priorityTone(issuePriority(issue))}>{issuePriority(issue)}</ToneBadge>
          )}
          <ToneBadge tone={state.tone}>{state.label}</ToneBadge>
          {reviewed && <ToneBadge tone={reviewed.tone}>{reviewed.label}</ToneBadge>}
        </div>
      </header>
      <TabGroup className="flex min-h-0 flex-1 flex-col">
        <TabList className="px-space-5">
          <TabLabel label="Summary" />
          <TabLabel label="Evidence" />
          <TabLabel
            label="Work & Review"
            badgeProps={
              issue?.proposals.length
                ? { children: String(issue.proposals.length), color: "secondary" }
                : undefined
            }
          />
        </TabList>
        <TabPanels className="min-h-0 flex-1 overflow-y-auto">
          <TabPanel className="flex flex-col gap-space-5 p-space-5">
            <Summary
              asset={asset}
              issue={issue}
              detail={detail}
              connected={connected}
              onInvestigate={onInvestigate}
            />
          </TabPanel>
          <TabPanel className="flex flex-col gap-space-6 p-space-5">
            {detail ? (
              <Evidence
                detail={detail}
                cited={issue?.evidence.map((item) => item.reference_id) ?? []}
              />
            ) : (
              <Text color="tertiary">Loading evidence…</Text>
            )}
          </TabPanel>
          <TabPanel className="flex flex-col gap-space-4 p-space-5">
            <WorkReview issue={issue} />
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </section>
  );
}

function Summary({
  asset,
  issue,
  detail,
  connected,
  onInvestigate,
}: {
  asset: Asset;
  issue?: Issue;
  detail?: Detail;
  connected: boolean;
  onInvestigate: () => void;
}) {
  const pressureUnits = new Set(
    detail?.trends
      .filter((t) => t.tag.measurement.includes("pressure"))
      .map((t) => t.tag.unit_of_measure),
  );
  const mixedUnits = pressureUnits.size > 1 && (
    <Banner intent="info" title="Mixed pressure units">
      {`${asset.asset_id} reports pressure in ${[...pressureUnits].join(" and ")}. Convert before comparing tags. This is a data characteristic, not a fault.`}
    </Banner>
  );
  if (!issue)
    return (
      <>
        {mixedUnits}
        <EmptyState
          icon={MagnifyingGlassIcon}
          title="No open signal"
          description="No signal doesn't mean healthy: this equipment hasn't been assessed. Check the evidence, or ask the agent about it."
        />
      </>
    );
  const assessment = issue.assessment;
  return (
    <>
      {mixedUnits}
      <div className="flex flex-col gap-space-2">
        <Text variant="xs" color="tertiary" as="span" weight="medium">
          {assessment ? "AGENT ASSESSMENT" : "DETECTED SIGNAL"}
        </Text>
        <Text variant="h5" as="h3" weight="semibold">
          {issue.title}
        </Text>
        <Text variant="body" color="secondary">
          {issue.summary}
        </Text>
      </div>
      {assessment ? (
        <div className="flex flex-col gap-space-4 rounded-lg border border-muted border-l-brand border-l-2 bg-surface-level-3 p-space-4">
          <div className="flex flex-col gap-space-1">
            <Text variant="xs" color="tertiary" as="span" weight="medium">
              RECOMMENDATION
            </Text>
            <Text variant="md" weight="semibold">
              {assessment.recommendation}
            </Text>
          </div>
          <Text variant="sm">{assessment.summary}</Text>
          <div className="flex flex-col gap-space-1">
            <Text variant="xs" color="tertiary" as="span" weight="medium">
              WHAT REMAINS UNCERTAIN
            </Text>
            <Text variant="sm" color="secondary">
              {assessment.uncertainty}
            </Text>
          </div>
          <div className="flex flex-wrap items-center gap-space-1">
            {assessment.evidence_ids.map((id) => (
              <Badge key={id} color="plain" size="xs" rounded="xs">
                {id}
              </Badge>
            ))}
          </div>
          <Text variant="xs" color="tertiary">
            Saved {formatMoment(assessment.assessed_at)}
            {issue.assessment_history.length > 1 &&
              ` · ${issue.assessment_history.length} assessments on record`}
          </Text>
        </div>
      ) : (
        <EmptyState
          variant="brand"
          icon={ClipboardTextIcon}
          title="Not investigated yet"
          description="The signal is a triage cue, not a diagnosis. The agent checks sensor trends and maintenance records with two specialists, then saves a cited assessment here."
          action={
            <Button size="sm" onClick={onInvestigate}>
              {connected ? "Investigate with the agent" : "Connect the agent to investigate"}
            </Button>
          }
        />
      )}
      <div className="flex flex-col gap-space-2">
        <SectionHeading title="Evidence Behind the Signal" />
        <ul className="flex flex-col divide-y divide-muted rounded-lg border border-muted">
          {issue.evidence.map((item) => (
            <li
              key={item.reference_id}
              className="flex items-center gap-space-3 px-space-4 py-space-3"
            >
              <Mono className="w-28 shrink-0 text-primary">{item.reference_id}</Mono>
              <Text variant="sm" color="secondary" as="span">
                {item.description}
              </Text>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

function Evidence({ detail, cited }: { detail: Detail; cited: string[] }) {
  const rank = (tagId: string) => (cited.includes(tagId) ? cited.indexOf(tagId) : cited.length);
  const trends = detail.trends.toSorted((a, b) => rank(a.tag.tag_id) - rank(b.tag.tag_id));
  return (
    <>
      <div className="flex flex-col gap-space-3">
        <SectionHeading
          title="Sensor Trends"
          action={
            <Text variant="xs" color="tertiary" as="span">
              45 days · native units
            </Text>
          }
        />
        <div className="grid gap-space-3 xl:grid-cols-2">
          {trends.map((trend) => (
            <TrendChart key={trend.tag.tag_id} trend={trend} />
          ))}
        </div>
      </div>
      <Records title="Inspection Notes" empty="No notes recorded.">
        {detail.notes.map((note) => (
          <Row
            key={note.note_id}
            id={note.note_id}
            meta={`${formatDay(note.inspected_at)}${note.work_order_id ? ` · ${note.work_order_id}` : ""}`}
          >
            {note.note}
          </Row>
        ))}
      </Records>
      <Records title="Work Orders" empty="No work orders recorded.">
        {detail.work_orders.map((order) => (
          <Row
            key={order.work_order_id}
            id={order.work_order_id}
            meta={`${order.work_type} · opened ${formatDay(order.opened_at)}`}
            badge={<ToneBadge tone={orderTone[order.status]}>{titleCase(order.status)}</ToneBadge>}
          >
            {order.description}
          </Row>
        ))}
      </Records>
      {detail.failures.length > 0 && (
        <Records title="Recorded Failures" empty="">
          {detail.failures.map((event) => (
            <Row
              key={event.failure_id}
              id={event.failure_id}
              meta={`${formatDay(event.occurred_at)} · ${event.downtime_hours} h downtime`}
            >
              {`${titleCase(event.failure_mode)}. Recorded cause: ${event.root_cause}.`}
            </Row>
          ))}
        </Records>
      )}
      <Records title="Spare Parts" empty="No spares held for this asset.">
        {detail.spare_parts.map((part) => (
          <Row
            key={part.part_id}
            id={part.part_id}
            meta={`Reorder at ${part.reorder_point}`}
            badge={
              <ToneBadge
                tone={
                  part.stock_on_hand < part.reorder_point
                    ? part.stock_on_hand
                      ? "warning"
                      : "error"
                    : "secondary"
                }
              >
                {`${part.stock_on_hand} in stock`}
              </ToneBadge>
            }
          >
            {part.description}
          </Row>
        ))}
      </Records>
    </>
  );
}

function Records({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: ReactNode[];
}) {
  return (
    <div className="flex flex-col gap-space-3">
      <SectionHeading title={title} />
      {children.length ? (
        <ul className="flex flex-col divide-y divide-muted rounded-lg border border-muted">
          {children}
        </ul>
      ) : (
        <Text variant="sm" color="tertiary">
          {empty}
        </Text>
      )}
    </div>
  );
}

function Row({
  id,
  meta,
  badge,
  children,
}: {
  id: string;
  meta: string;
  badge?: ReactNode;
  children: string;
}) {
  return (
    <li className="flex flex-col gap-space-1 px-space-4 py-space-3">
      <span className="flex items-center gap-space-2">
        <Mono className="text-primary">{id}</Mono>
        <Text variant="xs" color="tertiary" as="span" className="flex-1">
          {meta}
        </Text>
        {badge}
      </span>
      <Text variant="sm" color="secondary">
        {children}
      </Text>
    </li>
  );
}

const proposalTone: Record<Proposal["status"], Tone> = {
  pending_review: "primary",
  approved: "success",
  rejected: "secondary",
};

function WorkReview({ issue }: { issue?: Issue }) {
  if (!issue?.proposals.length)
    return (
      <EmptyState
        icon={ClipboardTextIcon}
        title="No work proposed"
        description={
          issue
            ? "After the agent saves an assessment, ask it to propose work. You approve or reject each proposal."
            : "Work proposals are tied to detected signals."
        }
      />
    );
  return (
    <>
      <Text variant="xs" color="tertiary">
        Approval creates a synthetic draft. It never submits to a CMMS or changes equipment
        condition.
      </Text>
      {issue.proposals.map((proposal) => (
        <article
          key={proposal.proposal_id}
          className={cn(
            "flex flex-col gap-space-3 rounded-lg border p-space-4",
            proposal.status === "pending_review" ? "border-brand bg-brand-subtle" : "border-muted",
          )}
        >
          <div className="flex flex-wrap items-center gap-space-2">
            <ToneBadge tone={priorityTone(proposal.request.priority)}>
              {proposal.request.priority}
            </ToneBadge>
            <ToneBadge tone={proposalTone[proposal.status]}>{titleCase(proposal.status)}</ToneBadge>
            <Text variant="xs" color="tertiary" as="span">
              Proposed {formatMoment(proposal.created_at)}
            </Text>
          </div>
          <Text variant="md" weight="semibold" as="h3">
            {proposal.request.title}
          </Text>
          <Text variant="sm" color="secondary">
            {proposal.request.justification}
          </Text>
          <ol className="flex list-decimal flex-col gap-space-1 pl-space-5 text-sm text-primary">
            {proposal.request.tasks.map((task) => (
              <li key={task}>{task}</li>
            ))}
          </ol>
          {proposal.status === "pending_review" ? (
            <Text variant="xs" color="secondary">
              Awaiting your decision in the agent panel.
            </Text>
          ) : (
            <Text variant="xs" color="tertiary">
              {proposal.status === "approved" &&
                `${proposal.draft.draft_id} · not submitted to CMMS · `}
              Reviewed {formatMoment(proposal.review.reviewed_at)}
              {proposal.review.reason && ` · “${proposal.review.reason}”`}
            </Text>
          )}
        </article>
      ))}
    </>
  );
}
