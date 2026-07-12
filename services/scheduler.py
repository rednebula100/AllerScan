"""AlarmScheduler: 매일 지정 시각에 콜백을 실행하는 백그라운드 스케줄러.

schedule 라이브러리를 별도 데몬 스레드에서 돌려 GUI와 충돌하지 않게 한다.
"""
from __future__ import annotations

import threading
from typing import Callable

import schedule


class AlarmScheduler:
    """매일 hour:minute 에 callback을 호출한다."""

    def __init__(self, callback: Callable[[], None], hour: int = 7, minute: int = 0) -> None:
        self._callback = callback
        self.hour: int = hour
        self.minute: int = minute
        # 전역 schedule을 오염시키지 않도록 독립 Scheduler 인스턴스 사용
        self._scheduler = schedule.Scheduler()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def time_str(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def start(self) -> None:
        """스케줄러 스레드를 시작한다."""
        self._register_job()
        self._thread = threading.Thread(target=self._run, name="AlarmScheduler", daemon=True)
        self._thread.start()

    def set_time(self, hour: int, minute: int) -> None:
        """알림 시각을 변경하고 즉시 재등록한다."""
        self.hour = hour
        self.minute = minute
        self._register_job()

    def _register_job(self) -> None:
        self._scheduler.clear()
        self._scheduler.every().day.at(self.time_str).do(self._safe_run)

    def _safe_run(self) -> None:
        try:
            self._callback()
        except Exception:  # noqa: BLE001 - 콜백 오류로 스레드가 죽으면 안 됨
            pass

    def _run(self) -> None:
        # 20초마다 실행 대기 작업을 확인
        while not self._stop.is_set():
            self._scheduler.run_pending()
            self._stop.wait(20)

    def stop(self) -> None:
        """스케줄러를 정지한다."""
        self._stop.set()
        self._scheduler.clear()
