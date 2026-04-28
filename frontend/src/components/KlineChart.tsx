import { useEffect, useRef } from "react";
import { init, dispose } from "klinecharts";
import { API_BASE } from "../types";

interface Props {
  code: string | null;
}

export function KlineChart({ code }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !code) return;

    const chartId = `kline-${code}`;
    containerRef.current.id = chartId;

    const chart = init(chartId);
    if (!chart) return;

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
    chart.setPeriod({ span: 1, type: "day" });
    chart.setDataLoader({
      getBars: ({ callback }) => {
        globalThis.fetch(`${API_BASE}/stocks/${code}/history`)
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
      dispose(chartId);
    };
  }, [code]);

  if (!code) return null;

  return (
    <div style={{ padding: "0 16px", borderTop: "1px solid #21262d" }}>
      <div style={{ padding: "8px 0 4px" }}>
        <span style={{ color: "#58a6ff", fontSize: 13, fontWeight: 600 }}>{code} K线图</span>
      </div>
      <div ref={containerRef} style={{ width: "100%", height: 320 }} />
    </div>
  );
}
