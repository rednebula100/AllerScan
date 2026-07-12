"""주차별 알레르겐 출현율에 단순 선형회귀를 적용해 다음 주 노출 확률을 추정한다.

sklearn 없이 numpy.polyfit(1차)만 사용한다. 각 알레르겐의 "주간 출현율"(그 주 급식일 중
해당 알레르겐이 등장한 비율, 0~1)을 주차 인덱스에 대해 선형 추세선을 그리고, 다음 주
인덱스의 예측값을 [0, 1]로 클립해 "노출 확률"로 사용한다.

주의: 이는 진짜 확률 모델이 아니라 최근 추세를 선형 외삽한 근사치다. 표본(주차)이
적을수록 신뢰도가 낮다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from models.menu_item import ALLERGEN_NAMES

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
PREDICTION_JSON_PATH = os.path.join(RESULTS_DIR, "next_week_prediction.json")

ALLERGEN_COLUMNS = [ALLERGEN_NAMES[i] for i in range(1, 20)]


def _weekly_occurrence_rate(df: pd.DataFrame) -> pd.DataFrame:
    """주차별 알레르겐 출현율(0~1) DataFrame. index=week, columns=알레르겐."""
    counts = df.groupby("week")[ALLERGEN_COLUMNS].sum()
    meal_days = df.groupby("week").size()
    return counts.div(meal_days, axis=0).sort_index()


def predict_next_week(df: pd.DataFrame) -> dict:
    """알레르겐별 다음 주 노출 확률을 예측해 dict로 반환한다.

    반환 구조: {"weeks_used": int, "next_week_index": int,
                "predictions": {알레르겐명: 확률, ...} (확률 내림차순),
                "top3": [{"allergen": 이름, "probability": 값}, ...]}
    """
    if df.empty:
        return {"weeks_used": 0, "next_week_index": None, "predictions": {}, "top3": []}

    rates = _weekly_occurrence_rate(df)
    weeks = rates.index.to_numpy(dtype=float)
    next_week_index = int(weeks[-1]) + 1

    predictions: dict[str, float] = {}
    for allergen in ALLERGEN_COLUMNS:
        y = rates[allergen].to_numpy(dtype=float)
        if len(weeks) < 2 or np.all(y == y[0]):
            # 회귀에 필요한 변화/표본이 없으면 마지막 값을 그대로 사용
            pred = float(y[-1]) if len(y) else 0.0
        else:
            slope, intercept = np.polyfit(weeks, y, 1)
            pred = float(slope * next_week_index + intercept)
        predictions[allergen] = round(float(np.clip(pred, 0.0, 1.0)), 4)

    predictions = dict(sorted(predictions.items(), key=lambda kv: kv[1], reverse=True))
    top3 = [{"allergen": name, "probability": prob} for name, prob in list(predictions.items())[:3]]

    return {
        "weeks_used": len(weeks),
        "next_week_index": next_week_index,
        "predictions": predictions,
        "top3": top3,
    }


def save_prediction(result: dict, path: str = PREDICTION_JSON_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), **result}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
