"""AllerPredict 1D-CNN 모델 정의 (TensorFlow/Keras).

이 모듈은 import 시 TensorFlow를 로드하므로(무거움), GUI 등 TF가 필요 없는 곳에서는
import하지 않는다. 학습(train.py)과 예측기(predictor.py의 지연 로딩)에서만 사용한다.
"""
from __future__ import annotations

import os

# TF의 장황한 로그/oneDNN 안내를 억제 (import 전에 설정해야 함)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import tensorflow as tf  # noqa: E402
from tensorflow.keras import layers, models  # noqa: E402

from .dataset import NUM_ALLERGENS  # noqa: E402


def build_model(input_len: int = NUM_ALLERGENS) -> "tf.keras.Model":
    """알레르겐 노출 벡터 -> 반응 발생 확률을 예측하는 1D-CNN을 만든다."""
    # 알레르겐 번호(위치)마다 의미가 다르므로 위치 정보를 보존해야 한다. 따라서 전역 풀링
    # (위치 불변) 대신 Flatten을 써서 "어느 위치=어느 알레르겐이 반응과 연관되는지"를
    # Dense 층이 학습하게 한다. Conv1D 층은 인접 알레르겐 조합 특징을 뽑는다.
    model = models.Sequential(
        [
            layers.Input(shape=(input_len, 1)),
            layers.Conv1D(32, kernel_size=3, activation="relu", padding="same"),
            layers.BatchNormalization(),
            layers.Conv1D(64, kernel_size=3, activation="relu", padding="same"),
            layers.Flatten(),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(32, activation="relu"),
            layers.Dense(1, activation="sigmoid"),
        ],
        name="AllerPredict_1DCNN",
    )
    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model
