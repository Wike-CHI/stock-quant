import { useRef, useState, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { FuturesInfo } from "../types";

interface Props {
  futures: FuturesInfo[];
  loading: boolean;
  onSelect: (code: string, future?: FuturesInfo) => void;
  selectedCode: string | null;
}

function fmtBig(v?: number): string {
  if (!v) return "-";
  if (v >= 10000_0000) return (v / 10000_0000).toFixed(1) + "亿";
  if (v >= 10000) return (v / 10000).toFixed(0) + "万";
  return String(v);
}

const STATUS_COLORS: Record<string, { bg: string; badge: string; text: string }> = {
  limit_up:       { bg: "#3d1111", badge: "#b71c1c", text: "涨停" },
  limit_down:     { bg: "#0d3311", badge: "#1b5e20", text: "跌停" },
  near_limit_up:  { bg: "#2d1810", badge: "#c62828", text: "逼近涨停" },
  near_limit_down:{ bg: "#102018", badge: "#2e7d32", text: "逼近跌停" },
};

export function FuturesList({ futures, loading, onSelect, selectedCode }: Props) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() =>
    filter
      ? futures.filter(f => f.code.includes(filter) || f.name.includes(filter))
      : futures,
    [futures, filter]
  );

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 20,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: 8, borderBottom: "1px solid #333" }}>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="搜索合约代码/名称..."
          style={{
            width: "100%", padding: "6px 10px", borderRadius: 4,
            border: "1px solid #444", background: "#1a1a2e", color: "#eee",
            boxSizing: "border-box",
          }}
        />
      </div>
      <div style={{
        display: "flex", alignItems: "center", padding: "4px 12px",
        background: "#161b22", borderBottom: "1px solid #21262d", fontSize: 10, color: "#8b949e",
      }}>
        <span style={{ width: 90 }}>合约代码</span>
        <span style={{ flex: 1 }}>名称</span>
        <span style={{ width: 70, textAlign: "right" }}>现价</span>
        <span style={{ width: 60, textAlign: "right" }}>涨幅</span>
        <span style={{ width: 70, textAlign: "right" }}>持仓量</span>
        <span style={{ width: 70, textAlign: "right" }}>成交量</span>
      </div>
      <div ref={parentRef} style={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <div style={{ padding: 20, textAlign: "center", color: "#888" }}>加载中...</div>
        ) : (
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map(vRow => {
              const f = filtered[vRow.index];
              const isUp = f.change_pct > 0;
              const isDown = f.change_pct < 0;
              const color = isUp ? "#ef4444" : isDown ? "#22c55e" : "#888";
              const selected = f.code === selectedCode;
              const statusStyle = f.status ? STATUS_COLORS[f.status] : null;

              const rowBg = selected
                ? "#1e3a5f"
                : statusStyle
                  ? statusStyle.bg
                  : vRow.index % 2 === 0
                    ? "#0d1117"
                    : "#161b22";

              return (
                <div
                  key={f.code}
                  onClick={() => onSelect(f.code, f)}
                  style={{
                    position: "absolute", top: vRow.start, left: 0, right: 0,
                    height: vRow.size, display: "flex", alignItems: "center",
                    padding: "0 12px", cursor: "pointer",
                    background: rowBg,
                    borderBottom: "1px solid #21262d", fontSize: 12,
                  }}
                >
                  <span style={{ width: 90, color: "#ff9800", fontFamily: "monospace" }}>
                    {f.code}
                  </span>
                  <span style={{ flex: 1, color: "#c9d1d9", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 6 }}>
                    {f.name}
                    {statusStyle && (
                      <span style={{
                        padding: "1px 5px", borderRadius: 3, fontSize: 10, fontWeight: 700,
                        background: statusStyle.badge, color: "#fff",
                        flexShrink: 0,
                      }}>
                        {statusStyle.text}
                      </span>
                    )}
                  </span>
                  <span style={{ width: 70, textAlign: "right", color, fontWeight: 600 }}>
                    {f.price?.toFixed(2) ?? "--"}
                  </span>
                  <span style={{ width: 60, textAlign: "right", color, fontWeight: 600 }}>
                    {f.change_pct > 0 ? "+" : ""}{f.change_pct?.toFixed(2)}%
                  </span>
                  <span style={{ width: 70, textAlign: "right", color: "#8b949e", fontSize: 11 }}>
                    {fmtBig(f.open_interest)}
                  </span>
                  <span style={{ width: 70, textAlign: "right", color: "#8b949e", fontSize: 11 }}>
                    {fmtBig(f.volume)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
