"""알레르겐 0/1 행렬(processed_allergens.csv)에 대한 4종 분석.

모든 함수는 preprocessor.build_allergen_matrix()가 만든 DataFrame을 입력으로 받는다.
"""
from __future__ import annotations

import pandas as pd

from models.menu_item import ALLERGEN_NAMES

ALLERGEN_COLUMNS = [ALLERGEN_NAMES[i] for i in range(1, 20)]
WEEKDAY_ORDER = ["월", "화", "수", "목", "금"]


def allergen_frequency(df: pd.DataFrame) -> pd.Series:
    """알레르겐별 출현 빈도(등장한 급식일 수), 내림차순."""
    if df.empty:
        return pd.Series(dtype=int)
    return df[ALLERGEN_COLUMNS].sum().sort_values(ascending=False)


def cooccurrence_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """알레르겐 동시 출현 상관관계 행렬 (피어슨 상관계수, 19x19)."""
    if df.empty:
        return pd.DataFrame(index=ALLERGEN_COLUMNS, columns=ALLERGEN_COLUMNS, dtype=float)
    return df[ALLERGEN_COLUMNS].corr()


def weekday_avg_exposure(df: pd.DataFrame) -> pd.Series:
    """요일별 하루 평균 알레르겐 노출 개수 (월~금 순서)."""
    if df.empty:
        return pd.Series(0.0, index=WEEKDAY_ORDER)
    daily_count = df[ALLERGEN_COLUMNS].sum(axis=1)
    grouped = daily_count.groupby(df["weekday"]).mean()
    return grouped.reindex(WEEKDAY_ORDER).fillna(0.0)


def weekly_trend_top5(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """주차별 상위 5종 알레르겐의 노출(등장 급식일 수) 추세.

    반환: (주차 x 알레르겐5 DataFrame, top5 알레르겐 이름 리스트)
    """
    if df.empty:
        return pd.DataFrame(), []
    top5 = allergen_frequency(df).head(5).index.tolist()
    weekly = df.groupby("week")[top5].sum().sort_index()
    return weekly, top5
