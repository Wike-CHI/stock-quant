import { useRef, useCallback, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { StockInfo } from "../types";

interface Props {
  stocks: StockInfo[];
  loading: boolean;
  onSelect: (code: string) => void;
  selectedCode: string | null;
}

export function StockList({ stocks, loading, onSelect, selectedCode }: Props) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState("");

  const filtered = filter
    ? stocks.filter(s =>
        s.code.includes(filter) || s.name.includes(filter)
      )
    : stocks;

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
          placeholder="搜索代码/名称..."
          style={{
            width: "100%", padding: "6px 10px", borderRadius: 4,
            border: "1px solid #444", background: "#1a1a2e", color: "#eee",
            boxSizing: "border-box",
          }}
        />
      </div>
      <div ref={parentRef} style={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <div style={{ padding: 20, textAlign: "center", color: "#888" }}>加载中...</div>
        ) : (
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map(vRow => {
              const stock = filtered[vRow.index];
              const isUp = stock.change_pct > 0;
              const isDown = stock.change_pct < 0;
              const color = isUp ? "#ef4444" : isDown ? "#22c55e" : "#888";
              const selected = stock.code === selectedCode;

              return (
                <div
                  key={stock.code}
                  onClick={() => onSelect(stock.code)}
                  style={{
                    position: "absolute", top: vRow.start, left: 0, right: 0,
                    height: vRow.size, display: "flex", alignItems: "center",
                    padding: "0 12px", cursor: "pointer",
                    background: selected ? "#1e3a5f" : vRow.index % 2 === 0 ? "#0d1117" : "#161b22",
                    borderBottom: "1px solid #21262d",
                  }}
                >
                  <span style={{ width: 80, color: "#58a6ff", fontFamily: "monospace" }}>
                    {stock.code}
                  </span>
                  <span style={{ flex: 1, color: "#c9d1d9", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {stock.name}
                  </span>
                  <span style={{ width: 90, textAlign: "right", color, fontWeight: 600 }}>
                    {stock.price?.toFixed(2) ?? "--"}
                  </span>
                  <span style={{ width: 80, textAlign: "right", color, fontWeight: 600 }}>
                    {stock.change_pct > 0 ? "+" : ""}{stock.change_pct?.toFixed(2)}%
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
