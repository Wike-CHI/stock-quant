import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "../types";

interface Position {
  code: string; name: string;
  quantity: number; available: number;
  avg_cost: number; latest_price: number;
  market_value: number; profit: number; profit_pct: number;
}

interface AccountInfo {
  cash: number; total_assets: number;
  total_profit: number; total_profit_pct: number;
  positions: Position[];
}

interface Props {
  selectedCode: string | null;
  selectedName?: string;
}

export function TradingPanel({ selectedCode, selectedName = "" }: Props) {
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [quantity, setQuantity] = useState(100);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const fetchAccount = useCallback(async () => {
    try {
      const res = await globalThis.fetch(`${API_BASE}/trading/account`);
      if (res.ok) setAccount(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchAccount(); }, [fetchAccount]);

  const trade = async (side: "buy" | "sell") => {
    if (!selectedCode) return;
    setLoading(true);
    setMessage(null);
    try {
      const res = await globalThis.fetch(`${API_BASE}/trading/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: selectedCode, name: selectedName,
          side, quantity, price: 0, // 0=市价
        }),
      });
      const data = await res.json();
      setMessage({
        text: data.status === "filled"
          ? `${side === "buy" ? "买入" : "卖出"}成功 ${data.filled_price?.toFixed(2)} × ${quantity}`
          : `失败：${data.reason}`,
        ok: data.status === "filled",
      });
      fetchAccount();
    } catch (e) {
      setMessage({ text: `请求失败：${(e as Error).message}`, ok: false });
    } finally {
      setLoading(false);
    }
  };

  const pos = account?.positions.find(p => p.code === selectedCode);
  const buyDisabled = loading || !selectedCode;
  const sellDisabled = loading || !pos || pos.available < quantity;

  if (!selectedCode) return null;

  const btn = (side: "buy" | "sell", label: string, color: string, disabled: boolean) => (
    <button
      onClick={() => trade(side)}
      disabled={disabled}
      style={{
        flex: 1, padding: "8px 0", border: "none", borderRadius: 4,
        background: disabled ? "#21262d" : color, color: "#fff",
        cursor: disabled ? "not-allowed" : "pointer", fontWeight: 600, fontSize: 14,
      }}
    >
      {label} {quantity}股
    </button>
  );

  return (
    <div style={{ padding: 16, borderTop: "1px solid #21262d" }}>
      <h4 style={{ color: "#58a6ff", fontSize: 14, margin: "0 0 12px" }}>虚拟交易</h4>

      {account && (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <Stat label="总资产" value={`${(account.total_assets / 10000).toFixed(2)}万`} />
          <Stat label="现金" value={`${(account.cash / 10000).toFixed(2)}万`} />
          <Stat
            label="总盈亏"
            value={`${account.total_profit > 0 ? "+" : ""}${account.total_profit.toFixed(0)} (${account.total_profit_pct.toFixed(2)}%)`}
            color={account.total_profit >= 0 ? "#3fb950" : "#f85149"}
          />
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ color: "#8b949e", fontSize: 13 }}>数量：</span>
        {[100, 200, 500, 1000].map(n => (
          <button key={n} onClick={() => setQuantity(n)} style={{
            padding: "3px 10px", borderRadius: 4, border: "1px solid",
            borderColor: quantity === n ? "#58a6ff" : "#30363d",
            background: quantity === n ? "#1a3a5c" : "transparent",
            color: quantity === n ? "#58a6ff" : "#8b949e",
            cursor: "pointer", fontSize: 12,
          }}>{n}</button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        {btn("buy", "买入", "#da3633", buyDisabled)}
        {btn("sell", "卖出", "#238636", sellDisabled)}
      </div>

      {pos && (
        <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>
          持仓 {pos.quantity}股（可卖{pos.available}）· 成本{pos.avg_cost} ·
          盈亏 <span style={{ color: pos.profit >= 0 ? "#3fb950" : "#f85149" }}>
            {pos.profit >= 0 ? "+" : ""}{pos.profit.toFixed(0)} ({pos.profit_pct.toFixed(2)}%)
          </span>
        </div>
      )}

      {message && (
        <div style={{
          fontSize: 13, padding: "6px 10px", borderRadius: 4, marginTop: 4,
          background: message.ok ? "#0d3320" : "#3d1f1f",
          color: message.ok ? "#3fb950" : "#f85149",
        }}>
          {message.text}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: "#161b22", borderRadius: 4, padding: "6px 12px" }}>
      <div style={{ color: "#8b949e", fontSize: 11 }}>{label}</div>
      <div style={{ color: color || "#c9d1d9", fontSize: 14, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
