# AllerScan

알레르기가 있는 학생과 가족을 위한 학교급식 알레르기 필터 + 개인 식사/증상 기록 도우미입니다.
NEIS(교육정보 개방 포털) API로 급식 데이터를 가져와 내 알레르기와 대조하고, 식사·증상을 기록해
시차(lag) 상관 분석으로 의심되는 알레르겐을 찾아줍니다.

## 주요 기능

- **급식 알레르기 필터** — 학교 검색 → 주간 급식표를 안전(초록)/주의(노랑)/위험(빨강)으로 자동 색칠
- **19종 알레르기 프로필** — 체크박스로 선택, 프리셋 저장/불러오기
- **위험 회피 요약 배너** — "이번 주 안전한 날: 화, 목", 가장 자주 등장하는 알레르겐 안내
- **주간 영양 분석** — 요일별 칼로리, 메뉴 안전도 비율, 안전 캘린더 (matplotlib)
- **식사 · 증상 기록** — 먹은 음식과 그 뒤 나타난 증상(소화/피부/호흡/두통 등, 심각도 1~5)을 기록
- **시차 상관 분석 (Lag Correlation)** — 기록이 쌓이면 "OO 성분 섭취 후 N시간 뒤 증상"의 피어슨
  상관계수를 계산해 의심되는 알레르겐 TOP5를 보여줍니다
- **오늘의 누적 노출량** — 오늘 먹은 음식들의 알레르기 성분 노출 횟수를 집계해 경고
- **백그라운드 알림** — 시스템 트레이에 상주하며 매일 아침 오늘 급식에 위험 메뉴가 있으면 토스트 알림
- **식품 검색 (선택)** — 식품안전나라 API 연동 시 식사 기록에서 식품명으로 검색해 알레르기 정보 자동 입력

## 스크린샷

> 스크린샷을 `docs/screenshots/`에 추가하고 아래 경로를 갱신해주세요.

| 급식 필터 | 분석 탭 |
|---|---|
| `docs/screenshots/main.png` | `docs/screenshots/analysis.png` |

## Requirements

- Python 3.10 이상 (Windows 권장 — 트레이 알림은 Windows 전용 기능 포함)
- [NEIS Open API 키](https://open.neis.go.kr) (무료 발급, 급식 조회에 필요)
- [식품안전나라 Open API 키](https://www.foodsafetykorea.go.kr) (선택, 식품 검색 자동완성용)

## Installation & Quick Start

### Windows

```bat
install.bat
run.bat
```

`install.bat`이 의존성 설치와 `data/` 디렉토리 생성을 자동으로 처리합니다.
`run.bat`을 실행하면 API 키 입력을 안내합니다.

### macOS / Linux

```bash
chmod +x install.sh
./install.sh
```

```bash
export NEIS_API_KEY="발급받은_NEIS_키"
export MFDS_API_KEY="발급받은_식약처_키"   # 선택
python main.py
```

### 수동 설치

```bash
pip install -r requirements.txt
python main.py
```

## 환경변수 설정

| 변수 | 필수 여부 | 설명 |
|---|---|---|
| `NEIS_API_KEY` | 권장 | 없어도 실행은 되지만 급식 조회 범위가 제한됩니다. [발급받기](https://open.neis.go.kr) |
| `MFDS_API_KEY` | 선택 | 없으면 식사 기록에서 식품 검색이 비활성화되고 수동 입력으로 대체됩니다. [발급받기](https://www.foodsafetykorea.go.kr) |

Windows(PowerShell)에서 직접 설정하려면:

```powershell
$env:NEIS_API_KEY = "발급받은_키"
$env:MFDS_API_KEY = "발급받은_키"
python main.py
```

## 프로젝트 구조

```
AllerScan/
├── main.py                   # 실행 진입점
├── requirements.txt
├── install.bat / install.sh  # 설치 스크립트
├── run.bat                   # Windows 실행 스크립트
├── models/                   # 순수 로직 (타입힌트 전부 적용)
│   ├── allergy_profile.py    # 내 알레르기 프로필
│   ├── menu_item.py          # 급식 메뉴 파싱
│   ├── meal_fetcher.py       # NEIS API 클라이언트
│   ├── meal_record.py        # 식사 기록
│   ├── symptom_record.py     # 증상 기록
│   ├── correlation_analyzer.py  # 시차 상관 분석 (scipy)
│   └── mfds_fetcher.py       # 식품안전나라 API 클라이언트
├── gui/
│   └── app.py                # customtkinter 기반 메인 애플리케이션
├── services/                 # 백그라운드 서비스
│   ├── tray.py                # 시스템 트레이 아이콘
│   ├── scheduler.py           # 매일 알림 스케줄러
│   └── notifier.py            # 토스트 알림
└── data/                     # 사용자 데이터 (git에는 포함되지 않음)
    ├── presets/                # 알레르기 프로필 프리셋
    ├── meals/                  # 식사 기록
    └── symptoms/               # 증상 기록
```

## 기술 스택

Python · [customtkinter](https://github.com/TomSchimansky/CustomTkinter) · matplotlib · scipy · requests · pystray · plyer

## License

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.
