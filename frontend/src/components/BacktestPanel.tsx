import { useState } from "react";
import { API_BASE } from "../types";

interface BacktestResult {
  code: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  end_market_value: number;
  total_trades: number;
  win_rate: number;
}

interface Props {
  selectedCode: string | null;
}

export function BacktestPanel({ selectedCode }: Props) {
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    if (!selectedCode) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await globalThis.fetch(`${API_BASE}/backtest/${selectedCode}`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!selectedCode) return null;

  const MetricCard = ({ label, value, color }: { label: string; value: string; color: string }) => (
    <div style={{ background: "#161b22", borderRadius: 6, padding: "12px 16px", flex: "1 1 140px" }}>
      <div style={{ color: "#8b949e", fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ color, fontSize: 18, fontWeight: 600 }}>{value}</div>
    </div>
  );

  return (
    <div style={{ padding: 16, borderTop: "1px solid #21262d" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h4 style={{ color: "#58a6ff", fontSize: 14, margin: 0 }}>AKQuant 策略回测</h4>
        <button
          onClick={runBacktest}
          disabled={loading}
          style={{
            padding: "6px 16px", borderRadius: 4, border: "1px solid #30363d",
            background: loading ? "#21262d" : "#238636", color: "#fff",
            cursor: loading ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 600,
          }}
        >
          {loading ? "回测中..." : "开始回测"}
        </button>
      </div>

      {error && <div style={{ color: "#f85149", fontSize: 13, marginBottom: 8 }}>{error}</div>}

      {result && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <MetricCard
            label="总收益率"
            value={`${result.total_return_pct > 0 ? "+" : ""}${result.total_return_pct}%`}
            color={result.total_return_pct >= 0 ? "#3fb950" : "#f85149"}
          />
          <MetricCard label="夏普比率" value={result.sharpe_ratio.toFixed(2)} color="#58a6ff" />
          <MetricCard
            label="最大回撤"
            value={`${result.max_drawdown_pct}%`}
            color={result.max_drawdown_pct > -10 ? "#3fb950" : "#f85149"}
          />
          <MetricCard label="终值" value={`${(result.end_market_value / 10000).toFixed(2)}万`} color="#c9d1d9" />
          <MetricCard label="交易次数" value={`${result.total_trades}`} color="#c9d1d9" />
          <MetricCard
            label="胜率"
            value={`${result.win_rate}%`}
            color={result.win_rate >= 50 ? "#3fb950" : "#eab308"}
          />
        </div>
      )}
    </div>
  );
}
