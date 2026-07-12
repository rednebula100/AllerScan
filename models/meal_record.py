"""MealRecord: 한 끼 식사에 포함된 식품과 알레르기 노출 기록."""
from __future__ import annotations

import json
import os
from datetime import datetime

# food source 값: NEIS 급식 / 식약처 식품DB / 수동 입력
FOOD_SOURCES = ("neis", "mfds", "manual")


class MealRecord:
    """특정 시각의 식사 한 건. 여러 식품(foods)을 담는다.

    food dict 구조: {"name": str, "allergens": set[int], "source": str}
    """

    def __init__(self, timestamp: datetime, foods: list[dict] | None = None) -> None:
        self.timestamp: datetime = timestamp
        self.foods: list[dict] = foods if foods is not None else []

    def add_food(self, name: str, allergens: set[int], source: str = "manual") -> None:
        """식품 하나를 추가한다."""
        self.foods.append(
            {"name": name, "allergens": set(allergens), "source": source}
        )

    def get_allergen_exposure(self) -> dict[int, float]:
        """알레르기 번호별 노출 횟수(해당 성분을 가진 식품 수)를 반환한다."""
        exposure: dict[int, float] = {}
        for food in self.foods:
            for allergen in food["allergens"]:
                exposure[allergen] = exposure.get(allergen, 0.0) + 1.0
        return exposure

    # ------------------------------------------------------------------ #
    def save(self, path: str) -> None:
        """JSON 파일로 저장한다 (set은 정렬된 list로 직렬화)."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        data = {
            "timestamp": self.timestamp.isoformat(),
            "foods": [
                {
                    "name": f["name"],
                    "allergens": sorted(f["allergens"]),
                    "source": f.get("source", "manual"),
                }
                for f in self.foods
            ],
        }
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        """JSON 파일에서 불러온다 (self를 갱신)."""
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        self.timestamp = datetime.fromisoformat(data["timestamp"])
        self.foods = [
            {
                "name": f["name"],
                "allergens": {int(a) for a in f.get("allergens", [])},
                "source": f.get("source", "manual"),
            }
            for f in data.get("foods", [])
        ]
