import { PatternMatch, PATTERN_LABELS } from "../types";

interface Props {
  patterns: PatternMatch[];
  loading: boolean;
  selectedCode: string | null;
}

const CONFIDENCE_COLOR = (c: number) =>
  c >= 0.8 ? "#22c55e" : c >= 0.5 ? "#eab308" : "#888";

export function PatternPanel({ patterns, loading, selectedCode }: Props) {
  if (!selectedCode) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#555" }}>
        点击左侧股票查看涨幅规律分析
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#888" }}>
        分析中...
      </div>
    );
  }

  if (patterns.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#888" }}>
        未检测到明显涨幅规律
      </div>
    );
  }

  const grouped = patterns.reduce<Record<string, PatternMatch[]>>((acc, p) => {
    (acc[p.pattern_type] ??= []).push(p);
    return acc;
  }, {});

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ color: "#c9d1d9", marginBottom: 16 }}>
        {selectedCode} 涨幅规律分析
      </h3>
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type} style={{ marginBottom: 20 }}>
          <h4 style={{ color: "#58a6ff", marginBottom: 8, fontSize: 14 }}>
            {PATTERN_LABELS[type] ?? type} ({items.length})
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {items.map((p, i) => (
              <div
                key={i}
                style={{
                  background: "#161b22", borderRadius: 6, padding: "10px 14px",
                  borderLeft: `3px solid ${CONFIDENCE_COLOR(p.confidence)}`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: "#c9d1d9", fontSize: 13 }}>{p.description}</span>
                  <span style={{ color: CONFIDENCE_COLOR(p.confidence), fontSize: 12, fontWeight: 600 }}>
                    置信度 {(p.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ color: "#8b949e", fontSize: 12, marginTop: 4 }}>
                  {p.start_date} ~ {p.end_date}
                  {p.rise_probability > 0 && (
                    <span style={{ color: "#eab308", marginLeft: 12 }}>
                      上涨概率 {(p.rise_probability * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
