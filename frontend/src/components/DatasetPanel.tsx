import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "../types";

interface DatasetStats {
  daily_bars: number;
  minute_bars: number;
  stock_count: number;
  date_range: string[];
  recent_collections: Array<{ task_type: string; new_rows: number; collected_at: string }>;
}

interface DailyBar {
  code: string;
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  turnover: number | null;
  change_pct: number | null;
}

const cardStyle: React.CSSProperties = {
  background: "#161b22",
  border: "1px solid #21262d",
  borderRadius: 6,
  padding: "12px 16px",
  minWidth: 120,
};

const valueStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 700,
  color: "#58a6ff",
  lineHeight: 1.2,
};

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: "#8b949e",
  marginTop: 2,
};

const btnStyle = (variant: "primary" | "secondary"): React.CSSProperties => ({
  padding: "6px 14px",
  borderRadius: 4,
  border: variant === "primary" ? "1px solid #58a6ff" : "1px solid #30363d",
  background: variant === "primary" ? "#1e3a5f" : "transparent",
  color: variant === "primary" ? "#58a6ff" : "#c9d1d9",
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 500,
});

export function DatasetPanel() {
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [rows, setRows] = useState<DailyBar[]>([]);
  const [filterCode, setFilterCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [collecting, setCollecting] = useState(false);

  const fetchStats = useCallback(() => {
    fetch(`${API_BASE}/dataset/stats`)
      .then(res => res.ok ? res.json() : null)
      .then(setStats)
      .catch(() => {});
  }, []);

  const fetchData = useCallback(() => {
    const params = new URLSearchParams();
    if (filterCode) params.set("code", filterCode);

    setLoading(true);
    fetch(`${API_BASE}/dataset/query?${params}`)
      .then(res => res.ok ? res.json() : [])
      .then((data: DailyBar[]) => setRows(data.slice(-200)))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [filterCode]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCollect = () => {
    setCollecting(true);
    fetch(`${API_BASE}/dataset/collect`, { method: "POST" })
      .then(() => setTimeout(() => { fetchStats(); setCollecting(false); }, 3000))
      .catch(() => setCollecting(false));
  };

  const handleExport = (format: "csv" | "json") => {
    const base = `${API_BASE}/dataset/export/${format}`;
    const params = new URLSearchParams();
    if (filterCode) params.set("code", filterCode);
    window.open(`${base}?${params}`);
  };

  return (
    <div style={{ padding: 16 }}>
      {/* 统计卡片 */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <div style={cardStyle}>
          <div style={valueStyle}>{stats?.stock_count ?? "-"}</div>
          <div style={labelStyle}>股票数</div>
        </div>
        <div style={cardStyle}>
          <div style={valueStyle}>{stats?.daily_bars?.toLocaleString() ?? "-"}</div>
          <div style={labelStyle}>日线条数</div>
        </div>
        <div style={cardStyle}>
          <div style={valueStyle}>{stats?.minute_bars?.toLocaleString() ?? "-"}</div>
          <div style={labelStyle}>分钟线条数</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#58a6ff", lineHeight: 1.2 }}>
            {stats?.date_range?.length === 2
              ? `${stats.date_range[0]} ~ ${stats.date_range[1]}`
              : "-"}
          </div>
          <div style={labelStyle}>日期范围</div>
        </div>
      </div>

      {/* 操作栏 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <input
          value={filterCode}
          onChange={e => setFilterCode(e.target.value)}
          placeholder="输入股票代码筛选"
          style={{
            padding: "5px 10px", borderRadius: 4, border: "1px solid #30363d",
            background: "#161b22", color: "#c9d1d9", fontSize: 12, width: 160,
            outline: "none",
          }}
        />
        <button style={btnStyle("secondary")} onClick={handleExport("csv")}>
          导出 CSV
        </button>
        <button style={btnStyle("secondary")} onClick={() => handleExport("json")}>
          导出 JSON
        </button>
        <button style={btnStyle("primary")} onClick={handleCollect} disabled={collecting}>
          {collecting ? "采集中..." : "手动采集"}
        </button>
      </div>

      {/* 最近采集日志 */}
      {stats?.recent_collections?.length ? (
        <div style={{ marginBottom: 12, padding: "8px 12px", background: "#161b22", borderRadius: 4, border: "1px solid #21262d" }}>
          <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 4 }}>最近采集记录</div>
          {stats.recent_collections.map((log, i) => (
            <div key={i} style={{ fontSize: 12, color: "#c9d1d9", lineHeight: 1.6 }}>
              <span style={{ color: "#58a6ff" }}>{log.task_type}</span>
              {" "}&middot; 新增 {log.new_rows} 行 &middot; {log.collected_at}
            </div>
          ))}
        </div>
      ) : null}

      {/* 数据浏览表 */}
      <div style={{ border: "1px solid #21262d", borderRadius: 4, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#161b22" }}>
              {["代码", "日期", "开盘", "收盘", "最高", "最低", "成交量", "涨跌幅"].map(h => (
                <th key={h} style={{
                  padding: "6px 10px", textAlign: "left", color: "#8b949e",
                  fontWeight: 500, borderBottom: "1px solid #21262d", whiteSpace: "nowrap",
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: 20, textAlign: "center", color: "#8b949e" }}>加载中...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={8} style={{ padding: 20, textAlign: "center", color: "#8b949e" }}>暂无数据，点击"手动采集"开始</td></tr>
            ) : (
              rows.slice(-50).reverse().map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #21262d" }}>
                  <td style={{ padding: "4px 10px", color: "#58a6ff" }}>{r.code}</td>
                  <td style={{ padding: "4px 10px" }}>{r.date}</td>
                  <td style={{ padding: "4px 10px" }}>{r.open?.toFixed(2)}</td>
                  <td style={{ padding: "4px 10px", color: r.change_pct != null && r.change_pct >= 0 ? "#ef4444" : "#22c55e" }}>
                    {r.close?.toFixed(2)}
                  </td>
                  <td style={{ padding: "4px 10px" }}>{r.high?.toFixed(2)}</td>
                  <td style={{ padding: "4px 10px" }}>{r.low?.toFixed(2)}</td>
                  <td style={{ padding: "4px 10px" }}>{r.volume?.toLocaleString()}</td>
                  <td style={{
                    padding: "4px 10px",
                    color: r.change_pct != null && r.change_pct >= 0 ? "#ef4444" : "#22c55e",
                  }}>
                    {r.change_pct != null ? `${r.change_pct >= 0 ? "+" : ""}${r.change_pct.toFixed(2)}%` : "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
