"""PPT용 그래프 5종을 PNG로 저장한다 (다크 배경, AllerScan 팔레트 · 맑은 고딕)."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# AllerScan GUI와 통일된 팔레트
BG = "#1a1a2e"
PANEL = "#16213e"
ACCENT = "#4cc9f0"
SAFE = "#2d6a4f"
CAUTION = "#e9c46a"
DANGER = "#e63946"
TEXT = "#f1faee"
MUTED = "#9aa5c4"
GRID = "#2a2a4a"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def _style_ax(ax) -> None:
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)


def _new_fig(figsize=(8, 5)):
    fig, ax = plt.subplots(figsize=figsize, dpi=130, facecolor=BG)
    _style_ax(ax)
    return fig, ax


def plot_allergen_frequency(freq: pd.Series, path: str) -> str:
    """1. 알레르겐 출현 빈도 가로 막대."""
    fig, ax = _new_fig((8, 7))
    ordered = freq.sort_values(ascending=True)
    colors = [DANGER if v == ordered.max() else ACCENT for v in ordered.values]
    ax.barh(ordered.index, ordered.values, color=colors)
    ax.set_title("알레르겐 출현 빈도 (전체 기간)", color=TEXT, fontsize=15, fontweight="bold", pad=14)
    ax.set_xlabel("등장 급식일 수")
    fig.tight_layout()
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_heatmap(corr: pd.DataFrame, path: str) -> str:
    """2. 알레르겐 동시 출현 상관관계 히트맵.

    매일 등장하는(분산 0) 알레르겐은 상관계수가 정의되지 않아(NaN) 회색으로 표시하고
    하단에 안내 문구를 남긴다 (그냥 빈 칸으로 보이면 그래프가 깨진 것처럼 오해할 수 있음).
    """
    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=130, facecolor=BG)
    ax.set_facecolor(BG)
    cmap = matplotlib.colormaps["coolwarm"].copy()
    cmap.set_bad(color="#3a4266")
    masked = np.ma.masked_invalid(corr.values.astype(float))
    im = ax.imshow(masked, cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=90, color=TEXT, fontsize=8)
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index, color=TEXT, fontsize=8)
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.yaxis.set_tick_params(color=TEXT)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=TEXT)
    ax.set_title("알레르겐 동시 출현 상관관계", color=TEXT, fontsize=15, fontweight="bold", pad=14)
    if np.isnan(corr.values.astype(float)).any():
        fig.text(0.5, 0.01, "회색 = 매일 등장(변화 없음)해 상관계수를 계산할 수 없는 알레르겐",
                  ha="center", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_weekday_risk(weekday_avg: pd.Series, path: str) -> str:
    """3. 요일별 평균 위험 알레르겐 수."""
    fig, ax = _new_fig((7, 5))
    colors = [DANGER if v == weekday_avg.max() else ACCENT for v in weekday_avg.values]
    ax.bar(weekday_avg.index, weekday_avg.values, color=colors, width=0.55)
    ax.set_title("요일별 평균 알레르겐 노출 수", color=TEXT, fontsize=15, fontweight="bold", pad=14)
    # 한글은 세로 회전(기본값)이 읽기 불편해 가로로 눕혀 축 위에 배치한다.
    ax.set_ylabel("평균 알레르겐\n종류 수", color=TEXT, rotation=0, labelpad=32, va="center", ha="center")
    fig.tight_layout()
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_trend_top5(weekly: pd.DataFrame, top5: list[str], path: str) -> str:
    """4. 주차별 상위 5종 노출 추세선.

    상위 알레르겐은 거의 매일 등장해 값이 자주 겹친다. 색만으로는 겹친 선이 구분되지
    않으므로 마커 모양·선 스타일도 계열마다 다르게 줘서 겹쳐도 식별할 수 있게 한다.
    """
    fig, ax = _new_fig((9, 5.5))
    palette = [DANGER, ACCENT, CAUTION, SAFE, "#9d8cf1"]
    markers = ["o", "s", "^", "D", "P"]
    linestyles = ["-", "--", "-.", ":", "-"]
    # 겹치는 선을 살짝 어긋나게 그려 완전히 가려지지 않게 한다 (값 자체는 그대로 유지).
    offsets = [0.0, 0.06, -0.06, 0.12, -0.12]
    for name, color, marker, ls, off in zip(top5, palette, markers, linestyles, offsets):
        ax.plot(weekly.index, weekly[name] + off, marker=marker, markersize=6, linewidth=2,
                linestyle=ls, color=color, label=name, alpha=0.9)
    ax.set_title("주차별 상위 5종 알레르겐 노출 추세", color=TEXT, fontsize=15, fontweight="bold", pad=14)
    ax.set_xlabel("ISO 주차")
    ax.set_ylabel("등장\n급식일 수", color=TEXT, rotation=0, labelpad=28, va="center", ha="center")
    fig.text(0.99, 0.01, "※ 겹치는 선 구분을 위해 값에 미세한 오프셋을 더해 표시함",
              ha="right", color=MUTED, fontsize=8)
    legend = ax.legend(frameon=False, labelcolor=TEXT, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


HIGH_EXPOSURE_THRESHOLD = 0.95  # 이 이상은 "거의 매일 등장"으로 보고 그래프에서 제외


def plot_next_week_prediction(prediction: dict, path: str) -> str:
    """5. 다음 주 알레르겐별 노출 확률 예측 막대.

    출현율이 95% 이상인 알레르겐(사실상 매일 등장해 예측할 의미가 적음)은 제외하고,
    변동이 있는(=95% 미만) 알레르겐만 보여준다. 남는 항목이 없으면 "매일 고르게
    등장한다"는 안내 문구를 대신 표시한다.
    """
    all_items = list(prediction.get("predictions", {}).items())
    items = [(name, p) for name, p in all_items if p < HIGH_EXPOSURE_THRESHOLD][:10]
    wk = prediction.get("next_week_index", "?")
    fig, ax = _new_fig((8, 6))
    ax.set_title(f"다음 주({wk}주차) 알레르겐 노출 확률 예측", color=TEXT, fontsize=15,
                 fontweight="bold", pad=14)
    if not all_items:
        ax.text(0.5, 0.5, "예측할 데이터가 없습니다", ha="center", va="center", color=MUTED)
        ax.axis("off")
    elif not items:
        ax.text(0.5, 0.5, "주요 알레르겐이 매일 고르게 등장합니다", ha="center", va="center",
                color=TEXT, fontsize=14, fontweight="bold")
        ax.axis("off")
    else:
        names = [n for n, _ in items][::-1]
        probs = [p for _, p in items][::-1]
        colors = [DANGER if p >= 0.5 else (CAUTION if p >= 0.25 else ACCENT) for p in probs]
        ax.barh(names, probs, color=colors)
        ax.set_xlim(0, 1)
        ax.set_xlabel("다음 주 노출 확률")
    fig.tight_layout()
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_all(
    freq: pd.Series,
    corr: pd.DataFrame,
    weekday_avg: pd.Series,
    weekly: pd.DataFrame,
    top5: list[str],
    prediction: dict,
    results_dir: str = RESULTS_DIR,
) -> list[str]:
    """5종 그래프를 모두 생성하고 저장된 경로 목록을 반환한다."""
    os.makedirs(results_dir, exist_ok=True)
    paths = [
        plot_allergen_frequency(freq, os.path.join(results_dir, "allergen_frequency.png")),
        plot_heatmap(corr, os.path.join(results_dir, "allergen_heatmap.png")),
        plot_weekday_risk(weekday_avg, os.path.join(results_dir, "weekday_risk.png")),
        plot_trend_top5(weekly, top5, os.path.join(results_dir, "trend_top5.png")),
        plot_next_week_prediction(prediction, os.path.join(results_dir, "next_week_prediction.png")),
    ]
    return paths
