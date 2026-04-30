export interface FuturesFilterState {
  keyword: string;
  minChange: string;
  maxChange: string;
  minVolume: string;
  minOpenInterest: string;
  exchange: string;
  sortBy: string;
}

interface Props {
  filter: FuturesFilterState;
  onChange: (f: FuturesFilterState) => void;
}

const EXCHANGES = [
  { value: "", label: "全部交易所" },
  { value: "SHFE", label: "上期所" },
  { value: "DCE", label: "大商所" },
  { value: "CZCE", label: "郑商所" },
  { value: "CFFEX", label: "中金所" },
  { value: "GFEX", label: "广期所" },
];

const SORT_OPTIONS = [
  { value: "change_pct", label: "涨幅" },
  { value: "volume", label: "成交量" },
  { value: "open_interest", label: "持仓量" },
];

export const DEFAULT_FUTURES_FILTER: FuturesFilterState = {
  keyword: "", minChange: "", maxChange: "",
  minVolume: "", minOpenInterest: "", exchange: "", sortBy: "change_pct",
};

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "3px 6px", borderRadius: 3,
  border: "1px solid #30363d", background: "#0d1117", color: "#c9d1d9",
  fontSize: 11, boxSizing: "border-box",
};

const labelStyle: React.CSSProperties = {
  fontSize: 10, color: "#8b949e", marginBottom: 2,
};

export function FuturesFilter({ filter, onChange }: Props) {
  const set = (k: keyof FuturesFilterState, v: string) =>
    onChange({ ...filter, [k]: v });

  return (
    <div style={{
      padding: "8px 10px", borderBottom: "1px solid #21262d",
      display: "flex", flexWrap: "wrap", gap: 6, alignItems: "flex-end",
    }}>
      <div style={{ flex: "1 1 100px", minWidth: 80 }}>
        <div style={labelStyle}>合约/名称</div>
        <input
          style={inputStyle}
          value={filter.keyword}
          onChange={e => set("keyword", e.target.value)}
          placeholder="搜索..."
        />
      </div>
      <div style={{ width: 55 }}>
        <div style={labelStyle}>涨幅≥</div>
        <input
          style={inputStyle} type="number"
          value={filter.minChange}
          onChange={e => set("minChange", e.target.value)}
        />
      </div>
      <div style={{ width: 55 }}>
        <div style={labelStyle}>涨幅≤</div>
        <input
          style={inputStyle} type="number"
          value={filter.maxChange}
          onChange={e => set("maxChange", e.target.value)}
        />
      </div>
      <div style={{ width: 70 }}>
        <div style={labelStyle}>成交量≥</div>
        <input
          style={inputStyle} type="number"
          value={filter.minVolume}
          onChange={e => set("minVolume", e.target.value)}
          placeholder="手"
        />
      </div>
      <div style={{ width: 70 }}>
        <div style={labelStyle}>持仓量≥</div>
        <input
          style={inputStyle} type="number"
          value={filter.minOpenInterest}
          onChange={e => set("minOpenInterest", e.target.value)}
          placeholder="手"
        />
      </div>
      <div style={{ width: 80 }}>
        <div style={labelStyle}>交易所</div>
        <select
          style={{ ...inputStyle, cursor: "pointer" }}
          value={filter.exchange}
          onChange={e => set("exchange", e.target.value)}
        >
          {EXCHANGES.map(e => (
            <option key={e.value} value={e.value}>{e.label}</option>
          ))}
        </select>
      </div>
      <div style={{ width: 65 }}>
        <div style={labelStyle}>排序</div>
        <select
          style={{ ...inputStyle, cursor: "pointer" }}
          value={filter.sortBy}
          onChange={e => set("sortBy", e.target.value)}
        >
          {SORT_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
