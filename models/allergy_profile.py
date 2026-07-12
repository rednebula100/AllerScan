"""AllergyProfile: 사용자의 개인 알레르기 프로필 관리."""
from __future__ import annotations

import json
import os


# NEIS 급식 알레르기 유발 식재료 번호 (1~19)
VALID_ALLERGENS: set[int] = set(range(1, 20))


class AllergyProfile:
    """사용자 이름과 보유 알레르기 번호(1~19)를 관리한다."""

    def __init__(self, name: str = "나의 프로필", allergies: set[int] | None = None) -> None:
        self.name: str = name
        self.allergies: set[int] = set(allergies) if allergies else set()

    def add(self, num: int) -> None:
        """알레르기 번호를 추가한다 (1~19 범위만 허용)."""
        if num not in VALID_ALLERGENS:
            raise ValueError(f"알레르기 번호는 1~19 사이여야 합니다: {num}")
        self.allergies.add(num)

    def remove(self, num: int) -> None:
        """알레르기 번호를 제거한다 (없으면 무시)."""
        self.allergies.discard(num)

    def is_safe(self, allergens: set[int]) -> str:
        """메뉴의 알레르기 성분과 비교해 위험도를 판정한다.

        - safe:    겹치는 번호 없음
        - caution: 정확히 1개 겹침
        - danger:  2개 이상 겹침
        """
        overlap = len(self.allergies & allergens)
        if overlap == 0:
            return "safe"
        if overlap == 1:
            return "caution"
        return "danger"

    def save(self, path: str) -> None:
        """프로필을 JSON 파일로 저장한다."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        data = {"name": self.name, "allergies": sorted(self.allergies)}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        """JSON 파일에서 프로필을 불러온다."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.name = data.get("name", self.name)
        self.allergies = {int(n) for n in data.get("allergies", []) if int(n) in VALID_ALLERGENS}
