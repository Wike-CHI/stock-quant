import { useState } from "react";
import { API_BASE } from "../types";

interface Props {
  selectedCode: string | null;
}

interface Prediction {
  horizon: number;
  horizon_label: string;
  rise_prob: number;
  signal: string;
}

interface PredResult {
  code: string;
  last_date: string;
  last_close: number;
  predictions: Prediction[];
  model: string;
  error?: string;
  need_train?: boolean;
}

const SIGNAL_COLORS: Record<string, string> = {
  "看涨": "#22c55e",
  "看跌": "#ef4444",
  "中性": "#8b949e",
};

function probBar(prob: number, color: string) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 6, background: "#21262d", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${prob * 100}%`, height: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color: "#c9d1d9", width: 36, textAlign: "right" }}>
        {(prob * 100).toFixed(1)}%
      </span>
    </div>
  );
}

export function PredictionPanel({ selectedCode }: Props) {
  const [result, setResult] = useState<PredResult | null>(null);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<string | null>(null);

  if (!selectedCode) return null;

  const handlePredict = async () => {
    try {
      const res = await fetch(`${API_BASE}/stocks/${selectedCode}/predict`);
      if (!res.ok) {
        setResult({ error: `请求失败 (${res.status})` } as PredResult);
        return;
      }
      setResult(await res.json());
    } catch {
      setResult({ error: "网络错误" } as PredResult);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    setTrainResult(null);
    try {
      const res = await fetch(`${API_BASE}/stocks/${selectedCode}/train?epochs=50`, { method: "POST" });
      if (!res.ok) {
        setTraining(false);
        setTrainResult(`训练请求失败 (${res.status})`);
        return;
      }
      const data = await res.json();
      setTraining(false);
      if (data.error) {
        setTrainResult(`训练失败: ${data.error}`);
      } else {
        setTrainResult(`训练完成: 样本${data.samples}, 损失${data.best_val_loss}`);
        handlePredict();
      }
    } catch {
      setTraining(false);
      setTrainResult("训练请求失败");
    }
  };

  return (
    <div style={{ padding: "12px 16px", borderTop: "1px solid #21262d" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ color: "#58a6ff", fontSize: 13, fontWeight: 600 }}>
          LSTM 趋势预测
        </span>
        <button
          onClick={handlePredict}
          style={{
            padding: "2px 10px", borderRadius: 3, border: "1px solid #30363d",
            background: "#161b22", color: "#58a6ff", cursor: "pointer", fontSize: 11,
          }}
        >
          预测
        </button>
        <button
          onClick={handleTrain}
          disabled={training}
          style={{
            padding: "2px 10px", borderRadius: 3, border: "1px solid #30363d",
            background: training ? "#21262d" : "#161b22",
            color: training ? "#484f58" : "#f0883e", cursor: training ? "wait" : "pointer", fontSize: 11,
          }}
        >
          {training ? "训练中..." : "训练模型"}
        </button>
      </div>

      {trainResult && (
        <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 6 }}>{trainResult}</div>
      )}

      {result?.error && (
        <div style={{ fontSize: 12, color: "#f85149" }}>
          {result.need_train ? "模型未训练，请先点击「训练模型」" : result.error}
        </div>
      )}

      {result?.predictions && (
        <div style={{ display: "flex", gap: 16 }}>
          {result.predictions.map(p => (
            <div key={p.horizon} style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 2 }}>
                {p.horizon_label}趋势
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                <span style={{
                  fontSize: 13, fontWeight: 600,
                  color: SIGNAL_COLORS[p.signal] || "#c9d1d9",
                }}>
                  {p.signal}
                </span>
              </div>
              {probBar(p.rise_prob, SIGNAL_COLORS[p.signal] || "#58a6ff")}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
