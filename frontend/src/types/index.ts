export interface StockInfo {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  turnover: number;
  high: number;
  low: number;
  open: number;
  prev_close: number;
  buy_vol?: number;
  sell_vol?: number;
  turnover_rate?: number;
  vol_ratio?: number;
  pe?: number;
  pb?: number;
  total_mv?: number;
  circ_mv?: number;
}

export interface PatternMatch {
  code: string;
  name: string;
  pattern_type: string;
  confidence: number;
  description: string;
  start_date: string;
  end_date: string;
  rise_probability: number;
  details: Record<string, unknown>;
}

export const WS_URL = `ws://${window.location.hostname}:8000/ws`;
export const API_BASE = `http://${window.location.hostname}:8000/api`;

export const PATTERN_LABELS: Record<string, string> = {
  limit_up_streak: "连板模式",
  ma_bullish_alignment: "均线多头",
  volume_breakout: "放量突破",
  shrinkage_bounce: "缩量反弹",
  v_shape_reversal: "V型反转",
  bowl_rebound: "碗底反弹",
};
