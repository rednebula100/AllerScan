"""AllerScan 실행 진입점.

환경변수 NEIS_API_KEY 로 NEIS API 키를 전달한다(선택).
키가 없어도 제한된 범위로 동작하지만, 안정적인 사용을 위해 발급을 권장한다.
    https://open.neis.go.kr
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


def main() -> None:
    api_key = os.environ.get("NEIS_API_KEY", "")
    mfds_key = os.environ.get("MFDS_API_KEY", "")
    if not api_key:
        print("[안내] 환경변수 NEIS_API_KEY 가 설정되지 않았습니다. "
              "제한된 범위로 동작합니다.")
    if not mfds_key:
        print("[안내] 환경변수 MFDS_API_KEY 가 없어 식품 검색은 비활성화됩니다. "
              "식사 기록은 수동 입력으로 사용하세요.")
    app = MealApp(api_key=api_key, mfds_key=mfds_key)
    app.run()


if __name__ == "__main__":
    main()
