import { useEffect, useRef, useState } from "react";
import { init, dispose } from "klinecharts";
import { API_BASE } from "../types";

interface Props {
  code: string | null;
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

export function KlineChart({ code }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof init> | null>(null);
  const [activePeriod, setActivePeriod] = useState("daily");

  useEffect(() => {
    if (!containerRef.current || !code) return;

    const chartId = `kline-${code}`;
    containerRef.current.id = chartId;

    if (chartRef.current) {
      try { dispose(chartId); } catch { /* */ }
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
        globalThis.fetch(`${API_BASE}/stocks/${code}/history?period=${activePeriod}`)
          .then(res => res.ok ? res.json() : [])
          .then((data: Array<{ date: string; open: number; close: number; high: number; low: number; volume: number; turnover: number }>) => {
            const bars = data.map(d => ({
              timestamp: new Date(d.date).getTime(),
              open: d.open, high: d.high, low: d.low, close: d.close,
              volume: d.volume, turnover: d.turnover,
            }));
            callback(bars);
          })
          .catch(() => callback([]));
      },
    });

    return () => {
      try { dispose(chartId); } catch { /* */ }
      chartRef.current = null;
    };
  }, [code, activePeriod]);

  if (!code) return null;

  return (
    <div style={{ padding: "0 16px", borderTop: "1px solid #21262d" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0 4px" }}>
        <span style={{ color: "#58a6ff", fontSize: 13, fontWeight: 600 }}>{code} K线图</span>
        <div style={{ display: "flex", gap: 2, marginLeft: 8 }}>
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setActivePeriod(p.value)}
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
