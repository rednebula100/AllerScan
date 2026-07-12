"""AllerPredictor: 학습된 1D-CNN 모델을 불러와 반응 확률을 예측한다 (GUI용).

TensorFlow는 예측이 실제로 필요할 때(_load) 지연 import한다. 따라서 이 모듈을 import하는
것만으로는 TF를 로드하지 않아 GUI 시작이 느려지지 않는다.
"""
from __future__ import annotations

import os
import sys

import numpy as np

from models.menu_item import ALLERGEN_NAMES

from .dataset import NUM_ALLERGENS, exposure_to_vector

if hasattr(sys, "_MEIPASS"):
    _APP_ROOT = sys._MEIPASS
else:
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MODEL_PATH = os.path.join(
    _APP_ROOT, "allerpredict", "artifacts", "allerpredict_model.keras"
)


class AllerPredictor:
    """학습된 모델을 지연 로딩해 알레르겐 노출로부터 반응 확률을 예측한다."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH) -> None:
        self.model_path = model_path
        self._model = None

    @property
    def available(self) -> bool:
        """학습된 모델 파일이 존재하는지."""
        return os.path.exists(self.model_path)

    def _load(self):
        if self._model is None:
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
            os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
            import tensorflow as tf

            self._model = tf.keras.models.load_model(self.model_path)
        return self._model

    def predict_probability(self, exposure: dict[int, float]) -> float:
        """알레르겐 노출 dict에 대한 반응 발생 확률(0~1)을 반환한다."""
        vec = exposure_to_vector(exposure).reshape(1, NUM_ALLERGENS, 1)
        return float(self._load().predict(vec, verbose=0)[0, 0])

    def per_allergen_risk(self) -> list[tuple[int, str, float]]:
        """각 알레르겐을 단독 노출했을 때의 예측 확률로 위험도를 매긴다.

        모델이 어떤 알레르겐을 위험하게 보는지 해석하는 용도. 확률 내림차순 정렬.
        반환: [(번호, 이름, 확률), ...]
        """
        model = self._load()
        vecs = np.zeros((NUM_ALLERGENS, NUM_ALLERGENS, 1), dtype=np.float32)
        for i in range(NUM_ALLERGENS):
            vecs[i, i, 0] = 1.0
        probs = model.predict(vecs, verbose=0).reshape(-1)
        ranked = [
            (i + 1, ALLERGEN_NAMES[i + 1], float(probs[i])) for i in range(NUM_ALLERGENS)
        ]
        ranked.sort(key=lambda t: t[2], reverse=True)
        return ranked
