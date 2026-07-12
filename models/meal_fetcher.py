"""MealFetcher: NEIS 교육정보 개방 포털 API로 학교/급식 정보를 가져온다."""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

from .menu_item import MenuItem

_SCHOOL_URL = "https://open.neis.go.kr/hub/schoolInfo"
_MEAL_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"
_TIMEOUT = 10


class MealApiError(Exception):
    """API 호출 또는 응답 처리 중 발생한 오류."""


class MealFetcher:
    """NEIS API 래퍼. API 키는 선택(없으면 제한된 범위로 조회)."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key: str = api_key or ""
        # fetch_week 호출 시 날짜별 총 칼로리(kcal)를 함께 채운다.
        self.week_calories: dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _params(self, extra: dict[str, str]) -> dict[str, str]:
        params = {"Type": "json", "pIndex": "1", "pSize": "100"}
        if self.api_key:
            params["KEY"] = self.api_key
        params.update(extra)
        return params

    def _request(self, url: str, extra: dict[str, str], root: str) -> list[dict]:
        """API를 호출해 row 목록을 반환한다. 데이터 없으면 빈 리스트."""
        try:
            resp = requests.get(url, params=self._params(extra), timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout as exc:
            raise MealApiError("서버 응답 시간이 초과되었습니다. 네트워크를 확인해주세요.") from exc
        except requests.exceptions.SSLError as exc:
            raise MealApiError(
                "SSL 인증서 검증에 실패했습니다. 'pip install truststore' 후 다시 실행해주세요."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise MealApiError("인터넷에 연결할 수 없습니다.") from exc
        except requests.exceptions.RequestException as exc:
            raise MealApiError(f"요청 중 오류가 발생했습니다: {exc}") from exc
        except ValueError as exc:  # JSON 파싱 실패
            raise MealApiError("서버 응답을 해석할 수 없습니다.") from exc

        # 최상위 RESULT (데이터 없음 / 인증 오류 등)
        if "RESULT" in data:
            code = data["RESULT"].get("CODE", "")
            message = data["RESULT"].get("MESSAGE", "알 수 없는 오류")
            if code == "INFO-200":  # 해당하는 데이터가 없습니다.
                return []
            raise MealApiError(f"API 오류: {message} ({code})")

        if root not in data:
            return []

        block = data[root]
        # block[0] = head(메타), block[1] = {"row": [...]}
        rows: list[dict] = []
        for section in block:
            if isinstance(section, dict) and "row" in section:
                rows.extend(section["row"])
        return rows

    # ------------------------------------------------------------------ #
    # 공개 API
    # ------------------------------------------------------------------ #
    def search_school(self, name: str) -> list[dict]:
        """학교명으로 검색해 [{name, office_code, school_code, kind, address}] 반환."""
        name = name.strip()
        if not name:
            return []
        rows = self._request(_SCHOOL_URL, {"SCHUL_NM": name}, "schoolInfo")
        results: list[dict] = []
        for row in rows:
            results.append(
                {
                    "name": row.get("SCHUL_NM", ""),
                    "office_code": row.get("ATPT_OFCDC_SC_CODE", ""),
                    "school_code": row.get("SD_SCHUL_CODE", ""),
                    "kind": row.get("SCHUL_KND_SC_NM", ""),
                    "address": row.get("ORG_RDNMA", ""),
                }
            )
        return results

    def fetch_day(self, office_code: str, school_code: str, date: datetime) -> list[MenuItem]:
        """특정 날짜의 급식 메뉴 목록을 반환한다."""
        ymd = date.strftime("%Y%m%d")
        rows = self._request(
            _MEAL_URL,
            {
                "ATPT_OFCDC_SC_CODE": office_code,
                "SD_SCHUL_CODE": school_code,
                "MLSV_YMD": ymd,
            },
            "mealServiceDietInfo",
        )
        items, _ = self._rows_to_items(rows)
        return items

    def fetch_week(
        self, office_code: str, school_code: str, date: datetime
    ) -> dict[str, list[MenuItem]]:
        """date가 속한 주(월~금)의 급식을 반환한다.

        키는 "YYYYMMDD" 형식. 날짜별 총 칼로리는 self.week_calories에 채워진다.
        급식이 없는 날도 키는 포함되며 값은 빈 리스트다.
        """
        monday = date - timedelta(days=date.weekday())
        weekdays = [monday + timedelta(days=i) for i in range(5)]
        from_ymd = weekdays[0].strftime("%Y%m%d")
        to_ymd = weekdays[-1].strftime("%Y%m%d")

        rows = self._request(
            _MEAL_URL,
            {
                "ATPT_OFCDC_SC_CODE": office_code,
                "SD_SCHUL_CODE": school_code,
                "MLSV_FROM_YMD": from_ymd,
                "MLSV_TO_YMD": to_ymd,
            },
            "mealServiceDietInfo",
        )

        # 모든 날짜 키를 빈 리스트로 초기화
        result: dict[str, list[MenuItem]] = {d.strftime("%Y%m%d"): [] for d in weekdays}
        self.week_calories = {d.strftime("%Y%m%d"): 0.0 for d in weekdays}

        # 날짜별로 row를 모아 파싱 (한 날에 조식/중식/석식 여러 끼가 있을 수 있음)
        for row in rows:
            ymd = row.get("MLSV_YMD", "")
            if ymd not in result:
                continue
            items, kcal = self._rows_to_items([row])
            result[ymd].extend(items)
            self.week_calories[ymd] += kcal

        return result

    # ------------------------------------------------------------------ #
    @staticmethod
    def _rows_to_items(rows: list[dict]) -> tuple[list[MenuItem], float]:
        """meal row 목록 -> (MenuItem 목록, 총 칼로리 kcal)."""
        items: list[MenuItem] = []
        total_kcal = 0.0
        for row in rows:
            dish = row.get("DDISH_NM", "")
            for line in dish.split("<br/>"):
                line = line.strip()
                if line:
                    items.append(MenuItem(line))
            # CAL_INFO 예: "570.5 Kcal"
            cal_info = row.get("CAL_INFO", "")
            digits = "".join(c for c in cal_info if c.isdigit() or c == ".")
            try:
                total_kcal += float(digits) if digits else 0.0
            except ValueError:
                pass
        return items, total_kcal
