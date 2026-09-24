import { useState } from "react";
import { conditionLabel } from "../domain";
import type { Asset, AssetDetail, Issue } from "../types";
import { TrendChart } from "./TrendChart";

export function IssueDetail({
  asset,
  issue,
  detail,
  loading,
  connected,
}: {
  asset: Asset;
  issue?: Issue;
  detail: AssetDetail | null;
  loading: boolean;
  connected: boolean;
}) {
  const [tab, setTab] = useState("assessment");
  return (
    <section className="detail-panel panel">
      <div className="detail-title">
        <div>
          <span className="eyebrow">SELECTED EQUIPMENT</span>
          <h2>
            {asset.asset_id} <span>{asset.name}</span>
          </h2>
        </div>
        <span className={`status-pill ${issue?.assessment ? "assessed" : ""}`}>
          {conditionLabel(issue)}
        </span>
      </div>
      <div className="asset-meta">
        <span>{asset.unit_id}</span>
        <span>{asset.equipment_type}</span>
        <span>Criticality {asset.criticality}</span>
      </div>
      <div className="tabs" role="tablist" aria-label="Equipment information">
        {["assessment", "evidence", "work"].map((value) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
          >
            {value === "work" ? "Work & review" : value.charAt(0).toUpperCase() + value.slice(1)}
            {value === "work" && !!issue?.proposals.length && <span>{issue.proposals.length}</span>}
          </button>
        ))}
      </div>
      <div className="detail-body" role="tabpanel">
        {tab === "assessment" && (
          <>
            {issue ? (
              <>
                <div className="signal-summary">
                  <span className="eyebrow">
                    {issue.assessment
                      ? "AGENT ASSESSMENT"
                      : "SNAPSHOT SIGNAL · INVESTIGATION NEEDED"}
                  </span>
                  <h3>{issue.title}</h3>
                  <p>{issue.assessment?.summary ?? issue.summary}</p>
                </div>
                {issue.assessment ? (
                  <>
                    <h4>Recommendation</h4>
                    <p className="recommendation">{issue.assessment.recommendation}</p>
                    <div className="uncertainty">
                      <b>What remains uncertain</b>
                      <p>{issue.assessment.uncertainty}</p>
                    </div>
                    <div className="citations">
                      {issue.assessment.evidence_ids.map((id) => (
                        <span key={id}>{id}</span>
                      ))}
                    </div>
                    <p className="muted">
                      Assessed {new Date(issue.assessment.assessed_at).toLocaleString()} ·{" "}
                      {issue.assessment_history.length} saved assessment(s)
                    </p>
                  </>
                ) : (
                  <div className="empty-state">
                    <span className="empty-mark">◎</span>
                    <h4>Start with the evidence</h4>
                    <p>
                      The signal is a starting point. Ask the agent to investigate sensor trends and
                      maintenance history before proposing work.
                    </p>
                  </div>
                )}
                <h4>Evidence to investigate</h4>
                <div className="evidence-list">
                  {issue.evidence.map((item) => (
                    <div key={item.reference_id}>
                      <code>{item.reference_id}</code>
                      <span>{item.description}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <span className="empty-mark">◌</span>
                <h3>No seeded signal for this asset</h3>
                <p>
                  This equipment is unassessed. The absence of a signal does not establish that it
                  is healthy. You can still inspect its evidence and ask the agent questions.
                </p>
                {asset.asset_id === "K-401" && (
                  <p>
                    Pressure tags use both bar and psi. Unit conversion is a data characteristic,
                    not a fault.
                  </p>
                )}
              </div>
            )}
          </>
        )}
        {tab === "evidence" &&
          (loading ? (
            <p className="muted">Loading evidence…</p>
          ) : detail ? (
            <>
              <div className="trend-grid">
                {detail.trends.map((trend) => (
                  <TrendChart key={trend.tag.tag_id} trend={trend} />
                ))}
              </div>
              <h4>Inspection notes</h4>
              {detail.notes.map((note) => (
                <div className="note" key={note.note_id}>
                  <code>{note.note_id}</code>
                  <small>
                    {note.inspected_at.slice(0, 10)}
                    {note.work_order_id && ` · ${note.work_order_id}`}
                  </small>
                  <p>{note.note}</p>
                </div>
              ))}
              <h4>Maintenance history</h4>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Order</th>
                      <th>Status</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.work_orders.map((order) => (
                      <tr key={order.work_order_id}>
                        <td>
                          <code>{order.work_order_id}</code>
                        </td>
                        <td>
                          <span className={`order-status ${order.status}`}>{order.status}</span>
                        </td>
                        <td>{order.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {detail.failures.length > 0 && (
                <>
                  <h4>Recorded failures</h4>
                  {detail.failures.map((event) => (
                    <div className="note" key={event.failure_id}>
                      <code>{event.failure_id}</code>
                      <small>
                        {event.occurred_at.slice(0, 10)} · {event.downtime_hours}h downtime
                      </small>
                      <p>
                        {event.failure_mode} · recorded cause: {event.root_cause}
                      </p>
                    </div>
                  ))}
                </>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>
                {connected
                  ? "Select this asset again to retry loading evidence."
                  : "Connect the agent to inspect sensor and maintenance records."}
              </p>
            </div>
          ))}
        {tab === "work" && (
          <>
            <p className="muted">
              Work approval creates a synthetic draft. Equipment condition remains unchanged.
            </p>
            {issue?.proposals.length ? (
              issue.proposals.map((proposal) => (
                <div className={`work-card ${proposal.status}`} key={proposal.proposal_id}>
                  <div>
                    <span className="priority">{proposal.request.priority}</span>
                    <span className="status-pill">{proposal.status.replaceAll("_", " ")}</span>
                  </div>
                  <h3>{proposal.request.title}</h3>
                  <p>{proposal.request.justification}</p>
                  <ol>
                    {proposal.request.tasks.map((task) => (
                      <li key={task}>{task}</li>
                    ))}
                  </ol>
                  {proposal.status === "approved" && (
                    <code>{proposal.draft.draft_id} · not submitted to CMMS</code>
                  )}
                  {proposal.status !== "pending_review" && (
                    <p className="muted">
                      Reviewed by workspace operator ·{" "}
                      {new Date(proposal.review.reviewed_at).toLocaleString()}
                      {proposal.review.reason && ` · ${proposal.review.reason}`}
                    </p>
                  )}
                  {proposal.status === "pending_review" && (
                    <p>Review this proposal in the agent panel.</p>
                  )}
                </div>
              ))
            ) : (
              <div className="empty-state">
                <span className="empty-mark">↗</span>
                <h4>No work proposed yet</h4>
                <p>
                  Investigate the issue, then ask the agent to prepare a work proposal for review.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
