"""MenuItem: NEIS 급식 원본 문자열을 파싱해 메뉴명과 알레르기 성분을 추출."""
from __future__ import annotations

import re


# 번호 -> 알레르기 유발 식재료 이름
ALLERGEN_NAMES: dict[int, str] = {
    1: "난류", 2: "우유", 3: "메밀", 4: "땅콩", 5: "대두",
    6: "밀", 7: "고등어", 8: "게", 9: "새우", 10: "돼지고기",
    11: "복숭아", 12: "토마토", 13: "아황산류", 14: "호두", 15: "닭고기",
    16: "쇠고기", 17: "오징어", 18: "조개류", 19: "잣",
}

# 문자열 끝의 알레르기 표기: "1.5.6.16.", "(5.6.16)", " 5.6." 등
_ALLERGEN_TAIL = re.compile(r"[\s(]*((?:\d{1,2}\s*\.?\s*)+)\)?\s*$")


class MenuItem:
    """급식 메뉴 한 줄. raw 문자열에서 name과 allergens를 자동 추출한다."""

    def __init__(self, raw: str) -> None:
        self.raw: str = raw
        self.name: str
        self.allergens: set[int]
        self.name, self.allergens = self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> tuple[str, set[int]]:
        # NEIS는 종종 <br/> 로 줄을 나누므로 안전하게 정리
        text = raw.replace("<br/>", " ").replace("&amp;", "&").strip()
        allergens: set[int] = set()
        name = text

        match = _ALLERGEN_TAIL.search(text)
        if match:
            numbers = re.findall(r"\d{1,2}", match.group(1))
            valid = {int(n) for n in numbers if 1 <= int(n) <= 19}
            if valid:
                allergens = valid
                name = text[: match.start()].strip(" .()")

        # 메뉴명 안의 슬래시(/) 제거 후 공백 정리 (예: "돈까스/소스" -> "돈까스 소스")
        name = name.replace("/", " ")
        name = re.sub(r"\s+", " ", name).strip()
        return name, allergens

    def get_allergen_names(self) -> list[str]:
        """보유 알레르기 번호를 실제 이름 목록으로 변환한다."""
        return [ALLERGEN_NAMES[n] for n in sorted(self.allergens) if n in ALLERGEN_NAMES]

    def __repr__(self) -> str:
        return f"MenuItem(name={self.name!r}, allergens={sorted(self.allergens)})"
