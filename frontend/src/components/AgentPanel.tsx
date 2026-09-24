import { useEffect, useMemo, useState } from "react";
import { AsteriskIcon } from "@phosphor-icons/react";
import { useStream } from "@langchain/react";
import { HumanMessage, type BaseMessage } from "@langchain/core/messages";
import { Button } from "@langchain/macaw-components/Button";
import { ThinkingState } from "@langchain/macaw-components/ThinkingState";
import Markdown from "react-markdown";
import { ASSISTANT, createClient } from "../api";
import { artifacts, errorText, messageText } from "../domain";
import type { Asset, Issue, LegacyInterrupt, Message, WorkInterrupt } from "../types";

type ChatState = { messages: BaseMessage[] };

export function AgentPanel({
  apiKey,
  asset,
  issue,
  onRefresh,
  onConnect,
}: {
  apiKey: string;
  asset: Asset;
  issue?: Issue;
  onRefresh: () => void;
  onConnect: () => void;
}) {
  const client = useMemo(() => createClient(apiKey), [apiKey]);
  const [thread, setThread] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!apiKey) return;
    let active = true;
    setThread(null);
    setError("");
    const stored = sessionStorage.getItem(`refinery-thread:${asset.asset_id}`);
    client.threads
      .create({
        threadId: issue?.thread_id ?? stored ?? undefined,
        ifExists: "do_nothing",
        metadata: {
          source: "refinery-workspace",
          asset: asset.asset_id,
          ...(issue ? { issue_id: issue.issue_id } : {}),
        },
      })
      .then((result) => {
        if (active) {
          setThread(result.thread_id);
          if (!issue) sessionStorage.setItem(`refinery-thread:${asset.asset_id}`, result.thread_id);
        }
      })
      .catch((cause) => {
        if (active) setError(errorText(cause));
      });
    return () => {
      active = false;
    };
  }, [apiKey, client, asset.asset_id, issue?.thread_id, issue?.issue_id]);
  return (
    <aside className="agent-panel panel">
      <div className="agent-heading">
        <div className="agent-orb">
          <AsteriskIcon size={24} />
        </div>
        <div>
          <h2>Reliability agent</h2>
          <p>
            {issue ? "Issue investigation" : "Equipment conversation"} · {asset.asset_id}
          </p>
        </div>
        <span className={`connection-dot ${thread && !error ? "online" : ""}`} />
      </div>
      {!apiKey ? (
        <div className="agent-welcome">
          <span className="big-orb">
            <AsteriskIcon size={65} />
          </span>
          <h3>
            A second set of eyes
            <br />
            on your refinery.
          </h3>
          <p>Investigate the evidence, challenge a recommendation, and decide what happens next.</p>
          <Button onClick={onConnect}>Connect agent</Button>
          <small>Use your LangSmith workspace API key.</small>
        </div>
      ) : error ? (
        <div className="agent-welcome">
          <p className="error" role="alert">
            {error}
          </p>
          <Button onClick={onConnect}>Connection settings</Button>
        </div>
      ) : thread ? (
        <Conversation
          key={thread}
          apiKey={apiKey}
          asset={asset}
          issue={issue}
          threadId={thread}
          onRefresh={onRefresh}
        />
      ) : (
        <div className="agent-welcome">
          <ThinkingState label="Opening investigation…" />
        </div>
      )}
    </aside>
  );
}

