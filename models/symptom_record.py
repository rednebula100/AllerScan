"""SymptomRecord: 특정 시각에 겪은 증상 기록."""
from __future__ import annotations

import json
import os
from datetime import datetime

# 지원하는 증상 타입
SYMPTOM_TYPES = ("소화", "피부", "호흡", "두통", "기타")


class SymptomRecord:
    """특정 시각의 증상 한 건. 여러 증상(symptoms)을 담는다.

    symptom dict 구조: {"type": str, "severity": int(1~5), "note": str}
    """

    def __init__(self, timestamp: datetime, symptoms: list[dict] | None = None) -> None:
        self.timestamp: datetime = timestamp
        self.symptoms: list[dict] = symptoms if symptoms is not None else []

    def add_symptom(self, type: str, severity: int, note: str = "") -> None:
        """증상 하나를 추가한다 (심각도는 1~5로 보정)."""
        severity = max(1, min(5, int(severity)))
        self.symptoms.append({"type": type, "severity": severity, "note": note})

    def get_severity_score(self) -> float:
        """이 기록의 평균 심각도. 증상이 없으면 0.0."""
        if not self.symptoms:
            return 0.0
        return sum(s["severity"] for s in self.symptoms) / len(self.symptoms)

    # ------------------------------------------------------------------ #
    def save(self, path: str) -> None:
        """JSON 파일로 저장한다."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        data = {
            "timestamp": self.timestamp.isoformat(),
            "symptoms": [
                {"type": s["type"], "severity": int(s["severity"]), "note": s.get("note", "")}
                for s in self.symptoms
            ],
        }
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        """JSON 파일에서 불러온다 (self를 갱신)."""
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        self.timestamp = datetime.fromisoformat(data["timestamp"])
        self.symptoms = [
            {"type": s["type"], "severity": int(s["severity"]), "note": s.get("note", "")}
            for s in data.get("symptoms", [])
        ]
