import { useState, useCallback, useRef } from "react";
import { Header } from "./components/Header";
import { StockList } from "./components/StockList";
import { StockFilter } from "./components/StockFilter";
import type { FilterState } from "./components/StockFilter";
import { KlineChart } from "./components/KlineChart";
import { PatternPanel } from "./components/PatternPanel";
import { BacktestPanel } from "./components/BacktestPanel";
import { PredictionPanel } from "./components/PredictionPanel";
import { TradingPanel } from "./components/TradingPanel";
import { AlertPanel } from "./components/AlertPanel";
import type { AlertItem } from "./components/AlertPanel";
import { useStockList, usePatternAnalysis } from "./hooks/useStockData";
import { useWebSocket } from "./hooks/useWebSocket";
import type { StockInfo } from "./types";

function isWsMessage(v: unknown): v is { type: string; data: unknown } {
  return typeof v === "object" && v !== null && "type" in v && "data" in v
    && typeof (v as Record<string, unknown>).type === "string";
}

const DEFAULT_FILTER: FilterState = {
  keyword: "", minChange: "", maxChange: "",
  minPrice: "", maxPrice: "", minTurnoverRate: "", sortBy: "change_pct",
};

export default function App() {
  const [filter, setFilter] = useState<FilterState>(DEFAULT_FILTER);
  const { stocks, loading, refresh, applyQuotePatch } = useStockList(200, filter);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockInfo | null>(null);
  const { patterns, loading: patternLoading } = usePatternAnalysis(selectedCode);
  const [latestAlert, setLatestAlert] = useState<AlertItem | null>(null);

  const applyPatchRef = useRef(applyQuotePatch);
  applyPatchRef.current = applyQuotePatch;

  const { connected, subscribe } = useWebSocket({
    onMessage: useCallback((data: unknown) => {
      if (!isWsMessage(data)) return;
      if (data.type === "quotes" && Array.isArray(data.data)) {
        applyPatchRef.current(data.data as Array<Partial<StockInfo>>);
      } else if (data.type === "alert") {
        setLatestAlert(data.data as AlertItem);
      }
    }, []),
  });

  const handleSelect = (code: string, stock?: StockInfo) => {
    setSelectedCode(code);
    setSelectedStock(stock ?? null);
    subscribe([code]);
  };

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: "#0d1117", color: "#c9d1d9", fontFamily: "system-ui, sans-serif",
    }}>
      <Header connected={connected} onRefresh={refresh} />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ width: 420, borderRight: "1px solid #21262d", flexShrink: 0, display: "flex", flexDirection: "column" }}>
          <StockFilter filter={filter} onChange={setFilter} />
          <StockList
            stocks={stocks}
            loading={loading}
            onSelect={handleSelect}
            selectedCode={selectedCode}
          />
        </div>
        <div style={{ flex: 1, overflow: "auto" }}>
          <AlertPanel newAlert={latestAlert} onSelectCode={handleSelect} />
          <KlineChart code={selectedCode} />
          <PatternPanel
            patterns={patterns}
            loading={patternLoading}
            selectedCode={selectedCode}
          />
          <BacktestPanel selectedCode={selectedCode} />
          <PredictionPanel selectedCode={selectedCode} />
          <TradingPanel
            selectedCode={selectedCode}
            selectedName={selectedStock?.name}
          />
        </div>
      </div>
    </div>
  );
}
