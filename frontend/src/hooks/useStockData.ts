import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "../types";
import type { StockInfo, PatternMatch } from "../types";
import type { FilterState } from "../components/StockFilter";

export function useStockList(limit = 200, filter?: FilterState) {
  const [stocks, setStocks] = useState<StockInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setStocks(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [limit, filter?.keyword, filter?.minChange, filter?.maxChange, filter?.minPrice, filter?.maxPrice, filter?.minTurnoverRate, filter?.sortBy]);

  useEffect(() => { fetchData(); }, [fetchData]);
  return { stocks, loading, error, refresh: fetchData };
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
