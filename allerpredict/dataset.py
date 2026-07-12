"""AllerPredict 데이터 파이프라인.

AllerScan의 식사(MealRecord) / 증상(SymptomRecord) 기록을 1D-CNN 학습용 (X, y)로 변환한다.
실데이터가 부족하면 학습 가능한 신호가 담긴 합성 데이터로 보강한다.

입력 표현: 식사 한 건당 19차원 알레르겐 노출 벡터 (index i-1 = 알레르겐 번호 i의 노출 횟수).
라벨: 식사 후 REACTION_WINDOW_HOURS 시간 안에 평균 심각도 >= REACTION_SEVERITY_THRESHOLD 인
      증상 기록이 있으면 1(반응 발생), 없으면 0.

주의: 알레르겐 번호 순서(1~19)에는 공간적 의미가 없다. 1D-CNN을 쓰는 것은 스펙 요구사항이며,
      conv+pooling은 인접 슬롯 간 알레르겐 조합 패턴을 학습하는 용도로 동작한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from models import CorrelationAnalyzer, MealRecord, SymptomRecord

NUM_ALLERGENS = 19
REACTION_WINDOW_HOURS = 24.0
REACTION_SEVERITY_THRESHOLD = 3.0

# 합성 데이터에서 '진짜' 반응을 일으키는 알레르겐(정답). 모델이 학습으로 찾아내야 하는 대상.
DEFAULT_TRIGGERS = (2, 6, 9)  # 우유, 밀, 새우


def exposure_to_vector(exposure: dict[int, float]) -> np.ndarray:
    """알레르겐 번호->노출횟수 dict를 19차원 float 벡터로 변환한다."""
    vec = np.zeros(NUM_ALLERGENS, dtype=np.float32)
    for num, count in exposure.items():
        if 1 <= num <= NUM_ALLERGENS:
            vec[num - 1] = float(count)
    return vec


def build_dataset_from_records(
    meals: list[MealRecord], symptoms: list[SymptomRecord]
) -> tuple[np.ndarray, np.ndarray]:
    """식사/증상 기록 리스트를 (X, y)로 변환한다."""
    window = timedelta(hours=REACTION_WINDOW_HOURS)
    xs: list[np.ndarray] = []
    ys: list[int] = []
    for meal in meals:
        vec = exposure_to_vector(meal.get_allergen_exposure())
        reacted = 0
        for symptom in symptoms:
            if (
                meal.timestamp <= symptom.timestamp <= meal.timestamp + window
                and symptom.get_severity_score() >= REACTION_SEVERITY_THRESHOLD
            ):
                reacted = 1
                break
        xs.append(vec)
        ys.append(reacted)

    if not xs:
        return (
            np.empty((0, NUM_ALLERGENS), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
        )
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.int64)


def generate_synthetic(
    n_samples: int = 2000,
    triggers: tuple[int, ...] = DEFAULT_TRIGGERS,
    seed: int = 42,
    label_noise: float = 0.08,
) -> tuple[np.ndarray, np.ndarray]:
    """학습 가능한 신호가 담긴 합성 (X, y)를 만든다.

    각 샘플은 1~5개 알레르겐이 노출(횟수 1~3)되며, trigger 알레르겐이 포함되면
    높은 확률(0.85)로, 아니면 낮은 기저 확률(0.05)로 반응이 발생한다. 여기에 label_noise
    비율만큼 라벨을 뒤집어 현실적인 불확실성을 준다.
    """
    rng = np.random.default_rng(seed)
    trigger_set = set(triggers)
    x = np.zeros((n_samples, NUM_ALLERGENS), dtype=np.float32)
    y = np.zeros(n_samples, dtype=np.int64)
    allergen_ids = np.arange(1, NUM_ALLERGENS + 1)

    for i in range(n_samples):
        k = int(rng.integers(1, 6))  # 1~5개 알레르겐 노출
        present = rng.choice(allergen_ids, size=k, replace=False)
        for allergen in present:
            x[i, allergen - 1] = float(rng.integers(1, 4))  # 노출 횟수 1~3

        has_trigger = any(int(a) in trigger_set for a in present)
        prob = 0.85 if has_trigger else 0.05
        label = 1 if rng.random() < prob else 0
        if rng.random() < label_noise:
            label = 1 - label
        y[i] = label

    return x, y


def load_dataset(
    data_dir: str = "data",
    min_real: int = 50,
    synthetic_samples: int = 2000,
    seed: int = 42,
    synthetic_only: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """실데이터를 불러오고, 부족하면 합성 데이터로 보강해 (X, y, meta)를 반환한다."""
    real_x = np.empty((0, NUM_ALLERGENS), dtype=np.float32)
    real_y = np.empty((0,), dtype=np.int64)
    if not synthetic_only:
        analyzer = CorrelationAnalyzer()
        analyzer.load_all(data_dir)
        real_x, real_y = build_dataset_from_records(
            analyzer.meal_records, analyzer.symptom_records
        )

    meta: dict = {"real_samples": int(len(real_x))}

    if synthetic_only or len(real_x) < min_real:
        syn_x, syn_y = generate_synthetic(synthetic_samples, seed=seed)
        if len(real_x):
            x = np.concatenate([real_x, syn_x])
            y = np.concatenate([real_y, syn_y])
            meta["source"] = "real+synthetic"
        else:
            x, y = syn_x, syn_y
            meta["source"] = "synthetic"
        meta["synthetic_samples"] = int(len(syn_x))
    else:
        x, y = real_x, real_y
        meta["synthetic_samples"] = 0
        meta["source"] = "real"

    meta["total_samples"] = int(len(x))
    meta["positive_rate"] = float(y.mean()) if len(y) else 0.0
    return x, y, meta
