"""Windows 토스트 알림 (plyer 사용). 어떤 스레드에서도 안전하게 호출 가능."""
from __future__ import annotations


def send_notification(title: str, message: str, timeout: int = 8) -> bool:
    """토스트 알림을 띄운다. 실패해도 예외를 던지지 않고 False를 반환한다."""
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="AllerScan",
            timeout=timeout,
        )
        return True
    except Exception:  # noqa: BLE001 - 알림 실패가 앱을 중단시켜선 안 됨
        return False
