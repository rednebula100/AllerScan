"""TrayController: pystray 기반 시스템 트레이 상주 아이콘.

아이콘 루프는 run_detached()로 별도 스레드에서 실행되므로 tkinter mainloop와
충돌하지 않는다. 메뉴 콜백은 트레이 스레드에서 호출되므로, 콜백 안에서 GUI를
조작할 때는 호출측(MealApp)이 app.after(0, ...)로 마샬링해야 한다.
"""
from __future__ import annotations

from typing import Callable

import pystray
from PIL import Image, ImageDraw

# 색상 팔레트 (앱과 통일)
_BG = (26, 26, 46)
_ACCENT = (76, 201, 240)
_DANGER = (230, 57, 70)


def _make_icon_image(size: int = 64) -> Image.Image:
    """접시 위 경고 점 모양의 트레이 아이콘을 생성한다."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = 6
    # 바깥 접시 (하늘색 링)
    draw.ellipse([pad, pad, size - pad, size - pad], fill=_ACCENT)
    inner = pad + 8
    draw.ellipse([inner, inner, size - inner, size - inner], fill=_BG)
    # 중앙 경고 점 (빨강)
    c = size // 2
    r = 8
    draw.ellipse([c - r, c - r, c + r, c + r], fill=_DANGER)
    return img


class TrayController:
    """트레이 아이콘과 우클릭 메뉴를 관리한다."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("오늘 급식 보기", lambda icon, item: on_show(), default=True),
            pystray.MenuItem("알림 설정", lambda icon, item: on_settings()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", lambda icon, item: on_quit()),
        )
        self.icon = pystray.Icon(
            "AllerScan", _make_icon_image(), "AllerScan · 급식 알레르기 도우미", menu
        )

    def run_detached(self) -> None:
        """트레이 아이콘을 별도 스레드에서 실행한다."""
        self.icon.run_detached()

    def notify(self, message: str, title: str = "AllerScan") -> None:
        """트레이 아이콘에서 풍선 알림을 띄운다(보조 알림 경로)."""
        try:
            self.icon.notify(message, title)
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:  # noqa: BLE001
            pass
