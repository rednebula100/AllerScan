"""gui.app.make_app_icon()으로 그린 방패 아이콘을 assets/icon.ico로 저장한다.

PyInstaller 빌드(AllerScan.spec)가 참조하는 .ico 파일을 만드는 용도.
    python tools/generate_icon.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.app import make_app_icon  # noqa: E402

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    base = make_app_icon(256)  # 고해상도로 그린 뒤 ICO 저장 시 각 크기로 축소
    base.save(OUTPUT_PATH, format="ICO", sizes=ICO_SIZES)
    print(f"저장됨: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
