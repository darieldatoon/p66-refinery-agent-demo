import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useStream } from "@langchain/react";
import { HumanMessage, type BaseMessage } from "@langchain/core/messages";
import { Button } from "@langchain/macaw-components/Button";
import { EmptyState } from "@langchain/macaw-components/EmptyState";
import { IconButton } from "@langchain/macaw-components/IconButton";
import { Text } from "@langchain/macaw-components/Text";
import { Textarea } from "@langchain/macaw-components/Textarea";
import { ThinkingState } from "@langchain/macaw-components/ThinkingState";
import { cn } from "@langchain/macaw-components/utils/cn";
import { ArrowUpIcon } from "@phosphor-icons/react/dist/ssr/ArrowUp";
import { ArrowSquareOutIcon } from "@phosphor-icons/react/dist/ssr/ArrowSquareOut";
import { AsteriskIcon } from "@phosphor-icons/react/dist/ssr/Asterisk";
import { PlugsIcon } from "@phosphor-icons/react/dist/ssr/Plugs";
import Markdown from "react-markdown";
import { ASSISTANT, createClient } from "../api";
import { artifacts, errorText, messageText, priorityTone, quickActions } from "../domain";
import type { Asset, Issue, LegacyInterrupt, Message, WorkInterrupt } from "../types";
import { ToneBadge } from "./ui";

type ChatState = { messages: BaseMessage[] };
export type AgentAction = "investigate" | "propose" | "report";
export interface AgentRequest {
  assetId: string;
  action: AgentAction;
  nonce: number;
}

