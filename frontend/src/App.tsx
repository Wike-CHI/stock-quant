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
import { DatasetPanel } from "./components/DatasetPanel";
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

const TABS = [
  { key: "pattern", label: "涨幅规律" },
  { key: "kline", label: "K线图表" },
  { key: "dataset", label: "数据集" },
  { key: "backtest", label: "策略回测" },
  { key: "trading", label: "虚拟交易" },
  { key: "predict", label: "AI预测" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const tabStyle = (active: boolean): React.CSSProperties => ({
  padding: "8px 16px",
  cursor: "pointer",
  borderBottom: active ? "2px solid #58a6ff" : "2px solid transparent",
  color: active ? "#58a6ff" : "#8b949e",
  fontWeight: active ? 600 : 400,
  fontSize: 13,
  transition: "color 0.15s, border-color 0.15s",
  whiteSpace: "nowrap",
});

export default function App() {
  const [filter, setFilter] = useState<FilterState>(DEFAULT_FILTER);
  const { stocks, loading, refresh, applyQuotePatch } = useStockList(200, filter);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockInfo | null>(null);
  const { patterns, loading: patternLoading } = usePatternAnalysis(selectedCode);
  const [latestAlert, setLatestAlert] = useState<AlertItem | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("pattern");

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
        <div style={{ width: 520, borderRight: "1px solid #21262d", flexShrink: 0, display: "flex", flexDirection: "column" }}>
          <StockFilter filter={filter} onChange={setFilter} />
          <StockList
            stocks={stocks}
            loading={loading}
            onSelect={handleSelect}
            selectedCode={selectedCode}
          />
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <AlertPanel newAlert={latestAlert} onSelectCode={handleSelect} />
          <div style={{
            display: "flex", gap: 0,
            borderBottom: "1px solid #21262d",
            padding: "0 16px", flexShrink: 0,
          }}>
            {TABS.map(t => (
              <div
                key={t.key}
                role="tab"
                style={tabStyle(activeTab === t.key)}
                onClick={() => setActiveTab(t.key)}
              >
                {t.label}
              </div>
            ))}
          </div>
          <div style={{ flex: 1, overflow: "auto", position: "relative" }}>
            <div style={{ display: activeTab === "pattern" ? "block" : "none" }}>
              <PatternPanel patterns={patterns} loading={patternLoading} selectedCode={selectedCode} />
            </div>
            <div style={{ display: activeTab === "kline" ? "block" : "none" }}>
              <KlineChart code={selectedCode} active={activeTab === "kline"} />
            </div>
            <div style={{ display: activeTab === "dataset" ? "block" : "none" }}>
              <DatasetPanel />
            </div>
            <div style={{ display: activeTab === "backtest" ? "block" : "none" }}>
              <BacktestPanel selectedCode={selectedCode} />
            </div>
            <div style={{ display: activeTab === "trading" ? "block" : "none" }}>
              <TradingPanel selectedCode={selectedCode} selectedName={selectedStock?.name} />
            </div>
            <div style={{ display: activeTab === "predict" ? "block" : "none" }}>
              <PredictionPanel selectedCode={selectedCode} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
