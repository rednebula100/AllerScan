"""datasci: NEIS 급식 데이터 기반 알레르겐 노출 패턴 분석 (한 학기 단위).

pandas가 필요하므로 이 패키지는 지연 import로 쓰는 것을 권장한다(GUI 시작 속도 유지).
설치: pip install -r datasci/requirements.txt
"""
from .analyzer import (
    allergen_frequency,
    cooccurrence_matrix,
    weekday_avg_exposure,
    weekly_trend_top5,
)
from .collector import collect_semester
from .predictor import predict_next_week
from .preprocessor import build_allergen_matrix

__all__ = [
    "collect_semester",
    "build_allergen_matrix",
    "allergen_frequency",
    "cooccurrence_matrix",
    "weekday_avg_exposure",
    "weekly_trend_top5",
    "predict_next_week",
]