export function AgentPanel({
  apiKey,
  asset,
  issue,
  request,
  onRequestHandled,
  onRefresh,
  onConnect,
}: {
  apiKey: string;
  asset: Asset;
  issue?: Issue;
  request?: AgentRequest | null;
  onRequestHandled?: () => void;
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
    <aside
      aria-label="Reliability agent"
      className="flex h-full min-h-0 flex-col rounded-lg border border-muted bg-surface-level-2"
    >
      <header className="flex items-center gap-space-3 border-b border-muted px-space-4 py-space-3">
        <span className="flex size-8 items-center justify-center rounded-md bg-brand-subtle text-icon-brand">
          <AsteriskIcon aria-hidden size={18} weight="bold" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <Text variant="sm" weight="semibold" as="h2">
            Reliability Agent
          </Text>
          <Text variant="xs" color="tertiary" as="span" className="truncate">
            {issue ? `${asset.asset_id} issue thread` : `${asset.asset_id} conversation`}
          </Text>
        </div>
        <span
          aria-label={thread && !error ? "Connected" : "Not connected"}
          className={cn(
            "size-2 rounded-full",
            thread && !error ? "bg-success-strong" : "bg-surface-level-4",
          )}
        />
      </header>
      {!apiKey ? (
        <div className="flex flex-1 items-center justify-center p-space-5">
          <EmptyState
            variant="brand"
            icon={PlugsIcon}
            title="Connect the agent"
            description="Investigate signals with a data analyst and maintenance planner, then review the work it proposes."
            action={
              <Button size="sm" onClick={onConnect}>
                Connect agent
              </Button>
            }
          />
        </div>
      ) : error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-space-3 p-space-5">
          <Text variant="sm" color="error" role="alert">
            {error}
          </Text>
          <Button size="sm" variant="outlined" color="secondary" onClick={onConnect}>
            Connection settings
          </Button>
        </div>
      ) : thread ? (
        <Conversation
          key={thread}
          apiKey={apiKey}
          asset={asset}
          issue={issue}
          threadId={thread}
          request={request}
          onRequestHandled={onRequestHandled}
          onRefresh={onRefresh}
        />
      ) : (
        <div className="flex flex-1 items-center justify-center">
          <ThinkingState label="Opening conversation" />
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
  request,
  onRequestHandled,
  onRefresh,
}: {
  apiKey: string;
  asset: Asset;
  issue?: Issue;
  threadId: string;
  request?: AgentRequest | null;
  onRequestHandled?: () => void;
  onRefresh: () => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [error, setError] = useState("");
  const [finalMessages, setFinalMessages] = useState<Message[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const conversation = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
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
  useLayoutEffect(() => {
    const element = conversation.current;
    if (element && followLatest.current) element.scrollTop = element.scrollHeight;
  }, [messages, busy, review]);
  const customReview =
    review && "kind" in review && review.kind === "work_order_review" ? review : null;
  const legacyReview = review && "action_requests" in review ? review : null;
  const disabled = busy || refreshing || !!review;
  const send = async (text: string) => {
    followLatest.current = true;
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
  const actionText = (action: AgentAction) =>
    action === "report"
      ? quickActions.report(asset)
      : issue
        ? quickActions[action](issue)
        : quickActions.report(asset);
  useEffect(() => {
    if (!request || request.assetId !== asset.asset_id) return;
    // A run or review already in progress absorbs the request instead of queueing another.
    if (stream.isLoading || review) {
      onRequestHandled?.();
      return;
    }
    if (disabled) return;
    onRequestHandled?.();
    void send(actionText(request.action));
    // Only a new request, or the panel becoming free, should trigger a send.
  }, [request?.nonce, disabled]);
  const decide = async (action: "approve" | "reject") => {
    followLatest.current = true;
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
  const steps = messages.filter((message) => message.type === "tool").length;
  const status = busy ? "Working" : refreshing ? "Saving" : review ? "Needs your review" : "Ready";
  return (
    <>
      <div className="flex items-center justify-between border-b border-muted px-space-4 py-space-2">
        <Text variant="xs" color="secondary" as="span" data-testid="agent-status">
          {status}
        </Text>
        <Text variant="xs" color="tertiary" as="span">
          {steps > 0 ? `${steps} tool steps` : "Data analyst · Maintenance planner"}
        </Text>
      </div>
      <div
        ref={conversation}
        className="flex min-h-0 flex-1 flex-col gap-space-4 overflow-y-auto px-space-4 py-space-4"
        data-testid="conversation"
        onScroll={(event) => {
          const element = event.currentTarget;
          followLatest.current =
            element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}
      >
        {!messages.length && (
          <div className="flex flex-col gap-space-2 py-space-4">
            <Text variant="h6" as="h3" weight="semibold">
              {issue ? issue.title : `Ask about ${asset.asset_id}`}
            </Text>
            <Text variant="sm" color="secondary">
              {issue
                ? "Start an investigation. The agent reads trends and maintenance history, explains what it is unsure of, and saves a cited assessment."
                : "Ask about trends, maintenance history or spares. This equipment has no open signal."}
            </Text>
          </div>
        )}
        {messages.map((message, index) => {
          const text = messageText(message.content);
          if (message.type === "tool" || !text) return null;
          const human = message.type === "human";
          return (
            <div
              key={message.id ?? index}
              data-role={message.type}
              className={cn("flex flex-col gap-space-1", human && "items-end")}
            >
              <Text variant="xs" color="tertiary" as="span">
                {human ? "You" : "Agent"}
              </Text>
              <div
                className={cn(
                  "markdown text-sm text-primary",
                  human && "max-w-[85%] rounded-lg bg-surface-level-3 px-space-3 py-space-2",
                )}
              >
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
          <Text variant="sm" color="error" role="alert">
            {error || errorText(stream.error)}
          </Text>
        ) : null}
        {busy && <ThinkingState label="Consulting the specialists" />}
        {review && (
          <section
            aria-labelledby="review-title"
            className="flex flex-col gap-space-3 rounded-lg border border-brand bg-brand-subtle p-space-4"
          >
            <Text variant="xs" color="secondary" as="span" weight="medium">
              YOUR DECISION IS NEEDED
            </Text>
            <Text variant="h6" as="h3" weight="semibold" id="review-title">
              Review proposed work
            </Text>
            {proposed.map((request) => (
              <div key={request.title} className="flex flex-col gap-space-2">
                <div className="flex items-start gap-space-2">
                  <ToneBadge tone={priorityTone(request.priority)}>{request.priority}</ToneBadge>
                  <Text variant="sm" weight="semibold" as="h4">
                    {request.title}
                  </Text>
                </div>
                <Text variant="sm" color="secondary">
                  {request.justification}
                </Text>
                <ol className="flex list-decimal flex-col gap-space-1 pl-space-5 text-sm text-primary">
                  {request.tasks.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ol>
              </div>
            ))}
            <Textarea
              id="review-reason"
              size="md"
              label="Review note (optional)"
              value={reviewReason}
              maxLength={1000}
              rows={2}
              onChange={setReviewReason}
              placeholder="Add a reason or instruction"
            />
            <Text variant="xs" color="tertiary">
              Approval creates a synthetic draft only. Equipment condition stays unchanged.
            </Text>
            <div className="flex gap-space-2">
              <Button
                size="sm"
                disabled={busy || !canDecide("approve")}
                onClick={() => void decide("approve")}
              >
                Approve draft
              </Button>
              <Button
                size="sm"
                variant="outlined"
                color="secondary"
                disabled={busy || !canDecide("reject")}
                onClick={() => void decide("reject")}
              >
                Reject proposal
              </Button>
            </div>
          </section>
        )}
        {published.length > 0 && (
          <div className="flex flex-col gap-space-2">
            <Text variant="xs" color="tertiary" as="span" weight="medium">
              REPORTS
            </Text>
            {published.map((item) => (
              <a
                key={item.url}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between gap-space-2 rounded-md border border-muted px-space-3 py-space-2 text-sm text-link hover:bg-surface-level-2-hover"
              >
                {item.label}
                <ArrowSquareOutIcon aria-hidden size={16} weight="regular" />
              </a>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-space-2 border-t border-muted p-space-3">
        <div className="flex flex-wrap gap-space-2">
          {issue && (
            <Button
              size="sm"
              variant={issue.assessment ? "outlined" : "normal"}
              color={issue.assessment ? "secondary" : "primary"}
              disabled={disabled}
              onClick={() => void send(quickActions.investigate(issue))}
            >
              {issue.assessment ? "Reassess" : "Investigate issue"}
            </Button>
          )}
          {issue?.assessment && (
            <Button
              size="sm"
              disabled={disabled}
              onClick={() => void send(quickActions.propose(issue))}
            >
              Propose work
            </Button>
          )}
          <Button
            size="sm"
            variant="outlined"
            color="secondary"
            disabled={disabled}
            onClick={() => void send(quickActions.report(asset))}
          >
            Create report
          </Button>
        </div>
        <form
          className="flex items-end gap-space-2"
          onSubmit={(event) => {
            event.preventDefault();
            const text = prompt.trim();
            if (text) {
              setPrompt("");
              void send(text);
            }
          }}
        >
          <Textarea
            id="chat-message"
            aria-label="Message the reliability agent"
            size="md"
            className="flex-1"
            rows={1}
            autoResize
            maxHeight={140}
            value={prompt}
            onChange={setPrompt}
            placeholder={review ? "Decide on the proposal first" : "Ask about the evidence"}
            disabled={!!review}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <IconButton
            type="submit"
            icon={ArrowUpIcon}
            label="Send message"
            disabled={disabled || !prompt.trim()}
          />
        </form>
      </div>
    </>
  );
}
