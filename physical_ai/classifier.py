"""FoodClassifier: Teachable Machine 이미지 분류 모델로 식품을 인식하고 알레르겐을 매핑한다.

physical_ai/keras_model.h5 + labels.txt (Teachable Machine "Standard" 이미지 프로젝트 내보내기)를
사용한다. TensorFlow 2.16+ (Keras 3)에서는 이 구형 h5 포맷을 직접 로드할 수 없어서(레이어 설정에
있는 'groups' 인자 비호환 + 중첩 Functional 모델 재구성 실패), 레거시 호환 패키지인 tf_keras로
로드한다 (pip install tf-keras). AllerPredict가 쓰는 일반 tf.keras와는 별개 네임스페이스라
같은 프로세스 안에서 서로 간섭하지 않는다.

TensorFlow(tf_keras)는 실제로 분류가 필요할 때(_load) 지연 import한다.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

# PyInstaller onefile 빌드에서는 __file__이 실제 데이터 파일 위치와 다를 수 있어
# (AllerPredict와 동일한 이유), 프리즈 여부에 따라 기준 경로를 분기한다.
if hasattr(sys, "_MEIPASS"):
    _APP_ROOT = sys._MEIPASS
else:
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join(_APP_ROOT, "physical_ai", "keras_model.h5")
LABELS_PATH = os.path.join(_APP_ROOT, "physical_ai", "labels.txt")

IMAGE_SIZE = (224, 224)
CONFIDENCE_THRESHOLD = 0.6

# 클래스명(labels.txt 순서) -> 알레르기 번호 집합. 빈 집합 = 안전, None = 매핑 불가("기타").
ALLERGEN_MAP: dict[str, set[int] | None] = {
    "우유/유제품": {2},
    "달걀": {1},
    "밀가루/빵": {6},
    "갑각류(새우/게)": {8, 9},
    "견과류": {4, 14, 19},
    "채소/과일 (안전)": set(),
    "기타": None,
}

UNKNOWN_RESULT = {"class_name": "판단불가", "confidence": 0.0, "allergens": None, "risk_level": "판단불가"}


def _load_labels(path: str = LABELS_PATH) -> list[str]:
    """'0 우유/유제품' 형식의 labels.txt를 인덱스 순서의 이름 리스트로 읽는다."""
    labels: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 맨 앞 인덱스 숫자와 공백을 떼어낸다 (예: "0 우유/유제품" -> "우유/유제품")
            parts = line.split(" ", 1)
            name = parts[1].strip() if len(parts) == 2 and parts[0].isdigit() else line
            labels.append(name)
    return labels


class FoodClassifier:
    """Teachable Machine 모델을 지연 로딩해 식품 이미지를 분류한다."""

    def __init__(self, model_path: str = MODEL_PATH, labels_path: str = LABELS_PATH) -> None:
        self.model_path = model_path
        self.labels_path = labels_path
        self._model = None
        self._labels: list[str] | None = None

    @property
    def available(self) -> bool:
        return os.path.exists(self.model_path) and os.path.exists(self.labels_path)

    @property
    def is_loaded(self) -> bool:
        """모델이 이미 메모리에 로드되어 있는지 (최초 1회만 수 초 걸리는 로딩을 UI에서
        안내하는 데 쓴다)."""
        return self._model is not None

    def _load(self):
        if self._model is None:
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
            import tf_keras

            self._model = tf_keras.models.load_model(self.model_path, compile=False)
            self._labels = _load_labels(self.labels_path)
        return self._model

    @staticmethod
    def _preprocess(image: np.ndarray) -> np.ndarray:
        """RGB uint8 HxWx3 배열을 Teachable Machine 표준 전처리(224x224, [-1,1] 정규화)로 변환."""
        pil_img = Image.fromarray(image.astype(np.uint8)).convert("RGB")
        pil_img = pil_img.resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
        arr = np.asarray(pil_img).astype(np.float32)
        normalized = (arr / 127.5) - 1.0
        return normalized[np.newaxis, ...]

    def classify_image(self, image: np.ndarray) -> dict:
        """RGB 이미지(H, W, 3 uint8)를 분류한다.

        반환: {"class_name": str, "confidence": float, "allergens": set[int] | None,
               "risk_level": "안전" | "주의" | "판단불가"}
        신뢰도가 CONFIDENCE_THRESHOLD(60%) 미만이면 무조건 판단불가로 처리한다.
        """
        if not self.available:
            return dict(UNKNOWN_RESULT)

        model = self._load()
        batch = self._preprocess(image)
        probs = model.predict(batch, verbose=0)[0]
        idx = int(np.argmax(probs))
        confidence = float(probs[idx])
        class_name = self._labels[idx] if self._labels and idx < len(self._labels) else "기타"

        if confidence < CONFIDENCE_THRESHOLD:
            return {"class_name": class_name, "confidence": confidence, "allergens": None,
                     "risk_level": "판단불가"}

        allergens = ALLERGEN_MAP.get(class_name)
        if allergens is None:
            risk_level = "판단불가"
        elif allergens:
            risk_level = "주의"
        else:
            risk_level = "안전"

        return {
            "class_name": class_name,
            "confidence": confidence,
            "allergens": allergens,
            "risk_level": risk_level,
        }

    def classify_from_webcam_frame(self, frame: np.ndarray) -> dict:
        """OpenCV 웹캠 프레임(BGR, H x W x 3)을 분류한다."""
        rgb = frame[:, :, ::-1]  # BGR -> RGB (cv2.cvtColor와 동일 결과, 의존성 추가 없이 처리)
        return self.classify_image(rgb)
