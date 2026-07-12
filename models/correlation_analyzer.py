"""CorrelationAnalyzer: 식사(알레르기 노출)와 증상 사이의 시차(lag) 상관 분석."""
from __future__ import annotations

import glob
import os
from datetime import datetime, timedelta

import numpy as np
from scipy.stats import pearsonr

from .meal_record import MealRecord
from .menu_item import ALLERGEN_NAMES
from .symptom_record import SymptomRecord

# 기본 시차 후보 (시간)
DEFAULT_LAGS = [1, 2, 4, 6, 8, 12, 24]
# 식사 시각 + lag 를 기준으로 증상을 매칭할 때 허용 오차(시간)
WINDOW_HOURS = 2.0


class CorrelationAnalyzer:
    """식사 기록과 증상 기록을 모아 알레르기별 시차 상관을 계산한다."""

    def __init__(
        self,
        meal_records: list[MealRecord] | None = None,
        symptom_records: list[SymptomRecord] | None = None,
    ) -> None:
        self.meal_records: list[MealRecord] = meal_records or []
        self.symptom_records: list[SymptomRecord] = symptom_records or []

    # ------------------------------------------------------------------ #
    def load_all(self, data_dir: str) -> None:
        """data_dir/meals, data_dir/symptoms 아래의 모든 JSON 기록을 불러온다."""
        self.meal_records = []
        for path in sorted(glob.glob(os.path.join(data_dir, "meals", "*.json"))):
            try:
                rec = MealRecord(datetime.min)
                rec.load(path)
                self.meal_records.append(rec)
            except (OSError, ValueError, KeyError):
                continue

        self.symptom_records = []
        for path in sorted(glob.glob(os.path.join(data_dir, "symptoms", "*.json"))):
            try:
                rec = SymptomRecord(datetime.min)
                rec.load(path)
                self.symptom_records.append(rec)
            except (OSError, ValueError, KeyError):
                continue

    # ------------------------------------------------------------------ #
    def analyze_lag(self, allergen: int, lag_hours: list[int] | None = None) -> dict[int, float]:
        """각 시차별로 (해당 알레르기 노출량, lag 시간 뒤 증상 심각도)의 피어슨 상관계수 반환.

        각 식사에 대해:
          x = 그 식사에서 해당 알레르기 노출 횟수 (없으면 0)
          y = (식사시각 + lag) 를 기준으로 ±WINDOW_HOURS 이내에 있는 증상들의 최대 심각도 (없으면 0)
        """
        if lag_hours is None:
            lag_hours = DEFAULT_LAGS

        meals = [
            (m.timestamp, m.get_allergen_exposure().get(allergen, 0.0))
            for m in self.meal_records
        ]
        window = timedelta(hours=WINDOW_HOURS)

        result: dict[int, float] = {}
        for lag in lag_hours:
            xs: list[float] = []
            ys: list[float] = []
            for ts, exposure in meals:
                target = ts + timedelta(hours=lag)
                severity = 0.0
                for s in self.symptom_records:
                    if abs(s.timestamp - target) <= window:
                        severity = max(severity, s.get_severity_score())
                xs.append(exposure)
                ys.append(severity)
            result[lag] = self._safe_pearson(xs, ys)
        return result

    @staticmethod
    def _safe_pearson(xs: list[float], ys: list[float]) -> float:
        """피어슨 상관계수. 표본이 부족하거나 상수 배열이면 0.0을 반환한다."""
        x = np.asarray(xs, dtype=float)
        y = np.asarray(ys, dtype=float)
        if len(x) < 2 or np.all(x == x[0]) or np.all(y == y[0]):
            return 0.0
        r, _ = pearsonr(x, y)
        return 0.0 if np.isnan(r) else float(r)

    def get_top_suspects(self) -> list[dict]:
        """알레르기별로 상관이 가장 높은 시차를 찾아 상위 5개를 반환한다.

        각 항목: {"allergen", "allergen_name", "lag_hours", "correlation"}
        """
        allergens: set[int] = set()
        for meal in self.meal_records:
            for food in meal.foods:
                allergens |= food["allergens"]

        suspects: list[dict] = []
        for allergen in allergens:
            lags = self.analyze_lag(allergen)
            if not lags:
                continue
            best_lag = max(lags, key=lambda lag: lags[lag])
            suspects.append(
                {
                    "allergen": allergen,
                    "allergen_name": ALLERGEN_NAMES.get(allergen, str(allergen)),
                    "lag_hours": best_lag,
                    "correlation": lags[best_lag],
                }
            )
        suspects.sort(key=lambda d: d["correlation"], reverse=True)
        return suspects[:5]

    def get_daily_exposure(self, date: datetime) -> dict[int, int]:
        """특정 날짜의 알레르기 번호별 누적 노출 횟수를 반환한다."""
        result: dict[int, int] = {}
        for meal in self.meal_records:
            if meal.timestamp.date() == date.date():
                for allergen, count in meal.get_allergen_exposure().items():
                    result[allergen] = result.get(allergen, 0) + int(count)
        return result
