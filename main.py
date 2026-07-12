"""AllerScan 실행 진입점.

API 키는 환경변수(NEIS_API_KEY, MFDS_API_KEY) 또는 앱 안의 "API 키 설정"에서 저장한
data/settings.json 중 하나로 전달된다 (환경변수가 우선). 둘 다 없으면 앱이 최초 실행
화면에서 직접 입력받는다.
"""
import os
import sys

# PyInstaller onefile/windowed(콘솔 없음) 빌드에서는 sys.stdout/stderr가 None이 되어
# print() 호출이 그대로 크래시로 이어진다. 콘솔이 없을 때는 출력을 버리도록 대체한다.
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(os.devnull, "w")

# NEIS 서버는 중간 인증서를 함께 보내지 않아 기본 CA 번들로는 SSL 검증이 실패한다.
# OS(Windows) 인증서 저장소를 사용하도록 truststore를 주입해 이 문제를 해결한다.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    print("[안내] truststore가 설치되어 있지 않습니다. "
          "SSL 오류가 발생하면 'pip install truststore'를 실행하세요.")

from gui import MealApp
from services import load_settings


def main() -> None:
    settings = load_settings()
    api_key = os.environ.get("NEIS_API_KEY") or settings.get("neis_api_key", "")
    mfds_key = os.environ.get("MFDS_API_KEY") or settings.get("mfds_api_key", "")
    app = MealApp(api_key=api_key, mfds_key=mfds_key)
    app.run()


if __name__ == "__main__":
    main()
