"""physical_ai: Teachable Machine 이미지 분류 모델로 식품을 인식해 알레르겐을 추정한다.

무거운 tf_keras는 FoodClassifier 내부에서 지연 import한다(GUI 시작 속도 유지).
설치: pip install -r physical_ai/requirements.txt
"""
from .classifier import ALLERGEN_MAP, CONFIDENCE_THRESHOLD, FoodClassifier

__all__ = ["FoodClassifier", "ALLERGEN_MAP", "CONFIDENCE_THRESHOLD"]
