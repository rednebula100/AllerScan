"""AllerScan 급식 패턴 분석 독립 실행 스크립트.

사용 예 (남강고등학교 2026년 1학기):
    python analyze.py --school 7010083 --office B10 --start 20260301 --end 20260712

환경변수 NEIS_API_KEY가 필요하다 (기존 AllerScan과 동일).
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from datasci import (  # noqa: E402
    allergen_frequency,
    build_allergen_matrix,
    collect_semester,
    cooccurrence_matrix,
    predict_next_week,
    weekday_avg_exposure,
    weekly_trend_top5,
)
from datasci.collector import save_raw
from datasci.predictor import save_prediction
from datasci.preprocessor import save_processed
from datasci.visualizer import generate_all


def main() -> None:
    parser = argparse.ArgumentParser(description="AllerScan 급식 패턴 분석")
    parser.add_argument("--school", required=True, help="NEIS 학교코드 (예: 7010083)")
    parser.add_argument("--office", required=True, help="NEIS 시도교육청코드 (예: B10)")
    parser.add_argument("--start", required=True, help="시작일 YYYYMMDD")
    parser.add_argument("--end", required=True, help="종료일 YYYYMMDD")
    args = parser.parse_args()

    api_key = os.environ.get("NEIS_API_KEY", "")
    if not api_key:
        print("[경고] NEIS_API_KEY 환경변수가 없습니다. 제한된 범위로 동작합니다.")

    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass

    start = datetime.strptime(args.start, "%Y%m%d")
    end = datetime.strptime(args.end, "%Y%m%d")

    print(f"[1/6] {args.office}/{args.school} 급식 데이터 수집 중 ({args.start} ~ {args.end})...")
    raw_df = collect_semester(args.office, args.school, start, end, api_key=api_key)
    raw_path = save_raw(raw_df)
    print(f"      메뉴 {len(raw_df)}건 수집 → {raw_path}")
    if raw_df.empty:
        print("      수집된 데이터가 없습니다. 학교/기간/API 키를 확인하세요.")
        return

    print("[2/6] 전처리 중 (알레르겐 0/1 행렬)...")
    processed_df = build_allergen_matrix(raw_df)
    processed_path = save_processed(processed_df)
    print(f"      급식일 {len(processed_df)}일 → {processed_path}")

    print("[3/6] 분석 4종 실행 중...")
    freq = allergen_frequency(processed_df)
    corr = cooccurrence_matrix(processed_df)
    weekday_avg = weekday_avg_exposure(processed_df)
    weekly, top5 = weekly_trend_top5(processed_df)
    print(f"      최다 출현 알레르겐: {freq.index[0]} ({int(freq.iloc[0])}일)")

    print("[4/6] 다음 주 예측 중 (선형회귀)...")
    prediction = predict_next_week(processed_df)
    pred_path = save_prediction(prediction)
    if prediction["top3"]:
        top3_txt = ", ".join(f"{t['allergen']} {t['probability']*100:.0f}%" for t in prediction["top3"])
        print(f"      다음 주 위험 TOP3: {top3_txt}")
    print(f"      → {pred_path}")

    print("[5/6] 그래프 5종 저장 중...")
    paths = generate_all(freq, corr, weekday_avg, weekly, top5, prediction)
    for p in paths:
        print(f"      - {p}")

    print("[6/6] 완료")
    print("\n===== 요약 =====")
    print(f"  수집 메뉴: {len(raw_df)}건 / 급식일: {len(processed_df)}일")
    print(f"  최다 알레르겐: {freq.index[0]}")
    print(f"  결과 폴더: datasci/results/")


if __name__ == "__main__":
    main()
