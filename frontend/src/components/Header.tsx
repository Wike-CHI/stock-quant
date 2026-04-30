interface Props {
  connected: boolean;
  onRefresh: () => void;
  mode: "stock" | "futures";
  onModeChange: (m: "stock" | "futures") => void;
}

const modeBtn = (active: boolean): React.CSSProperties => ({
  padding: "4px 14px", borderRadius: 4, border: active ? "1px solid #58a6ff" : "1px solid #30363d",
  background: active ? "#1e3a5f" : "transparent",
  color: active ? "#58a6ff" : "#8b949e",
  cursor: "pointer", fontSize: 12, fontWeight: active ? 600 : 400,
});

export function Header({ connected, onRefresh, mode, onModeChange }: Props) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "10px 16px", borderBottom: "1px solid #21262d",
      background: "#010409",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <h1 style={{ color: "#58a6ff", fontSize: 16, margin: 0 }}>
          {mode === "stock" ? "A股涨幅规律分析" : "期货行情监控"}
        </h1>
        <span style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 8,
          background: connected ? "#0d3320" : "#3d1f1f",
          color: connected ? "#3fb950" : "#f85149",
        }}>
          {connected ? "WS已连接" : "WS未连接"}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ display: "flex", borderRadius: 4, overflow: "hidden" }}>
          <button style={modeBtn(mode === "stock")} onClick={() => onModeChange("stock")}>
            股票
          </button>
          <button style={modeBtn(mode === "futures")} onClick={() => onModeChange("futures")}>
            期货
          </button>
        </div>
        {mode === "stock" && (
          <button
            onClick={onRefresh}
            style={{
              padding: "4px 12px", borderRadius: 4, border: "1px solid #30363d",
              background: "#21262d", color: "#c9d1d9", cursor: "pointer", fontSize: 13,
            }}
          >
            刷新
          </button>
        )}
      </div>
    </div>
  );
}
