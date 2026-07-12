"""MealApp: customtkinter 기반 급식 알레르기 + 식사/증상 기록 도우미 GUI."""
from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from collections import Counter
from datetime import datetime, timedelta
from tkinter import messagebox
from typing import NamedTuple

import customtkinter as ctk
import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageDraw, ImageFont

from models import (
    AllergyProfile,
    CorrelationAnalyzer,
    MealFetcher,
    MealRecord,
    MenuItem,
    MFDSFetcher,
    SymptomRecord,
)
from models.menu_item import ALLERGEN_NAMES
from models.symptom_record import SYMPTOM_TYPES
from services import AlarmScheduler, TrayController, load_settings, save_settings, send_notification

# matplotlib이 한글(요일/성분명)을 렌더링하도록 Windows 기본 한글 폰트 지정
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

# ----------------------------- 색상 팔레트 ----------------------------- #
BG = "#1a1a2e"
PANEL = "#16213e"
SAFE = "#2d6a4f"
CAUTION = "#e9c46a"
DANGER = "#e63946"
ACCENT = "#4cc9f0"
ACCENT_HOVER = "#7dd8f5"
CARD_TEXT_LIGHT = "#f1faee"
CARD_TEXT_DARK = "#1a1a2e"
BADGE_GRAY = "#3a4266"
MUTED = "#5a6483"
DIVIDER = "#2a2a4a"

FONT = "Malgun Gothic"
WEEKDAY_NAMES = ["월", "화", "수", "목", "금"]
MEAL_TAB = "🍽 식사 기록"
SYMPTOM_TAB = "⚡ 증상 기록"
ANALYSIS_TAB = "📊 분석"
TAB_ORDER = WEEKDAY_NAMES + [MEAL_TAB, SYMPTOM_TAB, ANALYSIS_TAB]

DATA_DIR = "data"
PRESET_DIR = os.path.join(DATA_DIR, "presets")
MEALS_DIR = os.path.join(DATA_DIR, "meals")
SYMPTOMS_DIR = os.path.join(DATA_DIR, "symptoms")
DATASCI_RESULTS_DIR = os.path.join("datasci", "results")

SEVERITY_LABELS = {1: "매우 약함", 2: "약함", 3: "보통", 4: "심함", 5: "매우 심함"}


def make_app_icon(size: int = 32) -> Image.Image:
    """방패 안에 'A'가 들어간 앱 아이콘을 프로그래밍 방식으로 생성한다."""
    scale = 8
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = s * 0.08
    shoulder = s * 0.26
    shield = [
        (s / 2, pad),
        (s - pad, shoulder),
        (s - pad, s * 0.56),
        (s / 2, s - pad),
        (pad, s * 0.56),
        (pad, shoulder),
    ]
    d.polygon(shield, fill=(76, 201, 240, 255))  # ACCENT
    # 안쪽 살짝 어두운 방패로 입체감
    inset = s * 0.12
    inner = [
        (s / 2, pad + inset * 0.7),
        (s - pad - inset, shoulder + inset * 0.5),
        (s - pad - inset, s * 0.54),
        (s / 2, s - pad - inset),
        (pad + inset, s * 0.54),
        (pad + inset, shoulder + inset * 0.5),
    ]
    d.polygon(inner, fill=(22, 33, 62, 255))  # PANEL

    # 가운데 'A'
    try:
        font = ImageFont.truetype("arialbd.ttf", int(s * 0.42))
    except OSError:
        font = ImageFont.load_default()
    d.text((s / 2, s * 0.46), "A", fill=(76, 201, 240, 255), font=font, anchor="mm")

    return img.resize((size, size), Image.LANCZOS)


class _CardRefs(NamedTuple):
    """카드 하나의 위젯 참조. 프로필이 바뀔 때 재생성 없이 색상만 갱신하는 데 쓴다."""
    item: MenuItem
    card: ctk.CTkFrame
    name_label: ctk.CTkLabel
    badges: dict[int, ctk.CTkLabel]


