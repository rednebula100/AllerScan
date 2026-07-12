"""NEIS API로 한 학기 급식 데이터를 수집해 DataFrame/CSV로 저장한다.

기존 MealFetcher(models/meal_fetcher.py)를 그대로 재사용한다. NEIS는 주 단위 조회
(fetch_week)만 지원하므로, 지정한 기간을 월요일 기준 주 단위로 나눠 반복 호출한다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd

from models import MealFetcher, MenuItem

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RAW_CSV_PATH = os.path.join(RESULTS_DIR, "raw_meals.csv")


def _week_mondays(start: datetime, end: datetime) -> list[datetime]:
    """start~end 구간을 포함하는 주들의 월요일 목록을 반환한다."""
    monday = start - timedelta(days=start.weekday())
    mondays = []
    while monday <= end:
        mondays.append(monday)
        monday += timedelta(weeks=1)
    return mondays


def collect_semester(
    office_code: str,
    school_code: str,
    start: datetime,
    end: datetime,
    api_key: str = "",
) -> pd.DataFrame:
    """start~end 기간의 급식을 주 단위로 수집해 DataFrame으로 반환한다.

    반환 컬럼: date(YYYYMMDD), menu_name, allergens(쉼표구분 번호 문자열)
    """
    fetcher = MealFetcher(api_key)
    rows: list[dict] = []

    for monday in _week_mondays(start, end):
        week_data = fetcher.fetch_week(office_code, school_code, monday)
        for ymd, items in week_data.items():
            date = datetime.strptime(ymd, "%Y%m%d")
            if not (start <= date <= end):
                continue
            item: MenuItem
            for item in items:
                rows.append(
                    {
                        "date": ymd,
                        "menu_name": item.name,
                        "allergens": ".".join(str(n) for n in sorted(item.allergens)),
                    }
                )

    df = pd.DataFrame(rows, columns=["date", "menu_name", "allergens"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def save_raw(df: pd.DataFrame, path: str = RAW_CSV_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path
