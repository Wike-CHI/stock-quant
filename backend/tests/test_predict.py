"""predict 模块单元测试"""
import numpy as np
import pandas as pd
import pytest

from services.predict import (
    SEQ_LEN, PRED_HORIZONS, FEATURE_COLS,
    _compute_features, _build_targets, _make_sequences,
    StockLSTM, get_model_status,
)


def _make_df(n=200):
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)
    base = 10.0
    close = base + np.cumsum(np.random.randn(n) * 0.3)
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": close + np.random.randn(n) * 0.1,
        "close": close,
        "high": close + abs(np.random.randn(n) * 0.2),
        "low": close - abs(np.random.randn(n) * 0.2),
        "volume": np.random.randint(100000, 500000, n),
        "turnover": np.random.uniform(1e6, 5e6, n),
    })


class TestFeatureEngineering:
    def test_compute_features_adds_all_columns(self):
        df = _make_df(200)
        result = _compute_features(df)
        for col in FEATURE_COLS:
            assert col in result.columns, f"缺少特征列: {col}"

    def test_compute_features_drops_nan_rows(self):
        df = _make_df(200)
        result = _compute_features(df).dropna()
        assert len(result) > 150

    def test_rsi_range(self):
        df = _make_df(200)
        result = _compute_features(df).dropna()
        assert result["rsi"].between(0, 100).all()

    def test_build_targets_shape(self):
        df = _make_df(200)
        targets = _build_targets(df)
        assert targets.shape == (200, len(PRED_HORIZONS))

    def test_build_targets_values_are_probabilities(self):
        df = _make_df(200)
        targets = _build_targets(df)
        assert targets.min() >= 0
        assert targets.max() <= 1


class TestModel:
    def test_lstm_forward_shape(self):
        import torch
        model = StockLSTM()
        x = torch.randn(4, SEQ_LEN, len(FEATURE_COLS))
        out = model(x)
        assert out.shape == (4, len(PRED_HORIZONS))
        assert (out >= 0).all() and (out <= 1).all()

    def test_make_sequences(self):
        df = _make_df(200)
        df = _compute_features(df).dropna()
        features = df[FEATURE_COLS].values.astype(np.float32)
        targets = _build_targets(df)
        X, y = _make_sequences(features, targets)
        assert X.shape == (len(features) - SEQ_LEN, SEQ_LEN, len(FEATURE_COLS))
        assert y.shape[0] == X.shape[0]

    def test_get_model_status(self):
        status = get_model_status()
        assert "device" in status
        assert status["feature_count"] == len(FEATURE_COLS)
        assert status["seq_len"] == SEQ_LEN


class TestTrainAndPredict:
    @pytest.fixture(autouse=True)
    def _use_tmp_model_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("services.predict.MODEL_DIR", tmp_path)

    def test_train_and_predict_roundtrip(self):
        from unittest.mock import patch

        df = _make_df(200)
        with patch("services.predict.get_stock_history", return_value=df):
            from services.predict import train_model, predict
            result = train_model("TEST01", epochs=3)
            assert "error" not in result
            assert result["samples"] > 0

            pred = predict("TEST01")
            assert "error" not in pred
            assert len(pred["predictions"]) == len(PRED_HORIZONS)
            for p in pred["predictions"]:
                assert 0 <= p["rise_prob"] <= 1

    def test_predict_without_model_returns_need_train(self):
        from unittest.mock import patch

        with patch("services.predict.get_stock_history", return_value=_make_df()):
            from services.predict import predict
            pred = predict("NOMODEL")
            assert pred.get("need_train") is True