function Conversation({
  apiKey,
  asset,
  issue,
  threadId,
  onRefresh,
}: {
  apiKey: string;
  asset: Asset;
  issue?: Issue;
  threadId: string;
  onRefresh: () => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [error, setError] = useState("");
  const [finalMessages, setFinalMessages] = useState<Message[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const client = useMemo(() => createClient(apiKey), [apiKey]);
  const stream = useStream<ChatState>({ client, assistantId: ASSISTANT, threadId });
  const busy = stream.isLoading || stream.isThreadLoading;
  const config = {
    configurable: { issue_id: issue?.issue_id ?? null, asset_id: asset.asset_id },
    recursion_limit: 60,
  };
  useEffect(() => {
    if (busy) {
      setFinalMessages(null);
      return;
    }
    let active = true;
    setRefreshing(true);
    // Stream projections can omit middleware rewrites; use the saved final checkpoint.
    client.threads
      .getState<ChatState>(threadId)
      .then((state) => {
        if (active) {
          setFinalMessages(state.values.messages ?? []);
          onRefresh();
        }
      })
      .catch((cause) => {
        if (active) setError(errorText(cause));
      })
      .finally(() => {
        if (active) setRefreshing(false);
      });
    return () => {
      active = false;
    };
  }, [busy, threadId, client, onRefresh]);
  const messages = busy
    ? stream.messages
    : (finalMessages ?? stream.values.messages ?? stream.messages);
  const published = artifacts(messages);
  const review = stream.interrupt?.value as WorkInterrupt | LegacyInterrupt | undefined;
  const customReview =
    review && "kind" in review && review.kind === "work_order_review" ? review : null;
  const legacyReview = review && "action_requests" in review ? review : null;
  const disabled = busy || refreshing || !!review;
  const send = async (text: string) => {
    setError("");
    try {
      await stream.submit(
        { messages: [new HumanMessage(text)] },
        {
          config,
          metadata: {
            source: "refinery-workspace",
            asset: asset.asset_id,
            unit: asset.unit_id,
            requester_role: "reliability-engineer",
            issue_id: issue?.issue_id,
          },
          multitaskStrategy: "reject",
        },
      );
    } catch (cause) {
      setError(errorText(cause));
    }
  };
  const decide = async (action: "approve" | "reject") => {
    setError("");
    const response = customReview
      ? { action, reason: reviewReason }
      : {
          decisions: legacyReview?.action_requests.map(() =>
            action === "approve"
              ? { type: action }
              : { type: action, message: reviewReason || "Operator rejected this draft." },
          ),
        };
    try {
      await stream.respond(response, { interruptId: stream.interrupt?.id, config });
      setReviewReason("");
    } catch (cause) {
      setError(errorText(cause));
    }
  };
  const canDecide = (action: "approve" | "reject") =>
    !!customReview ||
    !!legacyReview?.action_requests.every((request) =>
      legacyReview.review_configs.some(
        (reviewConfig) =>
          reviewConfig.action_name === request.name &&
          reviewConfig.allowed_decisions.includes(action),
      ),
    );
  const proposed = customReview
    ? [customReview.proposal.request]
    : (legacyReview?.action_requests.map((action) => action.args) ?? []);
  const toolCount = messages.filter((message) => message.type === "tool").length;
  return (
    <>
      <div className="agent-toolbar">
        <span className="thread-state" data-testid="agent-status">
          {busy
            ? "Investigating…"
            : refreshing
              ? "Saving final view…"
              : review
                ? "Awaiting your review"
                : "Ready"}
        </span>
        <span>{toolCount > 0 ? `${toolCount} evidence steps` : "2 specialists available"}</span>
      </div>
      <div className="agent-conversation" data-testid="conversation">
        {!messages.length && (
          <div className="conversation-intro">
            <span className="eyebrow">LET’S INVESTIGATE</span>
            <h3>{issue?.title ?? `Understand ${asset.asset_id}`}</h3>
            <p>
              I can bring together sensor trends and maintenance records, explain uncertainty, and
              prepare work for your review.
            </p>
          </div>
        )}
        {messages.map((message, index) => {
          const text = messageText(message.content);
          if (message.type === "tool" || !text) return null;
          return (
            <div
              key={message.id ?? index}
              className={`chat-message ${message.type === "human" ? "human" : "assistant"}`}
              data-role={message.type}
            >
              <span className="message-author">
                {message.type === "human" ? "You" : "Reliability agent"}
              </span>
              <div className="markdown">
                <Markdown
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {text}
                </Markdown>
              </div>
            </div>
          );
        })}
        {error || stream.error ? (
          <p role="alert" className="error">
            {error || errorText(stream.error)}
          </p>
        ) : null}
        {busy && (
          <div className="thinking">
            <ThinkingState label="Reviewing evidence…" />
            <span>Sensor analyst + maintenance planner</span>
          </div>
        )}
        {review && (
          <div className="approval-card">
            <span className="eyebrow">YOUR REVIEW IS REQUIRED</span>
            <h3>Review proposed work</h3>
            {proposed.map((request) => (
              <div key={request.title}>
                <span className="priority">{request.priority}</span>
                <h4>{request.title}</h4>
                <p>{request.justification}</p>
                <ol>
                  {request.tasks.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ol>
              </div>
            ))}
            <label htmlFor="review-reason">
              Review note <span>(optional)</span>
            </label>
            <textarea
              id="review-reason"
              value={reviewReason}
              maxLength={1000}
              onChange={(event) => setReviewReason(event.target.value)}
              placeholder="Add a reason or instruction…"
            />
            <p className="approval-disclaimer">
              Creates a synthetic draft only. Equipment condition stays unchanged.
            </p>
            <div className="approval-actions">
              <Button
                disabled={busy || !canDecide("approve")}
                onClick={() => void decide("approve")}
              >
                Approve draft
              </Button>
              <Button
                variant="outlined"
                color="secondary"
                disabled={busy || !canDecide("reject")}
                onClick={() => void decide("reject")}
              >
                Reject proposal
              </Button>
            </div>
          </div>
        )}
        {published.length > 0 && (
          <div className="artifact-list">
            <span className="eyebrow">REPORTS & ARTIFACTS</span>
            {published.map((item) => (
              <a key={item.url} href={item.url} target="_blank" rel="noopener noreferrer">
                <span>{item.image ? "▧" : "▤"}</span>
                <div>
                  <strong>{item.label}</strong>
                  <small>Open published artifact</small>
                </div>
                <span>↗</span>
              </a>
            ))}
          </div>
        )}
      </div>
      <div className="agent-bottom">
        <div className="quick-prompts">
          {issue && (
            <button
              disabled={disabled}
              onClick={() =>
                void send(
                  `Investigate issue ${issue.issue_id} for ${asset.asset_id}. Read get_issue_evidence, consult both specialists, then call record_issue_assessment with an evidence-backed recommendation, priority, condition and uncertainty. Keep the answer concise. Do not create a report or propose work yet.`,
                )
              }
            >
              {issue.assessment ? "Reassess issue" : "Investigate issue"}
            </button>
          )}
          {issue?.assessment && (
            <button
              disabled={disabled}
              onClick={() =>
                void send(
                  `Prepare a specific work proposal for issue ${issue.issue_id} based on the saved assessment. Use propose_issue_work and pause for my review. Do not claim approval or create an artifact.`,
                )
              }
            >
              Propose work
            </button>
          )}
          <button
            disabled={disabled}
            onClick={() =>
              void send(
                `Create and publish a self-contained HTML condition report for ${asset.asset_id} from the actual fixture evidence. Label it synthetic and fixed at 2026-09-23 12:00 UTC. Do not propose work.`,
              )
            }
          >
            Create report
          </button>
        </div>
        <form
          className="chat-compose"
          onSubmit={(event) => {
            event.preventDefault();
            const text = prompt.trim();
            if (text) {
              setPrompt("");
              void send(text);
            }
          }}
        >
          <label htmlFor="chat-message" className="sr-only">
            Message the reliability agent
          </label>
          <textarea
            id="chat-message"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask about the evidence or recommendation…"
            disabled={!!review}
          />
          <Button type="submit" disabled={disabled || !prompt.trim()} aria-label="Send message">
            ↑
          </Button>
        </form>
        <p className="chat-footer">Synthetic data · human decisions · no equipment control</p>
      </div>
    </>
  );
}
