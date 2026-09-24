import { LineChart, type LineChartSeries } from "@langchain/macaw-components/LineChart";
import { Text } from "@langchain/macaw-components/Text";
import {
  CHART_STATUS_COLORS,
  getCategoricalLineChartColor,
} from "@langchain/macaw-components/utils/chartColors";
import { titleCase } from "../domain";
import type { Trend } from "../types";
import { Mono } from "./ui";

const day = (timestamp: string) => Date.parse(`${timestamp}T00:00:00Z`);
const formatDay = (value: number) =>
  new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

export function TrendChart({ trend }: { trend: Trend }) {
  const { tag, points } = trend;
  const latest = points.at(-1);
  const values = points.flatMap((point) => [point.minimum, point.maximum]);
  const low = Math.min(...values, tag.alarm_low > 0 ? tag.alarm_low : Infinity);
  const high = Math.max(...values, tag.alarm_high);
  const pad = (high - low) * 0.08 || 1;
  const domain: [number, number] = [Math.max(0, low - pad), high + pad];
  const series: LineChartSeries[] = [
    {
      id: "mean",
      label: "Daily mean",
      color: getCategoricalLineChartColor(0),
      strokeWidth: 2,
      points: points.map((point) => ({ x: day(point.timestamp), y: point.value })),
    },
    {
      id: "max",
      label: "Daily max",
      color: getCategoricalLineChartColor(0),
      strokeWidth: 1,
      opacity: 0.35,
      showActiveMarker: false,
      points: points.map((point) => ({ x: day(point.timestamp), y: point.maximum })),
    },
    {
      id: "alarm",
      label: "High alarm",
      color: CHART_STATUS_COLORS.negative,
      strokeDasharray: "4 4",
      strokeWidth: 1,
      showActiveMarker: false,
      points: [points[0], latest].flatMap((point) =>
        point ? [{ x: day(point.timestamp), y: tag.alarm_high }] : [],
      ),
    },
  ];
  const digits =
    Math.abs(latest?.value ?? 0) >= 100 ? 0 : Math.abs(latest?.value ?? 0) >= 10 ? 1 : 2;
  return (
    <figure className="flex flex-col gap-space-2 rounded-lg border border-muted bg-surface-level-2 p-space-3">
      <figcaption className="flex items-start justify-between gap-space-2">
        <span className="flex flex-col">
          <Text variant="sm" weight="semibold" as="span">
            {titleCase(tag.measurement)}
          </Text>
          <Mono className="text-tertiary">{tag.tag_id}</Mono>
        </span>
        <span className="flex items-baseline gap-space-1 text-right">
          <Text variant="h5" weight="semibold" as="span">
            {latest ? latest.value.toFixed(digits) : "—"}
          </Text>
          <Text variant="xs" color="tertiary" as="span">
            {tag.unit_of_measure}
          </Text>
        </span>
      </figcaption>
      <div className="h-36">
        <LineChart
          aria-label={`${tag.tag_id} daily mean and maximum in ${tag.unit_of_measure}, 45 days. High alarm ${tag.alarm_high} ${tag.unit_of_measure}.`}
          series={series}
          showLegend={false}
          shouldAnimate={false}
          formatXValue={formatDay}
          xTickCount={3}
          yAxes={[
            {
              id: "value",
              domain,
              tickCount: 3,
              formatValue: (value) => value.toFixed(high >= 100 ? 0 : 1),
            },
          ]}
          yBands={[
            { id: "high-alarm", from: tag.alarm_high, color: "var(--bg-error)", opacity: 0.6 },
            ...(tag.alarm_low > 0
              ? [{ id: "low-alarm", to: tag.alarm_low, color: "var(--bg-error)", opacity: 0.6 }]
              : []),
          ]}
          grid={{ rows: true, columns: false }}
        />
      </div>
      <Text variant="xs" color="tertiary">
        Alarm {tag.alarm_low > 0 ? `below ${tag.alarm_low} or ` : ""}above {tag.alarm_high}{" "}
        {tag.unit_of_measure}
      </Text>
    </figure>
  );
}
