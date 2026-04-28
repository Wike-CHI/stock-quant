import { useState } from "react";
import { Header } from "./components/Header";
import { StockList } from "./components/StockList";
import { PatternPanel } from "./components/PatternPanel";
import { useStockList, usePatternAnalysis } from "./hooks/useStockData";
import { useWebSocket } from "./hooks/useWebSocket";

interface StockQuote {
  code: string;
  name: string;
  price: number;
  change_pct: number;
}

export default function App() {
  const { stocks, loading, refresh } = useStockList(200);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const { patterns, loading: patternLoading } = usePatternAnalysis(selectedCode);

  const { connected, subscribe } = useWebSocket({
    onMessage(data: unknown) {
      const msg = data as { type: string; data: StockQuote[] };
      if (msg.type === "quotes") {
        // 可在此更新实时行情状态
      }
    },
  });

  const handleSelect = (code: string) => {
    setSelectedCode(code);
    subscribe([code]);
  };

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: "#0d1117", color: "#c9d1d9", fontFamily: "system-ui, sans-serif",
    }}>
      <Header connected={connected} onRefresh={refresh} />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ width: 420, borderRight: "1px solid #21262d", flexShrink: 0 }}>
          <StockList
            stocks={stocks}
            loading={loading}
            onSelect={handleSelect}
            selectedCode={selectedCode}
          />
        </div>
        <div style={{ flex: 1, overflow: "auto" }}>
          <PatternPanel
            patterns={patterns}
            loading={patternLoading}
            selectedCode={selectedCode}
          />
        </div>
      </div>
    </div>
  );
}
