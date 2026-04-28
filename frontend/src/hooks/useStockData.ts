import { useEffect, useState, useCallback } from "react";
import { API_BASE, StockInfo, PatternMatch } from "../types";

export function useStockList(limit = 50) {
  const [stocks, setStocks] = useState<StockInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/top-gainers?limit=${limit}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStocks(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => { fetch(); }, [fetch]);
  return { stocks, loading, error, refresh: fetch };
}

export function usePatternAnalysis(code: string | null) {
  const [patterns, setPatterns] = useState<PatternMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) { setPatterns([]); return; }
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/stocks/${code}/pattern`)
      .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`)))
      .then(setPatterns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [code]);

  return { patterns, loading, error };
}
