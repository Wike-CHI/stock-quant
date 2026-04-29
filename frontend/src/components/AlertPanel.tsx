import { useEffect, useState, useCallback, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { API_BASE } from "../types";

export interface AlertItem {
  id: string;
  code: string;
  name: string;
  alert_type: string;
  level: "high" | "medium" | "low";
  title: string;
  message: string;
  price: number;
  change_pct: number;
  ts: number;
  ts_ms: number;
  extra: Record<string, unknown>;
}

interface Props {
  newAlert?: AlertItem | null;
  onSelectCode?: (code: string) => void;
}

const LEVEL_COLOR: Record<string, string> = {
  high:   "#ef4444",
  medium: "#f59e0b",
  low:    "#3b82f6",
};

const LEVEL_BG: Record<string, string> = {
  high:   "#2d1515",
  medium: "#2d2215",
  low:    "#152233",
};

function fmtTime(ts: number) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

function requestNotifPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

function sendBrowserNotif(alert: AlertItem) {
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification(alert.title, {
      body: alert.message,
      icon: "/favicon.ico",
      tag: alert.id,
    });
  }
}

export function AlertPanel({ newAlert, onSelectCode }: Props) {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<"all" | "high" | "medium" | "low">("all");
  const [notifEnabled, setNotifEnabled] = useState(
    "Notification" in window && Notification.permission === "granted"
  );
  const prevAlertId = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/alerts?limit=200`);
      if (res.ok) {
        const data: AlertItem[] = await res.json();
        setAlerts(data);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  useEffect(() => {
    if (!newAlert || newAlert.id === prevAlertId.current) return;
    prevAlertId.current = newAlert.id;
    setAlerts(prev => [newAlert, ...prev].slice(0, 500));
    if (notifEnabled) sendBrowserNotif(newAlert);
  }, [newAlert, notifEnabled]);

  const handleEnableNotif = async () => {
    requestNotifPermission();
    const perm = await Notification.requestPermission();
    setNotifEnabled(perm === "granted");
  };

  const handleClear = async () => {
    await fetch(`${API_BASE}/alerts`, { method: "DELETE" });
    setAlerts([]);
  };

  const filtered = filter === "all" ? alerts : alerts.filter(a => a.level === filter);

  const counts = {
    high:   alerts.filter(a => a.level === "high").length,
    medium: alerts.filter(a => a.level === "medium").length,
    low:    alerts.filter(a => a.level === "low").length,
  };

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 88,
    overscan: 10,
  });

  return (
    <div style={{ padding: "12px 16px" }}>
      {/* 标题栏 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>🔔 量化预警</span>
        <span style={{ fontSize: 12, color: "#888" }}>
          共 {alerts.length} 条
        </span>
        <div style={{ flex: 1 }} />
        {"Notification" in window && (
          <button
            onClick={handleEnableNotif}
            style={{
              padding: "3px 10px", borderRadius: 4, fontSize: 12, cursor: "pointer",
              background: notifEnabled ? "#166534" : "#374151",
              color: notifEnabled ? "#86efac" : "#9ca3af",
              border: "1px solid " + (notifEnabled ? "#16a34a" : "#4b5563"),
            }}
          >
            {notifEnabled ? "🔔 通知已开" : "🔕 开启通知"}
          </button>
        )}
        <button
          onClick={loadAlerts}
          style={{
            padding: "3px 10px", borderRadius: 4, fontSize: 12, cursor: "pointer",
            background: "#1e3a5f", color: "#58a6ff", border: "1px solid #1d4ed8",
          }}
        >
          刷新
        </button>
        <button
          onClick={handleClear}
          style={{
            padding: "3px 10px", borderRadius: 4, fontSize: 12, cursor: "pointer",
            background: "#1a1a2e", color: "#6b7280", border: "1px solid #374151",
          }}
        >
          清空
        </button>
      </div>

      {/* 级别过滤 */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {(["all", "high", "medium", "low"] as const).map(lv => (
          <button
            key={lv}
            onClick={() => setFilter(lv)}
            style={{
              padding: "3px 12px", borderRadius: 12, fontSize: 12, cursor: "pointer",
              background: filter === lv ? "#1e3a5f" : "#161b22",
              color: lv === "all" ? "#c9d1d9" : LEVEL_COLOR[lv],
              border: `1px solid ${filter === lv ? "#1d4ed8" : "#21262d"}`,
              fontWeight: filter === lv ? 600 : 400,
            }}
          >
            {lv === "all" ? `全部 (${alerts.length})`
              : lv === "high" ? `高 (${counts.high})`
              : lv === "medium" ? `中 (${counts.medium})`
              : `低 (${counts.low})`}
          </button>
        ))}
      </div>

      {/* 列表 — 虚拟滚动 */}
      {loading ? (
        <div style={{ color: "#888", fontSize: 13, padding: "20px 0", textAlign: "center" }}>加载中...</div>
      ) : filtered.length === 0 ? (
        <div style={{ color: "#555", fontSize: 13, padding: "20px 0", textAlign: "center" }}>
          暂无预警记录，系统每 30 秒自动扫描一次
        </div>
      ) : (
        <div ref={scrollRef} style={{ maxHeight: 400, overflow: "auto" }}>
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map(vItem => {
              const alert = filtered[vItem.index];
              return (
                <div
                  key={alert.id}
                  onClick={() => onSelectCode?.(alert.code)}
                  data-index={vItem.index}
                  ref={virtualizer.measureElement}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${vItem.start}px)`,
                    background: LEVEL_BG[alert.level] ?? "#161b22",
                    border: `1px solid ${LEVEL_COLOR[alert.level]}33`,
                    borderLeft: `3px solid ${LEVEL_COLOR[alert.level]}`,
                    borderRadius: 6,
                    padding: "8px 12px",
                    marginBottom: 6,
                    cursor: onSelectCode ? "pointer" : "default",
                    transition: "opacity 0.15s",
                    boxSizing: "border-box",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: LEVEL_COLOR[alert.level] }}>
                      {alert.title}
                    </span>
                    <span style={{
                      fontSize: 11, padding: "1px 6px", borderRadius: 8,
                      background: `${LEVEL_COLOR[alert.level]}22`,
                      color: LEVEL_COLOR[alert.level],
                    }}>
                      {alert.alert_type.replace("spot_", "").replace("hist_", "").replace(/_/g, " ")}
                    </span>
                    <div style={{ flex: 1 }} />
                    <span style={{ fontSize: 11, color: "#555" }}>{fmtTime(alert.ts)}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.4 }}>
                    {alert.message}
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
                    <span style={{ fontSize: 11, color: "#6b7280" }}>
                      现价 <span style={{ color: "#c9d1d9" }}>{alert.price?.toFixed(2)}</span>
                    </span>
                    <span style={{
                      fontSize: 11,
                      color: alert.change_pct >= 0 ? "#ef4444" : "#22c55e",
                    }}>
                      {alert.change_pct >= 0 ? "+" : ""}{alert.change_pct?.toFixed(2)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
