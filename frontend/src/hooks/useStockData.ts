import { useEffect, useState, useCallback, useRef } from "react";
import { API_BASE } from "../types";
import type { StockInfo, PatternMatch } from "../types";
import type { FilterState } from "../components/StockFilter";

const POLL_INTERVAL = 30_000; // 30 秒自动轮询

export function useStockList(limit = 200, filter?: FilterState) {
  const [stocks, setStocks] = useState<StockInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 用 Map 维护实时行情，key = code
  const quoteMapRef = useRef<Map<string, Partial<StockInfo>>>(new Map());

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (filter) {
        if (filter.keyword) params.set("keyword", filter.keyword);
        if (filter.minChange) params.set("min_change", filter.minChange);
        if (filter.maxChange) params.set("max_change", filter.maxChange);
        if (filter.minPrice) params.set("min_price", filter.minPrice);
        if (filter.maxPrice) params.set("max_price", filter.maxPrice);
        if (filter.minTurnoverRate) params.set("min_turnover_rate", filter.minTurnoverRate);
        if (filter.sortBy) params.set("sort_by", filter.sortBy);
      }
      const res = await globalThis.fetch(`${API_BASE}/stocks?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: StockInfo[] = await res.json();

      // 合并已有实时 patch
      const map = quoteMapRef.current;
      const merged = data.map(s => {
        const patch = map.get(s.code);
        return patch ? { ...s, ...patch } : s;
      });
      setStocks(merged);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [limit, filter?.keyword, filter?.minChange, filter?.maxChange,
      filter?.minPrice, filter?.maxPrice, filter?.minTurnoverRate, filter?.sortBy]);

  // 初始加载
  useEffect(() => { fetchData(); }, [fetchData]);

  // 30 秒自动轮询
  useEffect(() => {
    const timer = setInterval(() => { fetchData(); }, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchData]);

  /**
   * 接收 WS diff patch，就地更新 stocks 数组。
   * patch 每条只包含发生变化的字段 + code。
   */
  const applyQuotePatch = useCallback((patches: Array<Partial<StockInfo>>) => {
    if (!patches.length) return;

    // 更新 quoteMap
    const map = quoteMapRef.current;
    for (const patch of patches) {
      if (!patch.code) continue;
      const existing = map.get(patch.code) ?? {};
      map.set(patch.code, { ...existing, ...patch });
    }

    // 就地 merge 到 stocks（避免全量 re-render）
    const patchMap = new Map(patches.map(p => [p.code, p]));
    setStocks(prev => {
      let changed = false;
      const next = prev.map(s => {
        const p = patchMap.get(s.code);
        if (!p) return s;
        changed = true;
        return { ...s, ...p };
      });
      return changed ? next : prev;
    });
  }, []);

  return { stocks, loading, error, refresh: fetchData, applyQuotePatch };
}

export function usePatternAnalysis(code: string | null) {
  const [patterns, setPatterns] = useState<PatternMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) { setPatterns([]); return; }
    setLoading(true);
    setError(null);
    globalThis.fetch(`${API_BASE}/stocks/${code}/pattern`)
      .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`)))
      .then(setPatterns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [code]);

  return { patterns, loading, error };
}
