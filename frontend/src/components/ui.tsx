import type { ReactNode } from "react";
import { Badge } from "@langchain/macaw-components/Badge";
import { Text } from "@langchain/macaw-components/Text";
import { cn } from "@langchain/macaw-components/utils/cn";
import type { Tone } from "../domain";
import type { Asset } from "../types";

export function ToneBadge({ tone, children }: { tone: Tone; children: string }) {
  return (
    <Badge color={tone} size="sm">
      {children}
    </Badge>
  );
}

export function SectionHeading({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-space-2">
      <Text variant="h6" as="h3" weight="semibold">
        {title}
      </Text>
      {action}
    </div>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-xs", className)}>{children}</span>;
}

export function EquipmentGlyph({
  type,
  className,
}: {
  type: Asset["equipment_type"];
  className?: string;
}) {
  const shared = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  return (
    <svg viewBox="0 0 48 40" aria-hidden className={cn("h-8 w-10", className)}>
      {type === "column" && (
        <g {...shared}>
          <rect x="17" y="2" width="14" height="32" rx="7" />
          <path d="M17 12h14M17 19h14M17 26h14M12 38h24" />
        </g>
      )}
      {type === "exchanger" && (
        <g {...shared}>
          <rect x="4" y="10" width="40" height="18" rx="9" />
          <path d="M12 15l5 8 5-8 5 8 5-8M12 28v6M36 28v6" />
        </g>
      )}
      {type === "compressor" && (
        <g {...shared}>
          <path d="M6 8l36 6v12L6 32z" />
          <circle cx="22" cy="20" r="5" />
          <path d="M4 37h40" />
        </g>
      )}
      {type === "pump" && (
        <g {...shared}>
          <circle cx="18" cy="19" r="11" />
          <path d="M29 15h13v8H29M15 14l7 5-7 5zM8 37h34M11 29l-3 8M25 29l3 8" />
        </g>
      )}
    </svg>
  );
}
