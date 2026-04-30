import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import type { FuturesInfo } from "../types";
import { API_BASE } from "../types";
import { KlineChart } from "./KlineChart";
import { FuturesList } from "./FuturesList";
import { FuturesFilter, DEFAULT_FUTURES_FILTER } from "./FuturesFilter";
import type { FuturesFilterState } from "./FuturesFilter";
import { useWebSocket } from "../hooks/useWebSocket";

function isWsMessage(v: unknown): v is { type: string; data: unknown } {
  return typeof v === "object" && v !== null && "type" in v && "data" in v
    && typeof (v as Record<string, unknown>).type === "string";
}

export function FuturesPage() {
  const [filter, setFilter] = useState<FuturesFilterState>(DEFAULT_FUTURES_FILTER);
  const [futures, setFutures] = useState<FuturesInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [selectedFuture, setSelectedFuture] = useState<FuturesInfo | null>(null);

  const fetchRef = useRef<() => void>(() => {});

  const fetchFutures = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/futures/list`);
      if (!r.ok) throw new Error(r.statusText);
      setFutures(await r.json());
    } catch (e) {
      console.error("Futures fetch failed:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  fetchRef.current = fetchFutures;

  // Initial fetch + 30s polling
  useEffect(() => {
    fetchFutures();
    const timer = setInterval(() => fetchRef.current(), 30000);
    return () => clearInterval(timer);
  }, [fetchFutures]);

  // WebSocket for real-time quote patches
  const { connected, subscribe } = useWebSocket({
    onMessage: useCallback((data: unknown) => {
      if (!isWsMessage(data)) return;
      if (data.type === "quotes" && Array.isArray(data.data)) {
        const patches = data.data as Array<Partial<FuturesInfo>>;
        setFutures(prev => {
          const map = new Map(prev.map(f => [f.code, f]));
          for (const p of patches) {
            if (p.code && map.has(p.code)) {
              Object.assign(map.get(p.code)!, p);
            }
          }
          return [...map.values()];
        });
      }
    }, []),
  });

  // Subscribe selected code for focused real-time updates
  useEffect(() => {
    if (selectedCode) subscribe([selectedCode]);
  }, [selectedCode, subscribe]);

  // Client-side filtering & sorting
  const filtered = useMemo(() => {
    let arr = futures;
    const kw = filter.keyword.trim().toLowerCase();
    if (kw) {
      arr = arr.filter(f =>
        f.code.toLowerCase().includes(kw) ||
        f.name.toLowerCase().includes(kw)
      );
    }
    const minChg = parseFloat(filter.minChange);
    if (!isNaN(minChg)) arr = arr.filter(f => f.change_pct >= minChg);
    const maxChg = parseFloat(filter.maxChange);
    if (!isNaN(maxChg)) arr = arr.filter(f => f.change_pct <= maxChg);
    const minVol = parseFloat(filter.minVolume);
    if (!isNaN(minVol)) arr = arr.filter(f => f.volume >= minVol);
    const minOI = parseFloat(filter.minOpenInterest);
    if (!isNaN(minOI)) arr = arr.filter(f => f.open_interest >= minOI);

    // Exchange filter: map product prefix to exchange
    if (filter.exchange) {
      const EXCHANGE_PRODUCTS: Record<string, string[]> = {
        SHFE: ["CU","AL","ZN","PB","NI","SN","AU","AG","RB","HC","SS","BU","RU","NR","SP","FU","AO","BC"],
        DCE: ["M","Y","P","A","B","C","CS","JD","LH","I","J","JM","EG","EB","PG","PP","V","L"],
        CZCE: ["MA","UR","SA","FG","TA","PF","SM","SF","SR","CF","CY","OI","RM","AP","CJ","PK","SH"],
        CFFEX: ["IF","IC","IH","IM","TS","TF","T","TL"],
        GFEX: ["SI","LC"],
      };
      const products = EXCHANGE_PRODUCTS[filter.exchange] || [];
      arr = arr.filter(f => {
        const prefix = f.code.replace(/[0-9]/g, "").toUpperCase();
        return products.some(p => prefix === p || prefix.startsWith(p));
      });
    }

    const sortKey = filter.sortBy as keyof FuturesInfo;
    arr = [...arr].sort((a, b) => {
      const va = (a[sortKey] as number) ?? 0;
      const vb = (b[sortKey] as number) ?? 0;
      return vb - va;
    });
    return arr;
  }, [futures, filter]);

  const handleSelect = (code: string, future?: FuturesInfo) => {
    setSelectedCode(code);
    setSelectedFuture(future ?? null);
  };

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
      {/* 左侧：筛选 + 列表 */}
      <div style={{
        width: 520, borderRight: "1px solid #21262d",
        flexShrink: 0, display: "flex", flexDirection: "column",
      }}>
        <FuturesFilter filter={filter} onChange={setFilter} />
        <FuturesList
          futures={filtered}
          loading={loading}
          onSelect={handleSelect}
          selectedCode={selectedCode}
        />
      </div>

      {/* 右侧：行情信息 + K线 + 未来可扩展 Tab */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {selectedFuture && (
          <div style={{
            padding: "10px 16px", borderBottom: "1px solid #21262d",
            background: "#161b22", flexShrink: 0,
            display: "flex", alignItems: "center", gap: 16,
          }}>
            <span style={{ color: "#ff9800", fontWeight: 700, fontSize: 15, fontFamily: "monospace" }}>
              {selectedFuture.code}
            </span>
            <span style={{ color: "#c9d1d9" }}>{selectedFuture.name}</span>
            <span style={{
              color: selectedFuture.change_pct >= 0 ? "#ef4444" : "#22c55e",
              fontWeight: 700, fontSize: 16,
            }}>
              {selectedFuture.price?.toFixed(2)}
            </span>
            <span style={{
              color: selectedFuture.change_pct >= 0 ? "#ef4444" : "#22c55e",
              fontSize: 14,
            }}>
              {selectedFuture.change_pct > 0 ? "+" : ""}{selectedFuture.change_pct?.toFixed(2)}%
            </span>
            <span style={{ color: "#8b949e", fontSize: 12 }}>
              昨结 {selectedFuture.prev_close?.toFixed(2)}
            </span>
            <span style={{ color: "#8b949e", fontSize: 12 }}>
              持仓 {selectedFuture.open_interest?.toLocaleString()} 手
            </span>
            <span style={{ color: "#8b949e", fontSize: 12 }}>
              成交 {selectedFuture.volume?.toLocaleString()} 手
            </span>
          </div>
        )}
        <div style={{ flex: 1, overflow: "auto" }}>
          <KlineChart
            code={selectedCode}
            active={true}
            dataSource="futures"
          />
        </div>
      </div>
    </div>
  );
}
