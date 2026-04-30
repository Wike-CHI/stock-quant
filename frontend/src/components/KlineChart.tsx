import { useEffect, useRef, useState, useCallback } from "react";
import { init, dispose } from "klinecharts";
import { API_BASE } from "../types";

interface Props {
  code: string | null;
  active?: boolean;
}

const PERIODS = [
  { label: "1分", value: "1m", span: 1, type: "minute" as const },
  { label: "5分", value: "5m", span: 5, type: "minute" as const },
  { label: "15分", value: "15m", span: 15, type: "minute" as const },
  { label: "30分", value: "30m", span: 30, type: "minute" as const },
  { label: "60分", value: "60m", span: 60, type: "minute" as const },
  { label: "日", value: "daily", span: 1, type: "day" as const },
  { label: "周", value: "weekly", span: 1, type: "week" as const },
  { label: "月", value: "monthly", span: 1, type: "month" as const },
];

function loadBars(code: string, period: string): Promise<Array<{
  timestamp: number; open: number; high: number; low: number;
  close: number; volume: number; turnover: number;
}>> {
  return globalThis.fetch(`${API_BASE}/stocks/${code}/history?period=${period}`)
    .then(res => res.ok ? res.json() : [])
    .then((data: Array<{ date: string; open: number; close: number; high: number; low: number; volume: number; turnover: number }>) =>
      data.map(d => ({
        timestamp: new Date(d.date.includes("T") ? d.date : d.date + "T00:00:00+08:00").getTime(),
        open: d.open, high: d.high, low: d.low, close: d.close,
        volume: d.volume, turnover: d.turnover,
      }))
    )
    .catch(() => []);
}

export function KlineChart({ code, active = true }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof init> | null>(null);
  const chartIdRef = useRef<string>("");
  const [activePeriod, setActivePeriod] = useState("daily");

  useEffect(() => {
    if (!containerRef.current || !code || !active) return;

    const chartId = `kline-${code}-${Date.now()}`;
    containerRef.current.id = chartId;
    chartIdRef.current = chartId;

    if (chartRef.current) {
      try { dispose(chartIdRef.current); } catch { /* */ }
    }

    const chart = init(chartId);
    if (!chart) return;
    chartRef.current = chart;

    chart.createIndicator("MA", false, { id: "candle_pane" });
    chart.createIndicator("VOL");

    chart.setStyles({
      grid: { horizontal: { color: "rgba(255,255,255,0.04)" }, vertical: { color: "rgba(255,255,255,0.04)" } },
      candle: {
        bar: {
          upColor: "#ef4444", downColor: "#22c55e",
          upBorderColor: "#ef4444", downBorderColor: "#22c55e",
          upWickColor: "#ef4444", downWickColor: "#22c55e",
        },
      },
      xAxis: { axisLine: { color: "#30363d" } },
      yAxis: { axisLine: { color: "#30363d" } },
    });

    chart.setSymbol({ ticker: code });

    const periodConfig = PERIODS.find(p => p.value === activePeriod) || PERIODS[5];
    chart.setPeriod({ span: periodConfig.span, type: periodConfig.type });

    chart.setDataLoader({
      getBars: ({ callback }) => {
        loadBars(code, activePeriod).then(callback);
      },
    });

    return () => {
      try { dispose(chartIdRef.current); } catch { /* */ }
      chartRef.current = null;
      chartIdRef.current = "";
    };
  }, [code, activePeriod, active]);

  const handlePeriodChange = useCallback((period: string) => {
    setActivePeriod(period);
  }, []);

  if (!code) return null;

  return (
    <div style={{ padding: "0 16px", borderTop: "1px solid #21262d" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0 4px" }}>
        <span style={{ color: "#58a6ff", fontSize: 13, fontWeight: 600 }}>{code} K线图</span>
        <div style={{ display: "flex", gap: 2, marginLeft: 8 }}>
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => handlePeriodChange(p.value)}
              style={{
                padding: "2px 8px", borderRadius: 3,
                border: "1px solid #30363d", cursor: "pointer",
                fontSize: 11, lineHeight: "18px",
                background: activePeriod === p.value ? "#1e3a5f" : "transparent",
                color: activePeriod === p.value ? "#58a6ff" : "#8b949e",
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} style={{ width: "100%", height: 320 }} />
    </div>
  );
}
