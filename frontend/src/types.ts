export type Priority = "P1" | "P2" | "P3" | "P4";
export type Condition = "needs_attention" | "watch" | "uncertain";
export interface Asset {
  asset_id: string;
  unit_id: string;
  name: string;
  equipment_type: string;
  criticality: "A" | "B" | "C";
}
export interface Evidence {
  reference_id: string;
  kind: "sensor" | "work_order" | "note" | "failure";
  description: string;
}
export interface Signal {
  issue_id: string;
  asset_id: string;
  title: string;
  summary: string;
  priority: Priority;
  category: "condition" | "recurrence" | "data_quality";
  evidence: Evidence[];
  thread_id: string;
}
export interface Assessment {
  assessment_id: string;
  issue_id: string;
  condition: Condition;
  priority: Priority;
  summary: string;
  recommendation: string;
  uncertainty: string;
  evidence_ids: string[];
  assessed_at: string;
  thread_id: string;
}
export interface WorkRequest {
  asset_id: string;
  title: string;
  priority: Priority;
  justification: string;
  tasks: string[];
}
interface ProposalBase {
  proposal_id: string;
  issue_id: string;
  request: WorkRequest;
  created_at: string;
  thread_id: string;
}
interface Review {
  action: "approve" | "reject";
  reason: string;
  reviewed_at: string;
  actor: "workspace_operator";
}
export type Proposal =
  | (ProposalBase & { status: "pending_review" })
  | (ProposalBase & {
      status: "approved";
      review: Review;
      draft: { draft_id: string; submitted_to_cmms: false; synthetic: true; status: "draft" };
    })
  | (ProposalBase & { status: "rejected"; review: Review });
export interface Issue extends Signal {
  assessment: Assessment | null;
  assessment_history: Assessment[];
  proposals: Proposal[];
}
export interface Trend {
  tag: {
    tag_id: string;
    measurement: string;
    unit_of_measure: string;
    alarm_low: number;
    alarm_high: number;
  };
  points: { timestamp: string; value: number; minimum: number; maximum: number; samples: number }[];
}
export interface WorkOrder {
  work_order_id: string;
  status: string;
  opened_at: string;
  completed_at: string | null;
  description: string;
  cost: number;
  hours: number;
}
export interface InspectionNote {
  note_id: string;
  inspected_at: string;
  work_order_id: string | null;
  note: string;
}
export interface AssetDetail {
  asset: Asset;
  trends: Trend[];
  work_orders: WorkOrder[];
  notes: InspectionNote[];
  failures: {
    failure_id: string;
    occurred_at: string;
    root_cause: string;
    failure_mode: string;
    downtime_hours: number;
  }[];
}
export interface Snapshot {
  snapshot_id: string;
  data_as_of: string;
  synthetic: true;
  units: { unit_id: string; name: string }[];
  assets: Asset[];
  signals: Signal[];
}
export interface Workspace extends Omit<Snapshot, "signals"> {
  issues: Issue[];
  selected_asset: AssetDetail | null;
}
export interface Message {
  id?: string;
  type?: string;
  name?: string;
  content: unknown;
  tool_calls?: { name: string; args: unknown }[];
}
export interface AgentState {
  messages?: Message[];
  workspace?: Workspace;
}
export interface WorkInterrupt {
  kind: "work_order_review";
  proposal: Extract<Proposal, { status: "pending_review" }>;
}
export interface LegacyInterrupt {
  action_requests: { name: string; args: WorkRequest }[];
  review_configs: { action_name: string; allowed_decisions: string[] }[];
}
