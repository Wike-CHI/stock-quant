import { useState } from "react";

export interface FilterState {
  keyword: string;
  minChange: string;
  maxChange: string;
  minPrice: string;
  maxPrice: string;
  minTurnoverRate: string;
  sortBy: string;
}

interface Props {
  filter: FilterState;
  onChange: (f: FilterState) => void;
}

const PRESETS = [
  { label: "全部", filter: { keyword: "", minChange: "", maxChange: "", minPrice: "", maxPrice: "", minTurnoverRate: "", sortBy: "change_pct" } },
  { label: "涨幅>5%", filter: { keyword: "", minChange: "5", maxChange: "", minPrice: "", maxPrice: "", minTurnoverRate: "", sortBy: "change_pct" } },
  { label: "跌幅>3%", filter: { keyword: "", minChange: "", maxChange: "-3", minPrice: "", maxPrice: "", minTurnoverRate: "", sortBy: "change_pct" } },
  { label: "换手>5%", filter: { keyword: "", minChange: "", maxChange: "", minPrice: "", maxPrice: "", minTurnoverRate: "5", sortBy: "turnover_rate" } },
  { label: "低价股<10", filter: { keyword: "", minChange: "", maxChange: "", minPrice: "", maxPrice: "10", minTurnoverRate: "", sortBy: "price" } },
];

export function StockFilter({ filter, onChange }: Props) {
  const [expanded, setExpanded] = useState(false);

  const update = (partial: Partial<FilterState>) => {
    onChange({ ...filter, ...partial });
  };

  return (
    <div style={{ padding: 8, borderBottom: "1px solid #21262d" }}>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
        {PRESETS.map(p => (
          <button
            key={p.label}
            onClick={() => onChange({ ...p.filter })}
            style={{
              padding: "3px 8px", borderRadius: 4, border: "1px solid #30363d",
              background: "transparent", color: "#8b949e", cursor: "pointer",
              fontSize: 11, whiteSpace: "nowrap",
            }}
          >
            {p.label}
          </button>
        ))}
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            padding: "3px 8px", borderRadius: 4, border: "1px solid #30363d",
            background: expanded ? "#1e3a5f" : "transparent",
            color: expanded ? "#58a6ff" : "#8b949e", cursor: "pointer", fontSize: 11,
          }}
        >
          高级筛选
        </button>
      </div>
      {expanded && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
          <FilterInput label="涨幅>=%" value={filter.minChange} onChange={v => update({ minChange: v })} />
          <FilterInput label="涨幅<=%" value={filter.maxChange} onChange={v => update({ maxChange: v })} />
          <FilterInput label="价格>=" value={filter.minPrice} onChange={v => update({ minPrice: v })} />
          <FilterInput label="价格<=" value={filter.maxPrice} onChange={v => update({ maxPrice: v })} />
          <FilterInput label="换手率>=%" value={filter.minTurnoverRate} onChange={v => update({ minTurnoverRate: v })} />
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ color: "#8b949e", fontSize: 11, whiteSpace: "nowrap" }}>排序</span>
            <select
              value={filter.sortBy}
              onChange={e => update({ sortBy: e.target.value })}
              style={{
                flex: 1, padding: "4px 6px", borderRadius: 4,
                border: "1px solid #444", background: "#1a1a2e", color: "#eee", fontSize: 12,
              }}
            >
              <option value="change_pct">涨跌幅</option>
              <option value="turnover_rate">换手率</option>
              <option value="vol_ratio">量比</option>
              <option value="price">价格</option>
              <option value="turnover">成交额</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ color: "#8b949e", fontSize: 11, whiteSpace: "nowrap" }}>{label}</span>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          width: "100%", padding: "3px 6px", borderRadius: 4,
          border: "1px solid #444", background: "#1a1a2e", color: "#eee", fontSize: 12,
        }}
      />
    </div>
  );
}
