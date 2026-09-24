import type { Asset, Issue, Workspace } from "../types";
import { conditionLabel } from "../domain";

function Equipment({ asset, x, y }: { asset: Asset; x: number; y: number }) {
  const color = "currentColor";
  if (asset.equipment_type === "column")
    return (
      <g transform={`translate(${x},${y})`}>
        <rect
          x="-9"
          y="-27"
          width="18"
          height="52"
          rx="8"
          fill="var(--equipment-fill)"
          stroke={color}
        />
        <path d="M-9-13H9M-9 0H9M-9 13H9M-13 28H13" stroke={color} fill="none" />
      </g>
    );
  if (asset.equipment_type === "exchanger")
    return (
      <g transform={`translate(${x},${y})`}>
        <rect
          x="-22"
          y="-12"
          width="44"
          height="24"
          rx="12"
          fill="var(--equipment-fill)"
          stroke={color}
        />
        <path d="M-13-6L-5 6 3-6 11 6M-14 13V20M14 13V20" fill="none" stroke={color} />
      </g>
    );
  if (asset.equipment_type === "compressor")
    return (
      <g transform={`translate(${x},${y})`}>
        <path d="M-21-16L21-10V10L-21 16ZM-25 20H25" fill="var(--equipment-fill)" stroke={color} />
        <circle r="7" fill="none" stroke={color} />
      </g>
    );
  return (
    <g transform={`translate(${x},${y})`}>
      <circle cx="-4" r="15" fill="var(--equipment-fill)" stroke={color} />
      <path
        d="M-15 19H23M-13 10L-15 19M5 10L8 19M10-5H25V5H10M-4-5L3 0-4 5Z"
        fill="var(--equipment-fill)"
        stroke={color}
      />
    </g>
  );
}

export function RefineryMap({
  workspace,
  selected,
  onSelect,
}: {
  workspace: Workspace;
  selected: string;
  onSelect: (id: string) => void;
}) {
  const units = ["CDU", "FCC", "HDT"];
  const issues = new Map<string, Issue>(workspace.issues.map((issue) => [issue.asset_id, issue]));
  return (
    <div className="schematic-wrap">
      <svg
        viewBox="0 0 940 430"
        role="group"
        aria-label="Refinery equipment grouped by process unit"
        className="schematic"
      >
        <defs>
          <pattern id="grid" width="18" height="18" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r=".7" fill="#d8ded4" />
          </pattern>
        </defs>
        <rect width="940" height="430" fill="url(#grid)" />
        {units.map((unit, index) => {
          const assets = workspace.assets.filter((asset) => asset.unit_id === unit);
          const origin = 18 + index * 309;
          return (
            <g key={unit}>
              <rect
                x={origin}
                y="18"
                width="288"
                height="387"
                rx="14"
                fill="var(--map-unit)"
                stroke="var(--map-border)"
              />
              <text x={origin + 18} y="47" className="unit-id">
                {unit}
              </text>
              <text x={origin + 18} y="67" className="unit-name">
                {workspace.units.find((u) => u.unit_id === unit)?.name}
              </text>
              <path d={`M${origin + 18} 82H${origin + 270}`} stroke="var(--map-border)" />
              {assets.map((asset, assetIndex) => {
                const x = origin + 50 + (assetIndex % 3) * 93;
                const y = 124 + Math.floor(assetIndex / 3) * 61;
                const issue = issues.get(asset.asset_id);
                const active = selected === asset.asset_id;
                const state = issue?.assessment?.condition ?? (issue ? "signal" : "unassessed");
                return (
                  <g
                    key={asset.asset_id}
                    role="button"
                    tabIndex={0}
                    aria-label={`${asset.asset_id}, ${asset.name}, ${conditionLabel(issue)}`}
                    aria-pressed={active}
                    onClick={() => onSelect(asset.asset_id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelect(asset.asset_id);
                      }
                    }}
                    className={`map-asset ${state} ${active ? "selected" : ""}`}
                  >
                    <rect
                      x={x - 39}
                      y={y - 30}
                      width="78"
                      height="60"
                      rx="8"
                      className="asset-hit"
                    />
                    <Equipment asset={asset} x={x} y={y - 6} />
                    {issue && <circle cx={x + 25} cy={y - 22} r="4" className="asset-dot" />}
                    <text x={x} y={y + 25} textAnchor="middle" className="asset-id">
                      {asset.asset_id}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <div className="map-legend">
        <span>
          <i className="dot amber" /> Snapshot signal
        </span>
        <span>
          <i className="dot teal" /> Agent assessed
        </span>
        <span>
          <i className="dot gray" /> Unassessed
        </span>
        <span className="map-note">Schematic grouping · not physical topology</span>
      </div>
    </div>
  );
}
