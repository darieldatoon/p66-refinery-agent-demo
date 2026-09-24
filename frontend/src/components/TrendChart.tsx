import type { Trend } from "../types";

export function TrendChart({ trend }: { trend: Trend }) {
  const values = trend.points.map((point) => point.value);
  const low = Math.min(...values, trend.tag.alarm_low) * 0.9;
  const high = Math.max(...values, trend.tag.alarm_high) * 1.08;
  const y = (value: number) => 137 - ((value - low) / Math.max(high - low, 1)) * 113;
  const points = values
    .map((value, index) => `${42 + (index / Math.max(values.length - 1, 1)) * 390},${y(value)}`)
    .join(" ");
  return (
    <div className="trend-card">
      <div className="trend-heading">
        <div>
          <strong>{trend.tag.measurement.replaceAll("_", " ")}</strong>
          <small>{trend.tag.tag_id}</small>
        </div>
        <div>
          <b>{values.at(-1)?.toFixed(2)}</b>
          <small>{trend.tag.unit_of_measure}</small>
        </div>
      </div>
      <svg
        viewBox="0 0 450 170"
        role="img"
        aria-label={`${trend.tag.tag_id}, 45-day daily means in ${trend.tag.unit_of_measure}. Latest ${values.at(-1)?.toFixed(2)}. High alarm ${trend.tag.alarm_high}.`}
      >
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <line
              x1="42"
              x2="432"
              y1={24 + i * 37}
              y2={24 + i * 37}
              stroke="var(--map-border)"
              strokeDasharray="2 4"
            />
            <text x="33" y={28 + i * 37} textAnchor="end">
              {(high - ((high - low) * i) / 3).toFixed(1)}
            </text>
          </g>
        ))}
        <line
          x1="42"
          x2="432"
          y1={y(trend.tag.alarm_high)}
          y2={y(trend.tag.alarm_high)}
          stroke="#bd8050"
          strokeDasharray="5 4"
        />
        <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
        <text x="42" y="160">
          {trend.points[0]?.timestamp}
        </text>
        <text x="432" y="160" textAnchor="end">
          {trend.points.at(-1)?.timestamp}
        </text>
      </svg>
      <p>
        Daily mean · dashed line: configured high alarm {trend.tag.alarm_high}{" "}
        {trend.tag.unit_of_measure}
      </p>
    </div>
  );
}
