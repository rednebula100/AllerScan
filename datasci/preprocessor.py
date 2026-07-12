"""raw_meals.csv를 날짜별 알레르겐 0/1 행렬로 정제한다."""
from __future__ import annotations

import os

import pandas as pd

from models.menu_item import ALLERGEN_NAMES

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
PROCESSED_CSV_PATH = os.path.join(RESULTS_DIR, "processed_allergens.csv")

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _parse_allergens(cell: str) -> set[int]:
    if not isinstance(cell, str) or not cell.strip():
        return set()
    return {int(n) for n in cell.split(".") if n.strip()}


def build_allergen_matrix(raw_df: pd.DataFrame) -> pd.DataFrame:
    """raw_meals DataFrame(date, menu_name, allergens) -> 날짜별 0/1 알레르겐 행렬.

    컬럼: date, weekday, week(연도 기준 ISO 주차), <알레르겐 이름 19개 0/1>
    하루에 해당 알레르겐이 하나라도 등장하면 1.
    """
    if raw_df.empty:
        cols = ["date", "weekday", "week"] + [ALLERGEN_NAMES[i] for i in range(1, 20)]
        return pd.DataFrame(columns=cols)

    dates = sorted(raw_df["date"].unique())
    records: list[dict] = []
    for ymd in dates:
        day_rows = raw_df[raw_df["date"] == ymd]
        present: set[int] = set()
        for cell in day_rows["allergens"]:
            present |= _parse_allergens(cell)

        dt = pd.to_datetime(ymd, format="%Y%m%d")
        record: dict = {
            "date": ymd,
            "weekday": WEEKDAY_KO[dt.weekday()],
            "week": int(dt.isocalendar().week),
        }
        for num in range(1, 20):
            record[ALLERGEN_NAMES[num]] = 1 if num in present else 0
        records.append(record)

    return pd.DataFrame(records)


def save_processed(df: pd.DataFrame, path: str = PROCESSED_CSV_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path
