interface Props {
  connected: boolean;
  onRefresh: () => void;
}

export function Header({ connected, onRefresh }: Props) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "10px 16px", borderBottom: "1px solid #21262d",
      background: "#010409",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <h1 style={{ color: "#58a6ff", fontSize: 16, margin: 0 }}>
          A股涨幅规律分析
        </h1>
        <span style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 8,
          background: connected ? "#0d3320" : "#3d1f1f",
          color: connected ? "#3fb950" : "#f85149",
        }}>
          {connected ? "WS已连接" : "WS未连接"}
        </span>
      </div>
      <button
        onClick={onRefresh}
        style={{
          padding: "4px 12px", borderRadius: 4, border: "1px solid #30363d",
          background: "#21262d", color: "#c9d1d9", cursor: "pointer", fontSize: 13,
        }}
      >
        刷新
      </button>
    </div>
  );
}
