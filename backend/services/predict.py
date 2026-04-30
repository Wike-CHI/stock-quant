"""深度学习股票趋势预测服务

LSTM 模型预测未来 N 日涨跌概率。
特征：OHLCV + MA/RSI/KDJ/MACD 技术指标。
"""
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler

from services.stock_data import get_stock_history
from services.data_store import load_prediction_cache, save_prediction_cache

logger = logging.getLogger(__name__)

SEQ_LEN = 30
PRED_HORIZONS = [1, 3, 5]
FEATURE_COLS = [
    "open", "high", "low", "close", "volume",
    "ma5", "ma10", "ma20",
    "rsi", "macd", "macd_signal",
    "kdj_k", "kdj_d", "kdj_j",
    "return_1d", "return_5d", "volatility",
]

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "D:/AI/stock-quant/models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_cache: dict[str, tuple[StockLSTM, StandardScaler, float]] = {}


class StockLSTM(nn.Module):
    def __init__(self, input_size: int = len(FEATURE_COLS), hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, len(PRED_HORIZONS)),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    df["ma5"] = c.rolling(5).mean()
    df["ma10"] = c.rolling(10).mean()
    df["ma20"] = c.rolling(20).mean()

    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-8)
    df["rsi"] = 100 - 100 / (1 + rs)

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    low9 = l.rolling(9).min()
    high9 = h.rolling(9).max()
    denom = (high9 - low9).replace(0, 1)
    rsv = (c - low9) / denom * 100
    df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

    df["return_1d"] = c.pct_change(1)
    df["return_5d"] = c.pct_change(5)
    df["volatility"] = c.pct_change().rolling(20).std()

    return df


def _make_sequences(features: np.ndarray, targets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for i in range(len(features) - SEQ_LEN):
        X.append(features[i : i + SEQ_LEN])
        y.append(targets[i + SEQ_LEN])
    return np.array(X), np.array(y)


def _build_targets(df: pd.DataFrame) -> np.ndarray:
    c = df["close"].values
    targets = []
    for horizon in PRED_HORIZONS:
        future = np.roll(c, -horizon)
        targets.append((future > c).astype(float))
    targets = np.array(targets).T
    targets[len(targets) - max(PRED_HORIZONS) :] = 0.5
    return targets


def train_model(code: str, epochs: int = 50, lr: float = 1e-3) -> dict:
    df = get_stock_history(code)
    if len(df) < SEQ_LEN + 60:
        return {"error": f"数据不足: {len(df)} 行"}

    df = _compute_features(df)
    df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)
    if len(df) < SEQ_LEN + 30:
        return {"error": f"有效数据不足: {len(df)} 行"}

    feature_data = df[FEATURE_COLS].values.astype(np.float32)
    targets = _build_targets(df)

    scaler = StandardScaler()
    feature_scaled = scaler.fit_transform(feature_data).astype(np.float32)

    X, y = _make_sequences(feature_scaled, targets)
    if len(X) < 10:
        return {"error": f"序列不足: {len(X)}"}

    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    model = StockLSTM().to(_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCELoss()

    X_t = torch.tensor(X_train, device=_device)
    y_t = torch.tensor(y_train, dtype=torch.float32, device=_device)
    X_v = torch.tensor(X_val, device=_device)
    y_v = torch.tensor(y_val, dtype=torch.float32, device=_device)

    best_loss = float("inf")
    history = []
    for epoch in range(epochs):
        model.train()
        pred = model(X_t)
        loss = loss_fn(pred, y_t)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(X_v), y_v).item()
        history.append({"epoch": epoch + 1, "train_loss": round(loss.item(), 4), "val_loss": round(val_loss, 4)})

        if val_loss < best_loss:
            best_loss = val_loss
            torch.save({"model": model.state_dict(), "scaler_mean": scaler.mean_, "scaler_scale": scaler.scale_}, MODEL_DIR / f"{code}.pt")

    return {
        "code": code,
        "samples": len(X),
        "train_samples": split,
        "val_samples": len(X) - split,
        "best_val_loss": round(best_loss, 4),
        "epochs": epochs,
        "history": history[-10:],
    }


def predict(code: str) -> dict:
    cached = load_prediction_cache(code, max_age_sec=300)
    if cached is not None:
        return cached

    model_path = MODEL_DIR / f"{code}.pt"
    if not model_path.exists():
        return {"error": f"模型未训练: {code}", "need_train": True}

    df = get_stock_history(code)
    if len(df) < SEQ_LEN + 1:
        return {"error": "数据不足"}

    df = _compute_features(df)
    df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)
    if len(df) < SEQ_LEN:
        return {"error": "有效数据不足"}

    mtime = model_path.stat().st_mtime
    cached = _model_cache.get(code)
    if cached and cached[2] == mtime:
        model, scaler, _ = cached
    else:
        ckpt = torch.load(model_path, map_location=_device, weights_only=False)
        model = StockLSTM().to(_device)
        model.load_state_dict(ckpt["model"])
        model.eval()
        scaler = StandardScaler()
        scaler.mean_ = ckpt["scaler_mean"]
        scaler.scale_ = ckpt["scaler_scale"]
        _model_cache[code] = (model, scaler, mtime)

    recent = df[FEATURE_COLS].tail(SEQ_LEN).values.astype(np.float32)
    recent_scaled = scaler.transform(recent)
    X = torch.tensor(recent_scaled[np.newaxis], device=_device)

    with torch.no_grad():
        probs = model(X)[0].cpu().numpy()

    last_close = df["close"].iloc[-1]
    last_date = str(df["date"].iloc[-1])

    predictions = []
    for i, horizon in enumerate(PRED_HORIZONS):
        predictions.append({
            "horizon": horizon,
            "horizon_label": f"{horizon}日",
            "rise_prob": round(float(probs[i]), 3),
            "signal": "看涨" if probs[i] > 0.6 else ("看跌" if probs[i] < 0.4 else "中性"),
        })

    result = {
        "code": code,
        "last_date": last_date,
        "last_close": round(float(last_close), 2),
        "predictions": predictions,
        "model": "LSTM",
    }
    try:
        save_prediction_cache(code, result)
    except Exception:
        pass
    return result


def get_model_status() -> dict:
    models = list(MODEL_DIR.glob("*.pt"))
    return {
        "model_dir": str(MODEL_DIR),
        "saved_models": [p.stem for p in models],
        "device": str(_device),
        "feature_count": len(FEATURE_COLS),
        "seq_len": SEQ_LEN,
        "pred_horizons": PRED_HORIZONS,
    }
