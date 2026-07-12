"""AllerPredict: AllerScan 식사/증상 기록 기반 알레르기 반응 예측 (1D-CNN).

주의: model.py는 import 시 TensorFlow를 로드하므로 여기서 import하지 않는다.
      학습은 train.py, 예측은 AllerPredictor(지연 로딩)를 통해 이뤄진다.
"""
from .dataset import (
    NUM_ALLERGENS,
    build_dataset_from_records,
    exposure_to_vector,
    generate_synthetic,
    load_dataset,
)
from .predictor import DEFAULT_MODEL_PATH, AllerPredictor

__all__ = [
    "NUM_ALLERGENS",
    "build_dataset_from_records",
    "exposure_to_vector",
    "generate_synthetic",
    "load_dataset",
    "AllerPredictor",
    "DEFAULT_MODEL_PATH",
]
