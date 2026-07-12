"""settings: API 키 등 사용자 설정을 JSON으로 저장/불러오기.

git에는 포함되지 않는다 (.gitignore의 data/* 규칙에 의해 자동 제외).
"""
from __future__ import annotations

import json
import os

SETTINGS_PATH = os.path.join("data", "settings.json")


def load_settings() -> dict:
    """설정 파일을 불러온다. 없거나 손상되었으면 빈 dict를 반환한다."""
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    """설정을 JSON 파일로 저장한다."""
    directory = os.path.dirname(SETTINGS_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
