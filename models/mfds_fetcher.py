"""MFDSFetcher: 식약처 식품영양성분DB(I2790) API로 식품을 검색하고 알레르기 정보를 파싱."""
from __future__ import annotations

import re

import requests

from .menu_item import ALLERGEN_NAMES

_BASE_URL = "https://openapi.foodsafetykorea.go.kr/api"
_SERVICE = "I2790"
_TIMEOUT = 10

# 알레르기명(및 별칭) -> 번호. ALLERGY_INFO 필드 파싱에 사용.
_NAME_TO_NUM: dict[str, int] = {name: num for num, name in ALLERGEN_NAMES.items()}
_NAME_TO_NUM.update(
    {
        "계란": 1, "달걀": 1, "난류": 1, "소고기": 16, "쇠고기": 16,
        "아황산": 13, "아황산류": 13, "굴": 18, "전복": 18, "홍합": 18, "조개": 18,
    }
)


class MFDSApiError(Exception):
    """식약처 API 호출/응답 처리 오류."""


class MFDSFetcher:
    """식약처 식품 API 래퍼. 키가 없으면 검색이 비활성화된다(수동 입력으로 fallback)."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key: str = api_key or ""

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search_food(self, name: str) -> list[dict]:
        """식품명으로 검색. [{"name": str, "allergens": set[int]}] 반환.

        키가 없으면 빈 리스트를 반환한다(호출측에서 수동 입력으로 유도).
        """
        name = name.strip()
        if not name or not self.api_key:
            return []

        url = f"{_BASE_URL}/{self.api_key}/{_SERVICE}/json/1/10/FOOD_NM_KR={name}"
        try:
            resp = requests.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise MFDSApiError(f"식약처 API 요청 실패: {exc}") from exc

        # 인증키가 유효하지 않으면 JSON이 아니라 "<script>alert('인증키가 유효하지
        # 않습니다...')</script>" 형태의 HTML을 200 OK로 내려준다. json() 파싱 전에 먼저 걸러서
        # "Expecting value: line 1 column 1 (char 0)" 같은 알아보기 힘든 오류 대신 명확히 안내한다.
        if not resp.text.strip():
            raise MFDSApiError("식약처 API로부터 빈 응답을 받았습니다. 잠시 후 다시 시도해주세요.")
        if resp.text.lstrip().startswith("<"):
            raise MFDSApiError(
                "식약처 API 인증키가 유효하지 않습니다. "
                "https://www.foodsafetykorea.go.kr 에서 발급받은 키(MFDS_API_KEY)인지 확인해주세요. "
                "(공공데이터포털 data.go.kr 인증키는 다른 시스템이라 여기서 쓸 수 없습니다.)"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise MFDSApiError("식약처 응답을 해석할 수 없습니다.") from exc

        block = data.get(_SERVICE, {})
        result_code = block.get("RESULT", {}).get("CODE", "")
        if result_code and result_code not in ("INFO-000",):
            # INFO-200: 데이터 없음 -> 빈 리스트
            return []

        rows = block.get("row", [])
        results: list[dict] = []
        for row in rows:
            results.append(
                {
                    "name": row.get("FOOD_NM_KR", "").strip(),
                    "allergens": self.parse_allergy_info(row.get("ALLERGY_INFO", "")),
                }
            )
        return results

    @staticmethod
    def parse_allergy_info(info: str) -> set[int]:
        """ALLERGY_INFO 문자열(쉼표 구분 알레르기명/번호)을 알레르기 번호 집합으로 변환한다.

        예: "1.난류, 5.대두, 6.밀 함유" -> {1, 5, 6}
        """
        if not info:
            return set()
        allergens: set[int] = set()
        for token in re.split(r"[,/·]", info):
            token = token.strip()
            if not token:
                continue
            # "6.밀" 처럼 앞에 번호가 붙은 경우 우선 사용
            num_match = re.match(r"\s*(\d{1,2})\b", token)
            if num_match:
                n = int(num_match.group(1))
                if 1 <= n <= 19:
                    allergens.add(n)
                    continue
            # 이름으로 매칭 (부분 문자열 포함)
            for alias, num in _NAME_TO_NUM.items():
                if alias in token:
                    allergens.add(num)
                    break
        return allergens