class MealApp(ctk.CTk):
    """급식 알레르기 필터 + 식사/증상 기록 애플리케이션."""

    def __init__(self, api_key: str = "", mfds_key: str = "") -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.fetcher = MealFetcher(api_key)
        self.mfds = MFDSFetcher(mfds_key)
        self.profile = AllergyProfile()

        # 재사용 폰트 (제목 16 Bold / 본문 13 / 뱃지 11)
        self.f_title = ctk.CTkFont(family=FONT, size=16, weight="bold")
        self.f_brand = ctk.CTkFont(family=FONT, size=18, weight="bold")
        self.f_body = ctk.CTkFont(family=FONT, size=13)
        self.f_body_bold = ctk.CTkFont(family=FONT, size=13, weight="bold")
        self.f_badge = ctk.CTkFont(family=FONT, size=11)
        self.f_small = ctk.CTkFont(family=FONT, size=11)

        self.search_results: list[dict] = []
        self.selected_school: dict | None = None
        self.current_date: datetime = datetime.now()
        self.week_data: dict[str, list[MenuItem]] = {}
        self.check_vars: dict[int, tk.IntVar] = {}
        self._tab_frames: dict[str, ctk.CTkScrollableFrame] = {}
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        self._tab_content: dict[str, ctk.CTkScrollableFrame] = {}
        self._active_tab: str = WEEKDAY_NAMES[0]
        self._cards: dict[str, list[_CardRefs]] = {}
        self._dirty_tabs: dict[str, set[int] | None] = {}
        self._analysis_canvas: FigureCanvasTkAgg | None = None
        self._corr_canvas: FigureCanvasTkAgg | None = None
        self._exposure_canvas: FigureCanvasTkAgg | None = None
        self._quitting = False

        # 식사/증상 기록 상태
        self._meal_foods: list[dict] = []
        self._meal_search_results: list[dict] = []
        self._meal_allergen_vars: dict[int, tk.IntVar] = {}
        self._symptom_selected: set[str] = set()
        self._symptom_type_btns: dict[str, ctk.CTkButton] = {}

        self.title("AllerScan · 학교급식 알레르기 필터")
        self.geometry("1160x780")
        self.minsize(1000, 660)
        self.configure(fg_color=BG)

        self._build_topbar()
        self._build_body()
        self._build_bottom()

        self._select_tab(WEEKDAY_NAMES[0])
        self._rebuild_week()  # 초기 빈 상태 렌더 (위젯 구조 생성)

        # 백그라운드 서비스: 트레이 상주 + 매일 아침 알림 스케줄러
        self.tray = TrayController(
            on_show=lambda: self.after(0, self._show_window),
            on_settings=lambda: self.after(0, self._open_alarm_settings),
            on_quit=lambda: self.after(0, self._quit_app),
        )
        self.tray.run_detached()

        self.scheduler = AlarmScheduler(callback=self._check_today_danger, hour=7, minute=0)
        self.scheduler.start()

        self.protocol("WM_DELETE_WINDOW", self._quit_app)

        # NEIS 키가 전혀 없으면 창이 뜬 직후 API 키 설정 다이얼로그를 자동으로 띄운다.
        self.after(300, self._maybe_show_onboarding)

    # ================================================================== #
    # 레이아웃 구성
    # ================================================================== #
    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=50)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        # 앱 아이콘 + 브랜드 (수직 중앙)
        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(side="left", padx=(16, 20))
        self._icon_image = ctk.CTkImage(
            light_image=make_app_icon(28), dark_image=make_app_icon(28), size=(28, 28)
        )
        ctk.CTkLabel(brand, image=self._icon_image, text="").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(brand, text="AllerScan", font=self.f_brand, text_color=ACCENT).pack(side="left")

        self.search_entry = ctk.CTkEntry(
            bar, width=210, height=32, placeholder_text="학교명 검색 (예: 서울고등학교)",
            font=self.f_body,
        )
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _e: self._on_search())

        self.search_btn = ctk.CTkButton(
            bar, text="검색", width=60, height=32, corner_radius=8, font=self.f_body,
            fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER, command=self._on_search,
        )
        self.search_btn.pack(side="left", padx=(0, 8))

        self.school_menu = ctk.CTkOptionMenu(
            bar, width=270, height=32, font=self.f_body,
            values=["검색 결과가 여기 표시됩니다"], command=self._on_school_selected,
            fg_color="#0f3460", button_color="#0f3460", corner_radius=8,
        )
        self.school_menu.set("검색 결과가 여기 표시됩니다")
        self.school_menu.pack(side="left", padx=(0, 16))

        self.settings_btn = ctk.CTkButton(
            bar, text="⚙", width=32, height=32, corner_radius=8, font=self.f_body,
            fg_color="#0f3460", hover_color="#1b4a80", command=lambda: self._open_api_key_dialog(),
        )
        self.settings_btn.pack(side="right", padx=(6, 16))

        self.next_btn = ctk.CTkButton(
            bar, text="다음주 ▶", width=82, height=32, corner_radius=8, font=self.f_body,
            fg_color="#0f3460", hover_color="#1b4a80", command=lambda: self._shift_week(1),
        )
        self.next_btn.pack(side="right", padx=6)
        self.week_label = ctk.CTkLabel(bar, text="", font=self.f_body)
        self.week_label.pack(side="right", padx=6)
        self.prev_btn = ctk.CTkButton(
            bar, text="◀ 이전주", width=82, height=32, corner_radius=8, font=self.f_body,
            fg_color="#0f3460", hover_color="#1b4a80", command=lambda: self._shift_week(-1),
        )
        self.prev_btn.pack(side="right", padx=6)

        # 상단바 아래 얇은 구분선
        ctk.CTkFrame(self, fg_color=DIVIDER, height=1, corner_radius=0).pack(side="top", fill="x")

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(side="top", fill="both", expand=True, padx=12, pady=(10, 0))

        self._build_left_panel(body)

        center = ctk.CTkFrame(body, fg_color=BG, corner_radius=0)
        center.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.status_label = ctk.CTkLabel(
            center, text="학교를 검색하고 선택하면 이번 주 급식이 표시됩니다.",
            text_color="#9aa5c4", font=self.f_body,
        )
        self.status_label.pack(anchor="w", padx=6, pady=(0, 6))

        # 위험 회피 요약 배너
        self.banner = ctk.CTkFrame(center, fg_color=PANEL, corner_radius=10)
        self.banner_title = ctk.CTkLabel(
            self.banner, text="", font=self.f_body_bold,
            text_color=CARD_TEXT_LIGHT, anchor="w", justify="left",
        )
        self.banner_title.pack(anchor="w", padx=16, pady=(8, 0))
        self.banner_sub = ctk.CTkLabel(
            self.banner, text="", font=self.f_body,
            text_color=CARD_TEXT_LIGHT, anchor="w", justify="left",
        )
        self.banner_sub.pack(anchor="w", padx=16, pady=(0, 8))

        # pill 형태 탭바 (박스/구분선 없음)
        self._tabbar = ctk.CTkFrame(center, fg_color=BG, corner_radius=0)
        self._tabbar.pack(fill="x", pady=(2, 8))

        self._content_area = ctk.CTkFrame(center, fg_color=BG, corner_radius=0)
        self._content_area.pack(fill="both", expand=True)

        widths = {**{w: 46 for w in WEEKDAY_NAMES}, MEAL_TAB: 118, SYMPTOM_TAB: 118, ANALYSIS_TAB: 92}
        for name in TAB_ORDER:
            btn = ctk.CTkButton(
                self._tabbar, text=name, width=widths[name], height=34, corner_radius=17,
                font=self.f_body, fg_color="transparent", text_color=MUTED, hover_color=PANEL,
                command=lambda n=name: self._select_tab(n),
            )
            btn.pack(side="left", padx=(0, 6))
            self._tab_buttons[name] = btn

            content = ctk.CTkScrollableFrame(self._content_area, fg_color="transparent")
            self._tab_content[name] = content

        for name in WEEKDAY_NAMES:
            self._tab_frames[name] = self._tab_content[name]

        self._build_meal_tab(self._tab_content[MEAL_TAB])
        self._build_symptom_tab(self._tab_content[SYMPTOM_TAB])
        self._build_analysis_tab(self._tab_content[ANALYSIS_TAB])

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(parent, fg_color=PANEL, width=228, corner_radius=12)
        panel.pack(side="left", fill="y")
        panel.pack_propagate(False)

        ctk.CTkLabel(panel, text="내 알레르기", font=self.f_title, text_color=ACCENT).pack(
            anchor="w", padx=16, pady=(16, 4)
        )
        ctk.CTkLabel(
            panel, text="해당하는 항목을 모두 체크하세요", text_color="#9aa5c4", font=self.f_small,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        grid = ctk.CTkFrame(panel, fg_color="transparent")
        grid.pack(fill="x", padx=12)
        grid.grid_columnconfigure((0, 1), weight=1)
        for num, name in ALLERGEN_NAMES.items():
            var = tk.IntVar(value=0)
            self.check_vars[num] = var
            cb = ctk.CTkCheckBox(
                grid, text=f"{num}.{name}", variable=var, font=self.f_body,
                checkbox_width=18, checkbox_height=18, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=lambda n=num: self._on_toggle_allergen(n),
            )
            cb.grid(row=(num - 1) // 2, column=(num - 1) % 2, sticky="w", padx=6, pady=8)

        ctk.CTkFrame(panel, fg_color=DIVIDER, height=1).pack(fill="x", padx=16, pady=(14, 0))

        ctk.CTkLabel(panel, text="프리셋", font=self.f_body_bold, text_color=ACCENT).pack(
            anchor="w", padx=16, pady=(12, 4)
        )
        self.preset_entry = ctk.CTkEntry(panel, placeholder_text="프리셋 이름", font=self.f_body)
        self.preset_entry.pack(fill="x", padx=16, pady=(0, 6))
        btn_row = ctk.CTkFrame(panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        btn_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            btn_row, text="저장", corner_radius=8, font=self.f_body, fg_color=SAFE,
            hover_color="#3c8c69", command=self._on_save_preset,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            btn_row, text="불러오기", corner_radius=8, font=self.f_body, fg_color="#0f3460",
            hover_color="#1b4a80", command=self._on_load_preset,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_bottom(self) -> None:
        ctk.CTkFrame(self, fg_color=DIVIDER, height=1, corner_radius=0).pack(side="bottom", fill="x")
        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=44)
        bar.pack(side="bottom", fill="x")
        self.calorie_label = ctk.CTkLabel(
            bar, text="🔥 총 칼로리: -", font=self.f_body_bold, text_color=CAUTION,
        )
        self.calorie_label.pack(side="right", padx=20, pady=8)

    # ------------------------------------------------------------------ #
    # 커스텀 탭 전환
    # ------------------------------------------------------------------ #
    def _select_tab(self, name: str) -> None:
        for frame in self._tab_content.values():
            frame.pack_forget()
        self._tab_content[name].pack(fill="both", expand=True)
        self._active_tab = name
        self._restyle_tab_buttons()

        if name == ANALYSIS_TAB:
            self._render_analysis()
        elif name in WEEKDAY_NAMES:
            self._refresh_tab_colors(name)
            self._update_calorie()

    def _restyle_tab_buttons(self) -> None:
        """선택 탭은 강조색 pill, 미선택은 투명+회색. 급식 없는 요일은 더 흐리게."""
        dates = self._week_dates()
        no_meal = {
            WEEKDAY_NAMES[i]
            for i in range(5)
            if not self.week_data.get(dates[i].strftime("%Y%m%d"))
        }
        for name, btn in self._tab_buttons.items():
            if name == self._active_tab:
                btn.configure(fg_color=ACCENT, text_color=CARD_TEXT_LIGHT, hover_color=ACCENT_HOVER)
            else:
                dim = MUTED if name not in no_meal else "#39415f"
                btn.configure(fg_color="transparent", text_color=dim, hover_color=PANEL)

    # ================================================================== #
    # 이벤트 핸들러 (급식/프로필)
    # ================================================================== #
    def _on_toggle_allergen(self, num: int) -> None:
        if self.check_vars[num].get():
            self.profile.add(num)
        else:
            self.profile.remove(num)
        self._invalidate_colors({num})

    def _on_search(self) -> None:
        query = self.search_entry.get().strip()
        if not query:
            return
        self.search_btn.configure(state="disabled", text="...")
        self.status_label.configure(text=f"'{query}' 검색 중...")

        def worker() -> None:
            try:
                results = self.fetcher.search_school(query)
                self.after(0, lambda: self._on_search_done(results))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda: self._on_error("검색 실패", msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_done(self, results: list[dict]) -> None:
        self.search_btn.configure(state="normal", text="검색")
        self.search_results = results
        if not results:
            self.school_menu.configure(values=["검색 결과 없음"])
            self.school_menu.set("검색 결과 없음")
            self.status_label.configure(text="검색 결과가 없습니다. 학교명을 확인해주세요.")
            return
        labels = [self._school_label(s) for s in results]
        self.school_menu.configure(values=labels)
        self.school_menu.set(labels[0])
        self.status_label.configure(text=f"{len(results)}개 학교를 찾았습니다. 학교를 선택하세요.")
        self._on_school_selected(labels[0])

    @staticmethod
    def _school_label(school: dict) -> str:
        addr = school.get("address", "")
        region = addr.split()[0] if addr else school.get("kind", "")
        return f"{school['name']} ({region})"

    def _on_school_selected(self, label: str) -> None:
        for school in self.search_results:
            if self._school_label(school) == label:
                self.selected_school = school
                self._load_week()
                return

    def _shift_week(self, direction: int) -> None:
        self.current_date = self.current_date + timedelta(weeks=direction)
        if self.selected_school:
            self._load_week()
        else:
            self._rebuild_week()

    def _load_week(self) -> None:
        if not self.selected_school:
            return
        school = self.selected_school
        date = self.current_date
        self.status_label.configure(text=f"🔄 {school['name']} 급식을 불러오는 중...")

        def worker() -> None:
            try:
                data = self.fetcher.fetch_week(
                    school["office_code"], school["school_code"], date
                )
                self.after(0, lambda: self._on_week_loaded(data))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda: self._on_error("급식 조회 실패", msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_week_loaded(self, data: dict[str, list[MenuItem]]) -> None:
        self.week_data = data
        name = self.selected_school["name"] if self.selected_school else ""
        self.status_label.configure(text=f"✅ {name} · 이번 주 급식")
        today = datetime.now()
        monday = self.current_date - timedelta(days=self.current_date.weekday())
        if monday.date() <= today.date() <= (monday + timedelta(days=4)).date():
            self._select_tab(WEEKDAY_NAMES[today.weekday()])
        self._rebuild_week()

    def _on_error(self, title: str, message: str) -> None:
        self.search_btn.configure(state="normal", text="검색")
        self.status_label.configure(text=f"⚠️ {message}")
        messagebox.showerror(title, message)

    # ================================================================== #
    # 렌더링 (급식 카드)
    # ================================================================== #
    def _week_dates(self) -> list[datetime]:
        monday = self.current_date - timedelta(days=self.current_date.weekday())
        return [monday + timedelta(days=i) for i in range(5)]

    def _rebuild_week(self) -> None:
        """주 데이터가 바뀔 때만 호출: 탭의 카드 위젯을 전부 새로 만드는 무거운 연산."""
        dates = self._week_dates()
        self.week_label.configure(
            text=f"{dates[0].strftime('%Y.%m.%d')} ~ {dates[-1].strftime('%m.%d')}"
        )

        self._cards = {}
        for i, name in enumerate(WEEKDAY_NAMES):
            frame = self._tab_frames[name]
            for widget in frame.winfo_children():
                widget.destroy()

            date = dates[i]
            items = self.week_data.get(date.strftime("%Y%m%d"), [])
            ctk.CTkLabel(
                frame, text=f"{date.strftime('%m월 %d일')} ({name})",
                font=self.f_title, text_color=ACCENT,
            ).pack(anchor="w", padx=8, pady=(6, 10))

            if not items:
                ctk.CTkLabel(
                    frame, text="급식 정보 없음", text_color="#9aa5c4", font=self.f_body,
                ).pack(anchor="center", pady=40)
                self._cards[name] = []
                continue
            self._cards[name] = [self._make_card(frame, item) for item in items]

        self._dirty_tabs.clear()
        self._refresh_summary()

    def _invalidate_colors(self, changed: set[int] | None) -> None:
        """프로필 변화 시: 보이는 탭만 즉시 갱신, 나머지는 dirty 표시 후 지연 갱신."""
        for name in self._cards:
            self._mark_dirty(name, changed)
        if self._active_tab in WEEKDAY_NAMES:
            self._refresh_tab_colors(self._active_tab)
        self._refresh_summary()

    def _mark_dirty(self, name: str, changed: set[int] | None) -> None:
        current = self._dirty_tabs.get(name, False)
        if current is None:
            return
        if changed is None:
            self._dirty_tabs[name] = None
        elif current is False:
            self._dirty_tabs[name] = set(changed)
        else:
            current |= changed

    def _refresh_tab_colors(self, name: str) -> None:
        if name not in self._dirty_tabs:
            return
        pending = self._dirty_tabs[name]
        for refs in self._cards.get(name, []):
            if pending is None or (refs.item.allergens & pending):
                self._apply_card_style(refs)
        del self._dirty_tabs[name]

    def _refresh_summary(self) -> None:
        self._update_calorie()
        self._update_banner()
        self._restyle_tab_buttons()
        if self._active_tab == ANALYSIS_TAB:
            self._render_analysis()

    def _make_card(self, parent: ctk.CTkScrollableFrame, item: MenuItem) -> _CardRefs:
        card = ctk.CTkFrame(parent, corner_radius=12, height=88)
        card.pack(fill="x", padx=8, pady=6)
        card.pack_propagate(False)

        name_label = ctk.CTkLabel(card, font=self.f_title, anchor="w", justify="left")
        name_label.pack(anchor="w", padx=14, pady=(12, 4))

        badge_row = ctk.CTkFrame(card, fg_color="transparent")
        badge_row.pack(anchor="w", padx=12, pady=(0, 10))
        badges: dict[int, ctk.CTkLabel] = {}
        if item.allergens:
            for num in sorted(item.allergens):
                badge = ctk.CTkLabel(
                    badge_row, text=f" {ALLERGEN_NAMES[num]} ", font=self.f_badge,
                    text_color=CARD_TEXT_LIGHT, corner_radius=8,
                )
                badge.pack(side="left", padx=(0, 6))
                badges[num] = badge
        else:
            ctk.CTkLabel(badge_row, text="알레르기 성분 없음", font=self.f_badge).pack(side="left")

        refs = _CardRefs(item=item, card=card, name_label=name_label, badges=badges)
        self._apply_card_style(refs)
        return refs

    def _apply_card_style(self, refs: _CardRefs) -> None:
        status = self.profile.is_safe(refs.item.allergens)
        color = {"safe": SAFE, "caution": CAUTION, "danger": DANGER}[status]
        text_color = CARD_TEXT_DARK if status == "caution" else CARD_TEXT_LIGHT

        if refs.card.cget("fg_color") != color:
            refs.card.configure(fg_color=color)
        icon = "⚠️ " if status in ("caution", "danger") else "✅ "
        new_text = f"{icon}{refs.item.name}"
        if refs.name_label.cget("text") != new_text or refs.name_label.cget("text_color") != text_color:
            refs.name_label.configure(text=new_text, text_color=text_color)

        if not refs.badges:
            return
        ordered = sorted(refs.badges, key=lambda n: (n not in self.profile.allergies, n))
        for num in ordered:
            target = DANGER if num in self.profile.allergies else BADGE_GRAY
            badge = refs.badges[num]
            if badge.cget("fg_color") != target:
                badge.configure(fg_color=target)
            badge.pack_forget()
            badge.pack(side="left", padx=(0, 6))

    def _update_calorie(self) -> None:
        if self._active_tab not in WEEKDAY_NAMES:
            self.calorie_label.configure(text="🔥 총 칼로리: -")
            return
        idx = WEEKDAY_NAMES.index(self._active_tab)
        ymd = self._week_dates()[idx].strftime("%Y%m%d")
        kcal = self.fetcher.week_calories.get(ymd, 0.0)
        if kcal > 0:
            self.calorie_label.configure(text=f"🔥 {self._active_tab}요일 총 칼로리: {kcal:.0f} kcal")
        else:
            self.calorie_label.configure(text="🔥 총 칼로리: -")

    # ================================================================== #
    # 통계 / 요약 배너
    # ================================================================== #
    def _compute_stats(self) -> dict:
        dates = self._week_dates()
        per_day: list[dict] = []
        allergen_hits: Counter = Counter()
        totals = {"safe": 0, "caution": 0, "danger": 0}

        for i, name in enumerate(WEEKDAY_NAMES):
            ymd = dates[i].strftime("%Y%m%d")
            items = self.week_data.get(ymd, [])
            counts = {"safe": 0, "caution": 0, "danger": 0}
            for it in items:
                st = self.profile.is_safe(it.allergens)
                counts[st] += 1
                totals[st] += 1
                for a in (it.allergens & self.profile.allergies):
                    allergen_hits[a] += 1
            if not items:
                day_status = "none"
            elif counts["danger"]:
                day_status = "danger"
            elif counts["caution"]:
                day_status = "caution"
            else:
                day_status = "safe"
            per_day.append(
                {
                    "name": name, "date": dates[i], "ymd": ymd, "status": day_status,
                    "counts": counts, "kcal": self.fetcher.week_calories.get(ymd, 0.0),
                    "has": bool(items),
                }
            )
        return {"per_day": per_day, "allergen_hits": allergen_hits, "totals": totals}

    def _update_banner(self) -> None:
        stats = self._compute_stats()
        per_day = stats["per_day"]
        if not any(d["has"] for d in per_day):
            self.banner.pack_forget()
            return

        statuses = [d["status"] for d in per_day if d["has"]]
        if "danger" in statuses:
            color, tcolor = DANGER, CARD_TEXT_LIGHT
        elif "caution" in statuses:
            color, tcolor = CAUTION, CARD_TEXT_DARK
        else:
            color, tcolor = SAFE, CARD_TEXT_LIGHT
        self.banner.configure(fg_color=color)
        self.banner_title.configure(text_color=tcolor)
        self.banner_sub.configure(text_color=tcolor)

        if not self.profile.allergies:
            title = "🛡  왼쪽에서 내 알레르기를 선택하면 위험 요약이 표시됩니다."
            sub = "현재 모든 메뉴가 안전으로 표시됩니다."
        else:
            safe_days = [d["name"] for d in per_day if d["status"] == "safe"]
            title = "🛡  이번 주 안전한 날: " + (", ".join(safe_days) if safe_days else "없음")
            hits = stats["allergen_hits"]
            if hits:
                top_num, top_cnt = hits.most_common(1)[0]
                sub = (
                    f"⚠️  {ALLERGEN_NAMES[top_num]}이(가) 이번 주 {top_cnt}회 등장  ·  "
                    f"위험 {stats['totals']['danger']}건 / 주의 {stats['totals']['caution']}건"
                )
            else:
                sub = "✅  이번 주 내 알레르기와 겹치는 메뉴가 없습니다."
        self.banner_title.configure(text=title)
        self.banner_sub.configure(text=sub)
        self.banner.pack(fill="x", pady=(0, 8), before=self._tabbar)

    # ================================================================== #
    # 분석 탭
    # ================================================================== #
    @staticmethod
    def _style_ax(ax) -> None:
        ax.set_facecolor(BG)
        ax.tick_params(colors=CARD_TEXT_LIGHT, labelsize=11)
        for spine in ax.spines.values():
            spine.set_color(DIVIDER)

    def _divider(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkFrame(parent, fg_color=DIVIDER, height=1).pack(fill="x", padx=8, pady=(6, 10))

    def _build_analysis_tab(self, parent: ctk.CTkScrollableFrame) -> None:
        # 주간 영양 파트 (프로필/급식 변화 시 재렌더)
        self._analysis_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._analysis_frame.pack(fill="x")

        # 기록 분석 파트 (버튼 클릭 시에만 갱신 — 프로필 변화에 지워지지 않음)
        self._divider(parent)
        ctk.CTkLabel(
            parent, text="식사-증상 시차(lag) 상관 분석", font=self.f_title, text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(4, 4))
        ctk.CTkButton(
            parent, text="🔬 분석 실행", width=120, corner_radius=8, font=self.f_body,
            fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER, command=self._run_correlation,
        ).pack(anchor="w", padx=8, pady=(0, 8))
        self._corr_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._corr_frame.pack(fill="x")
        ctk.CTkLabel(
            self._corr_frame, text="‘분석 실행’을 누르면 기록을 분석합니다.",
            text_color=MUTED, font=self.f_body,
        ).pack(anchor="w", padx=12, pady=6)

        self._divider(parent)
        ctk.CTkLabel(
            parent, text="오늘의 누적 알레르기 노출량", font=self.f_title, text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(4, 4))
        self._exposure_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._exposure_frame.pack(fill="x")
        ctk.CTkLabel(
            self._exposure_frame, text="‘분석 실행’ 시 오늘 기록 기준으로 표시됩니다.",
            text_color=MUTED, font=self.f_body,
        ).pack(anchor="w", padx=12, pady=6)

        # 딥러닝 반응 예측 (AllerPredict 1D-CNN) — TF는 버튼 클릭 시 지연 로드
        self._divider(parent)
        ctk.CTkLabel(
            parent, text="🧠 딥러닝 반응 예측 (AllerPredict)", font=self.f_title, text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(4, 4))
        ctk.CTkButton(
            parent, text="🧠 예측 실행", width=120, corner_radius=8, font=self.f_body,
            fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER, command=self._run_prediction,
        ).pack(anchor="w", padx=8, pady=(0, 8))
        self._predict_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._predict_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            self._predict_frame,
            text="학습된 1D-CNN 모델로 오늘 노출 기준 알레르기 반응 확률을 예측합니다.",
            text_color=MUTED, font=self.f_body,
        ).pack(anchor="w", padx=12, pady=6)

        # 급식 패턴 분석 (datasci) — analyze.py로 미리 생성한 결과를 읽어 표시
        self._divider(parent)
        ctk.CTkLabel(
            parent, text="📅 급식 패턴 분석", font=self.f_title, text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(4, 4))
        pattern_btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        pattern_btn_row.pack(anchor="w", padx=8, pady=(0, 8))
        ctk.CTkButton(
            pattern_btn_row, text="📅 분석 데이터 로드", width=140, corner_radius=8, font=self.f_body,
            fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER,
            command=self._load_pattern_analysis,
        ).pack(side="left", padx=(0, 6))
        self._pattern_detail_btn = ctk.CTkButton(
            pattern_btn_row, text="🖼 상세 분석 보기", width=140, corner_radius=8, font=self.f_body,
            fg_color="#0f3460", hover_color="#1b4a80", state="disabled",
            command=self._show_pattern_detail,
        )
        self._pattern_detail_btn.pack(side="left")
        self._pattern_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._pattern_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            self._pattern_frame,
            text="analyze.py로 생성한 학기 단위 급식 패턴 분석 결과를 불러옵니다 "
                 "(먼저 터미널에서 'python analyze.py ...' 실행 필요).",
            text_color=MUTED, font=self.f_body, wraplength=580, justify="left",
        ).pack(anchor="w", padx=12, pady=6)

    def _render_analysis(self) -> None:
        frame = self._analysis_frame
        for w in frame.winfo_children():
            w.destroy()
        if self._analysis_canvas is not None:
            try:
                self._analysis_canvas.get_tk_widget().destroy()
            except Exception:  # noqa: BLE001
                pass
            self._analysis_canvas = None

        stats = self._compute_stats()
        per_day = stats["per_day"]
        if not any(d["has"] for d in per_day):
            ctk.CTkLabel(
                frame, text="학교를 선택하면 주간 영양 분석이 표시됩니다.",
                text_color=MUTED, font=self.f_body,
            ).pack(pady=30)
            return

        ctk.CTkLabel(
            frame, text="이번 주 안전 캘린더", font=self.f_title, text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(6, 4))
        cal = ctk.CTkFrame(frame, fg_color="transparent")
        cal.pack(fill="x", padx=8, pady=(0, 12))
        color_map = {"safe": SAFE, "caution": CAUTION, "danger": DANGER, "none": BADGE_GRAY}
        label_map = {"safe": "안전", "caution": "주의", "danger": "위험", "none": "없음"}
        for d in per_day:
            chip = ctk.CTkFrame(cal, fg_color=color_map[d["status"]], corner_radius=8, width=64, height=64)
            chip.pack(side="left", padx=5)
            chip.pack_propagate(False)
            tc = CARD_TEXT_DARK if d["status"] == "caution" else CARD_TEXT_LIGHT
            ctk.CTkLabel(chip, text=d["name"], font=self.f_title, text_color=tc).pack(pady=(10, 0))
            ctk.CTkLabel(chip, text=label_map[d["status"]], font=self.f_small, text_color=tc).pack()

        fig = Figure(figsize=(7.4, 3.1), dpi=100, facecolor=BG)
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)
        self._style_ax(ax1)
        ax1.bar(WEEKDAY_NAMES, [d["kcal"] for d in per_day], color=ACCENT)
        ax1.set_title("요일별 칼로리", color=CARD_TEXT_LIGHT, fontsize=14)
        ax1.set_ylabel("kcal", color=CARD_TEXT_LIGHT, fontsize=11)

        totals = stats["totals"]
        ax2.set_facecolor(BG)
        nz = [
            (s, l, c)
            for s, l, c in zip(
                [totals["safe"], totals["caution"], totals["danger"]],
                ["안전", "주의", "위험"], [SAFE, CAUTION, DANGER],
            )
            if s > 0
        ]
        if nz:
            sizes, labels, colors = zip(*nz)
            ax2.pie(sizes, labels=labels, colors=colors, autopct="%1.0f%%",
                    textprops={"color": CARD_TEXT_LIGHT, "fontsize": 11})
        else:
            ax2.text(0.5, 0.5, "데이터 없음", ha="center", va="center", color=MUTED)
            ax2.axis("off")
        ax2.set_title("메뉴 안전도 비율", color=CARD_TEXT_LIGHT, fontsize=14)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x", padx=8, pady=(0, 12))
        self._analysis_canvas = canvas

        ctk.CTkLabel(
            frame, text="가장 자주 등장한 위험 성분 TOP3 (내 알레르기 기준)",
            font=self.f_title, text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(6, 4))
        hits = stats["allergen_hits"]
        if not self.profile.allergies:
            ctk.CTkLabel(frame, text="내 알레르기를 선택하면 표시됩니다.", text_color=MUTED,
                        font=self.f_body).pack(anchor="w", padx=12, pady=(0, 6))
        elif not hits:
            ctk.CTkLabel(frame, text="이번 주 겹치는 위험 성분이 없습니다. 🎉", text_color=CAUTION,
                        font=self.f_body).pack(anchor="w", padx=12, pady=(0, 6))
        else:
            maxc = hits.most_common(1)[0][1]
            for rank, (num, cnt) in enumerate(hits.most_common(3), 1):
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(row, text=f"{rank}. {ALLERGEN_NAMES[num]}", width=100, anchor="w",
                            font=self.f_body_bold, text_color=CARD_TEXT_LIGHT).pack(side="left")
                bar = ctk.CTkProgressBar(row, progress_color=DANGER, fg_color=BADGE_GRAY, height=14)
                bar.set(cnt / maxc if maxc else 0)
                bar.pack(side="left", fill="x", expand=True, padx=8)
                ctk.CTkLabel(row, text=f"{cnt}회", width=44, text_color=CARD_TEXT_LIGHT,
                            font=self.f_body).pack(side="left")

    def _run_correlation(self) -> None:
        """식사/증상 기록을 로드해 상관 분석 + 오늘 노출량을 계산한다 (백그라운드 스레드)."""
        for w in self._corr_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._corr_frame, text="🔬 분석 중...", text_color=ACCENT,
                     font=self.f_body).pack(anchor="w", padx=12, pady=6)

        def worker() -> None:
            analyzer = CorrelationAnalyzer()
            analyzer.load_all(DATA_DIR)
            suspects = analyzer.get_top_suspects()
            exposure = analyzer.get_daily_exposure(datetime.now())
            n_meals = len(analyzer.meal_records)
            n_symptoms = len(analyzer.symptom_records)
            self.after(0, lambda: self._render_correlation(suspects, exposure, n_meals, n_symptoms))

        threading.Thread(target=worker, daemon=True).start()

    def _render_correlation(
        self, suspects: list[dict], exposure: dict[int, int], n_meals: int, n_symptoms: int
    ) -> None:
        # --- lag correlation 섹션 ---
        for w in self._corr_frame.winfo_children():
            w.destroy()
        if self._corr_canvas is not None:
            try:
                self._corr_canvas.get_tk_widget().destroy()
            except Exception:  # noqa: BLE001
                pass
            self._corr_canvas = None

        if n_meals < 5 or n_symptoms < 5 or not suspects:
            ctk.CTkLabel(
                self._corr_frame,
                text=f"기록이 부족합니다 (최소 5회 이상 필요)  ·  현재 식사 {n_meals}건 / 증상 {n_symptoms}건",
                text_color=MUTED, font=self.f_body,
            ).pack(anchor="w", padx=12, pady=6)
        else:
            names = [s["allergen_name"] for s in suspects]
            corrs = [s["correlation"] for s in suspects]
            fig = Figure(figsize=(7.4, 2.8), dpi=100, facecolor=BG)
            ax = fig.add_subplot(1, 1, 1)
            self._style_ax(ax)
            bar_colors = [DANGER if c >= 0.5 else ACCENT for c in corrs]
            ax.barh(names[::-1], corrs[::-1], color=bar_colors[::-1])
            ax.set_xlim(0, 1)
            ax.set_title("알레르기별 최고 상관계수", color=CARD_TEXT_LIGHT, fontsize=14)
            ax.set_xlabel("피어슨 상관계수", color=CARD_TEXT_LIGHT, fontsize=11)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self._corr_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="x", padx=8, pady=(0, 8))
            self._corr_canvas = canvas

            for s in suspects:
                warn = " ⚠️ 주의" if s["correlation"] >= 0.5 else ""
                color = DANGER if s["correlation"] >= 0.5 else CARD_TEXT_LIGHT
                ctk.CTkLabel(
                    self._corr_frame,
                    text=f"{s['allergen_name']}: {s['lag_hours']}시간 후 상관계수 "
                         f"{s['correlation']:.2f}{warn}",
                    text_color=color, font=self.f_body, anchor="w",
                ).pack(anchor="w", padx=14, pady=1)

        # --- 오늘 누적 노출량 섹션 ---
        for w in self._exposure_frame.winfo_children():
            w.destroy()
        if self._exposure_canvas is not None:
            try:
                self._exposure_canvas.get_tk_widget().destroy()
            except Exception:  # noqa: BLE001
                pass
            self._exposure_canvas = None

        if not exposure:
            ctk.CTkLabel(
                self._exposure_frame, text="오늘 저장된 식사 기록이 없습니다.",
                text_color=MUTED, font=self.f_body,
            ).pack(anchor="w", padx=12, pady=6)
            return

        items = sorted(exposure.items(), key=lambda kv: kv[1], reverse=True)
        names = [ALLERGEN_NAMES.get(n, str(n)) for n, _ in items]
        counts = [c for _, c in items]
        colors = [DANGER if n in self.profile.allergies else ACCENT for n, _ in items]
        fig = Figure(figsize=(7.4, 2.8), dpi=100, facecolor=BG)
        ax = fig.add_subplot(1, 1, 1)
        self._style_ax(ax)
        ax.bar(names, counts, color=colors)
        ax.set_title("오늘 알레르기 노출 횟수", color=CARD_TEXT_LIGHT, fontsize=14)
        ax.set_ylabel("횟수", color=CARD_TEXT_LIGHT, fontsize=11)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._exposure_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x", padx=8, pady=(0, 8))
        self._exposure_canvas = canvas

        warned = [
            (n, c) for n, c in items if n in self.profile.allergies
        ]
        for n, c in warned:
            ctk.CTkLabel(
                self._exposure_frame,
                text=f"⚠️ 내 알레르기 '{ALLERGEN_NAMES[n]}'에 오늘 이미 {c}회 노출됐습니다.",
                text_color=DANGER, font=self.f_body_bold, anchor="w",
            ).pack(anchor="w", padx=14, pady=1)

    # ================================================================== #
    # 딥러닝 반응 예측 (AllerPredict)
    # ================================================================== #
    def _run_prediction(self) -> None:
        """학습된 1D-CNN으로 오늘 노출 기준 반응 확률을 예측한다.

        TensorFlow와 allerpredict 모듈은 여기서 지연 import한다(앱 시작을 느리게 하지 않음).
        모델 로딩·추론은 백그라운드 스레드에서, UI 갱신은 after로 메인 스레드에서 처리한다.
        """
        for w in self._predict_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._predict_frame, text="🧠 모델 로딩·예측 중... (최초 실행은 몇 초 걸립니다)",
                     text_color=ACCENT, font=self.f_body).pack(anchor="w", padx=12, pady=6)

        def worker() -> None:
            try:
                from allerpredict import AllerPredictor
            except Exception as exc:  # noqa: BLE001 - TF 미설치 등
                self.after(0, lambda: self._render_prediction_error(
                    "AllerPredict 모듈을 불러올 수 없습니다. 예측 기능을 쓰려면 "
                    "'pip install -r allerpredict/requirements.txt'로 TensorFlow를 설치하세요.\n"
                    f"({exc})"))
                return
            predictor = AllerPredictor()
            if not predictor.available:
                self.after(0, lambda: self._render_prediction_error(
                    "학습된 모델이 없습니다. 먼저 터미널에서 'python train.py'를 실행해 "
                    "모델을 학습하세요."))
                return
            try:
                analyzer = CorrelationAnalyzer()
                analyzer.load_all(DATA_DIR)
                exposure = analyzer.get_daily_exposure(datetime.now())
                prob = predictor.predict_probability(exposure)
                risks = predictor.per_allergen_risk()
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda: self._render_prediction_error(f"예측 실패: {msg}"))
                return
            self.after(0, lambda: self._render_prediction(prob, exposure, risks))

        threading.Thread(target=worker, daemon=True).start()

    def _render_prediction_error(self, message: str) -> None:
        for w in self._predict_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._predict_frame, text=message, font=self.f_body, text_color=MUTED,
                     wraplength=580, justify="left", anchor="w").pack(anchor="w", padx=12, pady=6)

    def _render_prediction(self, prob: float, exposure: dict, risks: list) -> None:
        for w in self._predict_frame.winfo_children():
            w.destroy()

        if exposure:
            exp_txt = ", ".join(f"{ALLERGEN_NAMES[n]}×{c}" for n, c in sorted(exposure.items()))
        else:
            exp_txt = "오늘 기록된 식사 없음 (노출 0)"
        if prob >= 0.6:
            color, level = DANGER, "높음"
        elif prob >= 0.3:
            color, level = CAUTION, "주의"
        else:
            color, level = SAFE, "낮음"

        ctk.CTkLabel(self._predict_frame, text=f"오늘 노출: {exp_txt}", font=self.f_body,
                     text_color=CARD_TEXT_LIGHT, anchor="w", justify="left").pack(
            anchor="w", padx=12, pady=(4, 2))
        ctk.CTkLabel(self._predict_frame, text=f"예측 반응 발생 확률 {prob * 100:.0f}%  ·  위험도 {level}",
                     font=self.f_title, text_color=color, anchor="w").pack(anchor="w", padx=12, pady=(2, 8))

        ctk.CTkLabel(self._predict_frame, text="모델이 지목한 고위험 알레르겐 (단독 노출 시 예측 확률)",
                     font=self.f_body_bold, text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=12, pady=(4, 4))
        maxp = risks[0][2] if risks else 1.0
        for num, name, p in risks[:5]:
            row = ctk.CTkFrame(self._predict_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=name, width=84, anchor="w", font=self.f_body,
                         text_color=CARD_TEXT_LIGHT).pack(side="left")
            bar = ctk.CTkProgressBar(row, progress_color=DANGER, fg_color=BADGE_GRAY, height=14)
            bar.set(p / maxp if maxp else 0)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(row, text=f"{p * 100:.0f}%", width=44, font=self.f_body,
                         text_color=CARD_TEXT_LIGHT).pack(side="left")

        ctk.CTkLabel(
            self._predict_frame,
            text="※ AllerPredict 1D-CNN 예측값입니다. 참고용이며 의학적 진단이 아닙니다.",
            font=self.f_small, text_color=MUTED, anchor="w", justify="left",
        ).pack(anchor="w", padx=12, pady=(6, 4))

    # ================================================================== #
    # 급식 패턴 분석 (datasci) — analyze.py 결과 표시
    # ================================================================== #
    def _load_pattern_analysis(self) -> None:
        """analyze.py가 생성한 next_week_prediction.json을 읽어 TOP3를 표시한다."""
        for w in self._pattern_frame.winfo_children():
            w.destroy()

        path = os.path.join(DATASCI_RESULTS_DIR, "next_week_prediction.json")
        if not os.path.exists(path):
            self._pattern_detail_btn.configure(state="disabled")
            ctk.CTkLabel(
                self._pattern_frame,
                text="분석 결과가 없습니다. 터미널에서 먼저 실행하세요:\n"
                     "python analyze.py --school 7010083 --office B10 --start 20260301 --end 20260712",
                text_color=MUTED, font=self.f_body, wraplength=580, justify="left",
            ).pack(anchor="w", padx=12, pady=6)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                result = json.load(f)
        except (OSError, ValueError) as exc:
            ctk.CTkLabel(self._pattern_frame, text=f"분석 결과를 읽을 수 없습니다: {exc}",
                         text_color=DANGER, font=self.f_body).pack(anchor="w", padx=12, pady=6)
            return

        top3 = result.get("top3", [])
        week_idx = result.get("next_week_index", "?")
        ctk.CTkLabel(
            self._pattern_frame, text=f"다음 주({week_idx}주차) 위험 알레르겐 TOP3",
            font=self.f_body_bold, text_color=CARD_TEXT_LIGHT,
        ).pack(anchor="w", padx=12, pady=(4, 6))

        if not top3:
            ctk.CTkLabel(self._pattern_frame, text="예측할 데이터가 부족합니다.",
                         text_color=MUTED, font=self.f_body).pack(anchor="w", padx=12, pady=(0, 6))
        for rank, entry in enumerate(top3, 1):
            prob = entry["probability"]
            color = DANGER if prob >= 0.6 else (CAUTION if prob >= 0.3 else SAFE)
            row = ctk.CTkFrame(self._pattern_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{rank}. {entry['allergen']}", width=100, anchor="w",
                         font=self.f_body_bold, text_color=CARD_TEXT_LIGHT).pack(side="left")
            bar = ctk.CTkProgressBar(row, progress_color=color, fg_color=BADGE_GRAY, height=14)
            bar.set(prob)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(row, text=f"{prob * 100:.0f}%", width=44, font=self.f_body,
                         text_color=CARD_TEXT_LIGHT).pack(side="left")

        weeks_used = result.get("weeks_used", 0)
        ctk.CTkLabel(
            self._pattern_frame, text=f"※ {weeks_used}주치 데이터 기반 선형회귀 추정치입니다.",
            font=self.f_small, text_color=MUTED,
        ).pack(anchor="w", padx=12, pady=(6, 4))

        graphs_exist = os.path.exists(os.path.join(DATASCI_RESULTS_DIR, "allergen_frequency.png"))
        self._pattern_detail_btn.configure(state="normal" if graphs_exist else "disabled")

    def _show_pattern_detail(self) -> None:
        """급식 패턴 분석 그래프 5종을 matplotlib 창으로 띄운다."""
        names = [
            ("allergen_frequency.png", "① 알레르겐 출현 빈도"),
            ("allergen_heatmap.png", "② 동시 출현 상관관계"),
            ("weekday_risk.png", "③ 요일별 평균 노출"),
            ("trend_top5.png", "④ 주차별 상위 5종 추세"),
            ("next_week_prediction.png", "⑤ 다음 주 예측"),
        ]
        images = []
        for filename, label in names:
            path = os.path.join(DATASCI_RESULTS_DIR, filename)
            if os.path.exists(path):
                images.append((Image.open(path), label))

        if not images:
            messagebox.showinfo("상세 분석 보기", "그래프 파일이 없습니다. analyze.py를 먼저 실행하세요.")
            return

        fig = Figure(figsize=(14, 8.5), dpi=100, facecolor=BG)
        for i, (img, label) in enumerate(images):
            ax = fig.add_subplot(2, 3, i + 1)
            ax.imshow(img)
            ax.set_title(label, color=CARD_TEXT_LIGHT, fontsize=11)
            ax.axis("off")
        fig.suptitle("AllerScan · 급식 패턴 분석 상세", color=ACCENT, fontsize=15, fontweight="bold")
        fig.tight_layout()

        window = ctk.CTkToplevel(self)
        window.title("AllerScan · 급식 패턴 분석 상세")
        window.geometry("1180x760")
        window.configure(fg_color=BG)
        canvas = FigureCanvasTkAgg(fig, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ================================================================== #
    # 식사 기록 탭
    # ================================================================== #
    def _build_datetime_row(self, parent, date_default: datetime):
        """날짜/시간 입력 + '지금' 버튼 행. (date_entry, time_entry) 반환."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(4, 8))
        ctk.CTkLabel(row, text="날짜/시간", font=self.f_body, text_color=CARD_TEXT_LIGHT,
                     width=64, anchor="w").pack(side="left")
        date_entry = ctk.CTkEntry(row, width=120, font=self.f_body, placeholder_text="YYYY-MM-DD")
        date_entry.insert(0, date_default.strftime("%Y-%m-%d"))
        date_entry.pack(side="left", padx=(0, 6))
        time_entry = ctk.CTkEntry(row, width=80, font=self.f_body, placeholder_text="HH:MM")
        time_entry.insert(0, date_default.strftime("%H:%M"))
        time_entry.pack(side="left", padx=(0, 6))

        def set_now() -> None:
            now = datetime.now()
            date_entry.delete(0, "end"); date_entry.insert(0, now.strftime("%Y-%m-%d"))
            time_entry.delete(0, "end"); time_entry.insert(0, now.strftime("%H:%M"))

        ctk.CTkButton(row, text="지금", width=54, corner_radius=8, font=self.f_body,
                      fg_color="#0f3460", hover_color="#1b4a80", command=set_now).pack(side="left")
        return date_entry, time_entry

    @staticmethod
    def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
        try:
            return datetime.strptime(f"{date_str.strip()} {time_str.strip()}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _build_meal_tab(self, parent: ctk.CTkScrollableFrame) -> None:
        ctk.CTkLabel(parent, text="🍽 식사 기록", font=self.f_title, text_color=ACCENT).pack(
            anchor="w", padx=8, pady=(6, 2)
        )
        self._meal_date_entry, self._meal_time_entry = self._build_datetime_row(parent, datetime.now())

        # 식품 검색 (식약처 API)
        self._divider(parent)
        ctk.CTkLabel(parent, text="식품 검색 (식약처 식품DB)", font=self.f_body_bold,
                     text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=8)
        srow = ctk.CTkFrame(parent, fg_color="transparent")
        srow.pack(fill="x", padx=8, pady=(4, 4))
        self._meal_search_entry = ctk.CTkEntry(srow, width=220, font=self.f_body,
                                                placeholder_text="식품명 (예: 우유식빵)")
        self._meal_search_entry.pack(side="left", padx=(0, 6))
        self._meal_search_entry.bind("<Return>", lambda _e: self._meal_search())
        ctk.CTkButton(srow, text="검색", width=60, corner_radius=8, font=self.f_body, fg_color=ACCENT,
                      text_color=BG, hover_color=ACCENT_HOVER, command=self._meal_search).pack(side="left", padx=(0, 6))
        self._meal_result_menu = ctk.CTkOptionMenu(srow, width=240, font=self.f_body,
                                                    values=["검색 결과"], fg_color="#0f3460",
                                                    button_color="#0f3460", corner_radius=8)
        self._meal_result_menu.set("검색 결과")
        self._meal_result_menu.pack(side="left", padx=(0, 6))
        ctk.CTkButton(srow, text="추가", width=54, corner_radius=8, font=self.f_body, fg_color=SAFE,
                      hover_color="#3c8c69", command=self._meal_add_from_search).pack(side="left")

        # 수동 입력 (검색 실패 시)
        self._divider(parent)
        ctk.CTkLabel(parent, text="수동 입력 (검색이 안 될 때)", font=self.f_body_bold,
                     text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=8)
        mrow = ctk.CTkFrame(parent, fg_color="transparent")
        mrow.pack(fill="x", padx=8, pady=(4, 4))
        self._meal_name_entry = ctk.CTkEntry(mrow, width=200, font=self.f_body,
                                             placeholder_text="식품명 직접 입력")
        self._meal_name_entry.pack(side="left", padx=(0, 6))
        ctk.CTkButton(mrow, text="직접 추가", width=80, corner_radius=8, font=self.f_body,
                      fg_color=SAFE, hover_color="#3c8c69", command=self._meal_add_manual).pack(side="left")

        agrid = ctk.CTkFrame(parent, fg_color="transparent")
        agrid.pack(fill="x", padx=8, pady=(2, 4))
        for i in range(5):
            agrid.grid_columnconfigure(i, weight=1)
        for num, name in ALLERGEN_NAMES.items():
            var = tk.IntVar(value=0)
            self._meal_allergen_vars[num] = var
            ctk.CTkCheckBox(agrid, text=f"{num}.{name}", variable=var, font=self.f_small,
                            checkbox_width=16, checkbox_height=16, fg_color=ACCENT,
                            hover_color=ACCENT_HOVER).grid(
                row=(num - 1) // 5, column=(num - 1) % 5, sticky="w", padx=4, pady=4)

        # 추가된 식품 목록
        self._divider(parent)
        ctk.CTkLabel(parent, text="추가된 식품", font=self.f_body_bold,
                     text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=8)
        self._meal_list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._meal_list_frame.pack(fill="x", padx=8, pady=(4, 6))

        ctk.CTkButton(parent, text="💾 식사 기록 저장", corner_radius=8, font=self.f_body_bold,
                      fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER,
                      command=self._meal_save).pack(anchor="w", padx=8, pady=(4, 12))
        self._meal_render_list()

    def _meal_search(self) -> None:
        query = self._meal_search_entry.get().strip()
        if not query:
            return
        if not self.mfds.enabled:
            messagebox.showinfo("식품 검색", "식약처 API 키(MFDS_API_KEY)가 없어 검색이 비활성화되어 있습니다.\n"
                                          "아래 '수동 입력'을 사용하세요.")
            return

        def worker() -> None:
            try:
                results = self.mfds.search_food(query)
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: messagebox.showerror("식품 검색 실패", str(exc)))
                return
            self.after(0, lambda: self._meal_search_done(results))

        threading.Thread(target=worker, daemon=True).start()

    def _meal_search_done(self, results: list[dict]) -> None:
        self._meal_search_results = results
        if not results:
            self._meal_result_menu.configure(values=["검색 결과 없음"])
            self._meal_result_menu.set("검색 결과 없음")
            return
        labels = [self._food_label(f) for f in results]
        self._meal_result_menu.configure(values=labels)
        self._meal_result_menu.set(labels[0])

    @staticmethod
    def _food_label(food: dict) -> str:
        names = ", ".join(ALLERGEN_NAMES[a] for a in sorted(food["allergens"])) or "없음"
        return f"{food['name']} [{names}]"

    def _meal_add_from_search(self) -> None:
        label = self._meal_result_menu.get()
        for food in self._meal_search_results:
            if self._food_label(food) == label:
                self._meal_foods.append(
                    {"name": food["name"], "allergens": set(food["allergens"]), "source": "mfds"}
                )
                self._meal_render_list()
                return

    def _meal_add_manual(self) -> None:
        name = self._meal_name_entry.get().strip()
        if not name:
            messagebox.showwarning("수동 입력", "식품명을 입력해주세요.")
            return
        allergens = {num for num, var in self._meal_allergen_vars.items() if var.get()}
        self._meal_foods.append({"name": name, "allergens": allergens, "source": "manual"})
        self._meal_name_entry.delete(0, "end")
        for var in self._meal_allergen_vars.values():
            var.set(0)
        self._meal_render_list()

    def _meal_render_list(self) -> None:
        for w in self._meal_list_frame.winfo_children():
            w.destroy()
        if not self._meal_foods:
            ctk.CTkLabel(self._meal_list_frame, text="아직 추가된 식품이 없습니다.",
                         text_color=MUTED, font=self.f_body).pack(anchor="w", padx=4, pady=4)
            return
        for idx, food in enumerate(self._meal_foods):
            row = ctk.CTkFrame(self._meal_list_frame, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkButton(row, text="✕", width=28, corner_radius=8, font=self.f_body,
                          fg_color=DANGER, hover_color="#c42d3a",
                          command=lambda i=idx: self._meal_remove(i)).pack(side="right", padx=6, pady=6)
            ctk.CTkLabel(row, text=food["name"], font=self.f_body_bold,
                         text_color=CARD_TEXT_LIGHT).pack(side="left", padx=(10, 8), pady=6)
            badge_row = ctk.CTkFrame(row, fg_color="transparent")
            badge_row.pack(side="left", pady=6)
            if food["allergens"]:
                for num in sorted(food["allergens"]):
                    mine = num in self.profile.allergies
                    ctk.CTkLabel(badge_row, text=f" {ALLERGEN_NAMES[num]} ", font=self.f_badge,
                                 fg_color=DANGER if mine else BADGE_GRAY, text_color=CARD_TEXT_LIGHT,
                                 corner_radius=8).pack(side="left", padx=(0, 4))
            else:
                ctk.CTkLabel(badge_row, text="알레르기 없음", font=self.f_badge,
                             text_color=MUTED).pack(side="left")

    def _meal_remove(self, idx: int) -> None:
        if 0 <= idx < len(self._meal_foods):
            del self._meal_foods[idx]
            self._meal_render_list()

    def _meal_save(self) -> None:
        if not self._meal_foods:
            messagebox.showwarning("식사 기록", "저장할 식품을 먼저 추가해주세요.")
            return
        ts = self._parse_datetime(self._meal_date_entry.get(), self._meal_time_entry.get())
        if ts is None:
            messagebox.showerror("식사 기록", "날짜/시간 형식이 올바르지 않습니다. 예: 2026-07-12 / 18:30")
            return
        record = MealRecord(ts)
        for food in self._meal_foods:
            record.add_food(food["name"], food["allergens"], food["source"])
        path = os.path.join(MEALS_DIR, f"{ts.strftime('%Y-%m-%d_%H-%M')}.json")
        try:
            record.save(path)
        except OSError as exc:
            messagebox.showerror("식사 기록 저장 실패", str(exc))
            return
        self._meal_foods = []
        self._meal_render_list()
        messagebox.showinfo("식사 기록", f"{len(record.foods)}개 식품을 저장했습니다.\n{path}")

    # ================================================================== #
    # 증상 기록 탭
    # ================================================================== #
    def _build_symptom_tab(self, parent: ctk.CTkScrollableFrame) -> None:
        ctk.CTkLabel(parent, text="⚡ 증상 기록", font=self.f_title, text_color=ACCENT).pack(
            anchor="w", padx=8, pady=(6, 2)
        )
        self._symptom_date_entry, self._symptom_time_entry = self._build_datetime_row(parent, datetime.now())

        self._divider(parent)
        ctk.CTkLabel(parent, text="증상 타입 (여러 개 선택 가능)", font=self.f_body_bold,
                     text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=8)
        trow = ctk.CTkFrame(parent, fg_color="transparent")
        trow.pack(fill="x", padx=8, pady=(4, 6))
        for t in SYMPTOM_TYPES:
            btn = ctk.CTkButton(trow, text=t, width=80, corner_radius=8, font=self.f_body,
                                fg_color="transparent", text_color=CARD_TEXT_LIGHT,
                                border_width=1, border_color=MUTED, hover_color=PANEL,
                                command=lambda x=t: self._symptom_toggle(x))
            btn.pack(side="left", padx=(0, 6))
            self._symptom_type_btns[t] = btn

        self._divider(parent)
        ctk.CTkLabel(parent, text="심각도", font=self.f_body_bold,
                     text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=8)
        slider_row = ctk.CTkFrame(parent, fg_color="transparent")
        slider_row.pack(fill="x", padx=8, pady=(4, 6))
        self._symptom_severity = ctk.CTkSlider(slider_row, from_=1, to=5, number_of_steps=4,
                                               width=240, progress_color=ACCENT, button_color=ACCENT,
                                               command=self._symptom_severity_changed)
        self._symptom_severity.set(3)
        self._symptom_severity.pack(side="left", padx=(0, 12))
        self._symptom_severity_label = ctk.CTkLabel(slider_row, text="3 (보통)", font=self.f_body_bold,
                                                    text_color=CAUTION)
        self._symptom_severity_label.pack(side="left")

        self._divider(parent)
        ctk.CTkLabel(parent, text="메모", font=self.f_body_bold,
                     text_color=CARD_TEXT_LIGHT).pack(anchor="w", padx=8)
        self._symptom_note = ctk.CTkTextbox(parent, height=70, font=self.f_body,
                                           fg_color=PANEL, corner_radius=8)
        self._symptom_note.pack(fill="x", padx=8, pady=(4, 6))

        ctk.CTkButton(parent, text="💾 증상 기록 저장", corner_radius=8, font=self.f_body_bold,
                      fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER,
                      command=self._symptom_save).pack(anchor="w", padx=8, pady=(4, 12))

    def _symptom_toggle(self, t: str) -> None:
        btn = self._symptom_type_btns[t]
        if t in self._symptom_selected:
            self._symptom_selected.discard(t)
            btn.configure(fg_color="transparent", text_color=CARD_TEXT_LIGHT, border_width=1)
        else:
            self._symptom_selected.add(t)
            btn.configure(fg_color=ACCENT, text_color=BG, border_width=0)

    def _symptom_severity_changed(self, value: float) -> None:
        v = int(round(value))
        color = {1: SAFE, 2: SAFE, 3: CAUTION, 4: DANGER, 5: DANGER}[v]
        self._symptom_severity_label.configure(text=f"{v} ({SEVERITY_LABELS[v]})", text_color=color)

    def _symptom_save(self) -> None:
        if not self._symptom_selected:
            messagebox.showwarning("증상 기록", "증상 타입을 하나 이상 선택해주세요.")
            return
        ts = self._parse_datetime(self._symptom_date_entry.get(), self._symptom_time_entry.get())
        if ts is None:
            messagebox.showerror("증상 기록", "날짜/시간 형식이 올바르지 않습니다. 예: 2026-07-12 / 20:00")
            return
        severity = int(round(self._symptom_severity.get()))
        note = self._symptom_note.get("1.0", "end").strip()
        record = SymptomRecord(ts)
        for t in SYMPTOM_TYPES:  # 저장 순서 안정화
            if t in self._symptom_selected:
                record.add_symptom(t, severity, note)
        path = os.path.join(SYMPTOMS_DIR, f"{ts.strftime('%Y-%m-%d_%H-%M')}.json")
        try:
            record.save(path)
        except OSError as exc:
            messagebox.showerror("증상 기록 저장 실패", str(exc))
            return
        # 폼 초기화
        for t in list(self._symptom_selected):
            self._symptom_toggle(t)
        self._symptom_note.delete("1.0", "end")
        messagebox.showinfo("증상 기록", f"증상 {len(record.symptoms)}건을 저장했습니다.\n{path}")

    # ================================================================== #
    # 트레이 / 스케줄러 / 알림
    # ================================================================== #
    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _open_api_key_dialog(self, first_run: bool = False) -> None:
        """NEIS/식약처 API 키를 입력·저장하는 다이얼로그. 최초 실행 시 자동으로, 이후엔
        상단바 ⚙ 버튼으로 언제든 열 수 있다. 저장하면 즉시 반영되고 재시작 없이도
        급식 조회/식품 검색에 바로 쓰인다."""
        self._show_window()
        dialog = ctk.CTkToplevel(self)
        dialog.title("API 키 설정")
        dialog.geometry("440x380")
        dialog.configure(fg_color=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        title_text = "AllerScan에 오신 것을 환영합니다" if first_run else "API 키 설정"
        ctk.CTkLabel(dialog, text=title_text, font=self.f_title, text_color=ACCENT).pack(
            anchor="w", padx=20, pady=(20, 4)
        )
        if first_run:
            ctk.CTkLabel(
                dialog,
                text="급식 조회를 하려면 NEIS API 키가 필요합니다. 지금 건너뛰어도 나중에\n"
                     "상단바의 ⚙ 버튼으로 언제든 다시 설정할 수 있습니다.",
                font=self.f_small, text_color=MUTED, justify="left",
            ).pack(anchor="w", padx=20, pady=(0, 8))

        ctk.CTkLabel(
            dialog, text="NEIS Open API 키 (급식 조회, 권장)",
            font=self.f_body_bold, text_color=CARD_TEXT_LIGHT,
        ).pack(anchor="w", padx=20, pady=(8, 2))
        neis_entry = ctk.CTkEntry(
            dialog, width=400, height=32, font=self.f_body, placeholder_text="발급받은 NEIS 키 붙여넣기",
        )
        neis_entry.insert(0, self.fetcher.api_key)
        neis_entry.pack(padx=20)
        ctk.CTkLabel(
            dialog, text="발급: open.neis.go.kr", font=self.f_small, text_color=MUTED,
        ).pack(anchor="w", padx=20, pady=(2, 10))

        ctk.CTkLabel(
            dialog, text="식약처 Open API 키 (식품 검색, 선택)",
            font=self.f_body_bold, text_color=CARD_TEXT_LIGHT,
        ).pack(anchor="w", padx=20, pady=(4, 2))
        mfds_entry = ctk.CTkEntry(
            dialog, width=400, height=32, font=self.f_body,
            placeholder_text="발급받은 식약처 키 붙여넣기 (선택)",
        )
        mfds_entry.insert(0, self.mfds.api_key)
        mfds_entry.pack(padx=20)
        ctk.CTkLabel(
            dialog, text="발급: foodsafetykorea.go.kr", font=self.f_small, text_color=MUTED,
        ).pack(anchor="w", padx=20, pady=(2, 16))

        def on_save() -> None:
            neis_val = neis_entry.get().strip()
            mfds_val = mfds_entry.get().strip()
            settings = load_settings()
            settings["neis_api_key"] = neis_val
            settings["mfds_api_key"] = mfds_val
            try:
                save_settings(settings)
            except OSError as exc:
                messagebox.showerror("API 키 설정", f"저장 실패: {exc}")
                return
            self.fetcher.api_key = neis_val
            self.mfds.api_key = mfds_val
            dialog.destroy()
            messagebox.showinfo("API 키 설정", "저장되었습니다.")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(
            btn_row, text="저장", corner_radius=8, font=self.f_body_bold,
            fg_color=ACCENT, text_color=BG, hover_color=ACCENT_HOVER, command=on_save,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(
            btn_row, text="나중에" if first_run else "취소", corner_radius=8, font=self.f_body,
            fg_color="#0f3460", hover_color="#1b4a80", command=dialog.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _maybe_show_onboarding(self) -> None:
        """NEIS 키가 전혀 없으면(환경변수도, 저장된 설정도) 최초 실행 다이얼로그를 띄운다."""
        if not self.fetcher.api_key:
            self._open_api_key_dialog(first_run=True)

    def _open_alarm_settings(self) -> None:
        self._show_window()
        dialog = ctk.CTkInputDialog(
            text=f"알림 시각을 입력하세요 (HH:MM)\n현재 설정: {self.scheduler.time_str}",
            title="알림 설정",
        )
        value = dialog.get_input()
        if not value:
            return
        try:
            hh, mm = value.strip().split(":")
            hour, minute = int(hh), int(mm)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except Exception:  # noqa: BLE001
            messagebox.showerror("알림 설정", "올바른 형식이 아닙니다. 예: 07:30")
            return
        self.scheduler.set_time(hour, minute)
        messagebox.showinfo("알림 설정", f"매일 {self.scheduler.time_str}에 오늘 급식을 확인합니다.")

    def _quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.scheduler.stop()
        self.tray.stop()
        self.destroy()

    def _check_today_danger(self) -> None:
        school = self.selected_school
        if not school or not self.profile.allergies:
            return
        try:
            items = self.fetcher.fetch_day(
                school["office_code"], school["school_code"], datetime.now()
            )
        except Exception:  # noqa: BLE001
            return
        dangers = [it for it in items if self.profile.is_safe(it.allergens) == "danger"]
        if not dangers:
            return
        first = dangers[0]
        overlap = sorted(self.profile.allergies & first.allergens)
        names = ", ".join(ALLERGEN_NAMES[n] for n in overlap)
        extra = f" 외 {len(dangers) - 1}건" if len(dangers) > 1 else ""
        send_notification(
            "⚠️ 오늘 급식 알레르기 경고",
            f"오늘 {first.name} 주의 — 내 알레르기 {names} 포함{extra}",
        )

    # ================================================================== #
    # 프리셋
    # ================================================================== #
    def _sync_checkboxes(self) -> None:
        for num, var in self.check_vars.items():
            var.set(1 if num in self.profile.allergies else 0)

    def _on_save_preset(self) -> None:
        name = self.preset_entry.get().strip()
        if not name:
            messagebox.showwarning("프리셋 저장", "프리셋 이름을 입력해주세요.")
            return
        self.profile.name = name
        path = os.path.join(PRESET_DIR, f"{name}.json")
        try:
            self.profile.save(path)
            messagebox.showinfo("프리셋 저장", f"'{name}' 프리셋을 저장했습니다.")
        except OSError as exc:
            messagebox.showerror("프리셋 저장 실패", str(exc))

    def _on_load_preset(self) -> None:
        name = self.preset_entry.get().strip()
        if not name:
            messagebox.showwarning("프리셋 불러오기", "불러올 프리셋 이름을 입력해주세요.")
            return
        path = os.path.join(PRESET_DIR, f"{name}.json")
        if not os.path.exists(path):
            messagebox.showerror("프리셋 불러오기", f"'{name}' 프리셋을 찾을 수 없습니다.")
            return
        try:
            self.profile.load(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("프리셋 불러오기 실패", str(exc))
            return
        self._sync_checkboxes()
        self._invalidate_colors(None)
        messagebox.showinfo("프리셋 불러오기", f"'{name}' 프리셋을 불러왔습니다.")

    def run(self) -> None:
        self.mainloop()
