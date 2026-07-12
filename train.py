"""AllerPredict 1D-CNN 학습 스크립트 (독립 실행).

사용 예:
    python train.py                       # 실데이터+합성데이터 자동, 기본 설정
    python train.py --epochs 40 --synthetic-samples 3000
    python train.py --synthetic-only      # 실데이터 무시하고 합성만으로 학습

학습이 끝나면 다음을 allerpredict/artifacts/ 에 저장한다:
    allerpredict_model.keras   학습된 모델 (GUI가 로드)
    training_curves.png        loss / accuracy 곡선
    confusion_matrix.png       혼동 행렬
    roc_curve.png              ROC 곡선
    metrics.png                요약 지표 카드
"""
from __future__ import annotations

import argparse
import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import matplotlib

matplotlib.use("Agg")  # 화면 없이 PNG로만 저장
import matplotlib.pyplot as plt
import numpy as np

from allerpredict.dataset import NUM_ALLERGENS, load_dataset
from allerpredict.model import build_model

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allerpredict", "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "allerpredict_model.keras")

# PPT용 그래프 팔레트 (밝은 배경, 슬라이드 가독성 우선)
C_ACCENT = "#1f7a9e"
C_ACCENT2 = "#4cc9f0"
C_DANGER = "#e63946"
C_SAFE = "#2d6a4f"
C_GRID = "#d9dced"
C_TEXT = "#1a1a2e"
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def split_dataset(x, y, seed=42, val=0.15, test=0.15):
    """numpy만으로 train/val/test 분할 (계층 없이 랜덤 셔플)."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(x))
    n_test = int(len(x) * test)
    n_val = int(len(x) * val)
    test_idx = idx[:n_test]
    val_idx = idx[n_test : n_test + n_val]
    train_idx = idx[n_test + n_val :]
    return (
        (x[train_idx], y[train_idx]),
        (x[val_idx], y[val_idx]),
        (x[test_idx], y[test_idx]),
    )


def roc_curve_manual(y_true, y_score):
    """sklearn 없이 ROC 곡선과 AUC를 계산한다."""
    order = np.argsort(-y_score)
    y_true = y_true[order].astype(float)
    total_pos = y_true.sum()
    total_neg = len(y_true) - total_pos
    tps = np.cumsum(y_true)
    fps = np.cumsum(1.0 - y_true)
    tpr = np.concatenate([[0.0], tps / (total_pos if total_pos else 1.0)])
    fpr = np.concatenate([[0.0], fps / (total_neg if total_neg else 1.0)])
    auc = float(np.trapezoid(tpr, fpr)) if hasattr(np, "trapezoid") else float(np.trapz(tpr, fpr))
    return fpr, tpr, auc


def confusion_at(y_true, y_score, threshold=0.5):
    pred = (y_score >= threshold).astype(int)
    tp = int(np.sum((pred == 1) & (y_true == 1)))
    tn = int(np.sum((pred == 0) & (y_true == 0)))
    fp = int(np.sum((pred == 1) & (y_true == 0)))
    fn = int(np.sum((pred == 0) & (y_true == 1)))
    return np.array([[tn, fp], [fn, tp]]), pred


def _style_ax(ax):
    ax.set_facecolor("white")
    ax.grid(True, color=C_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(C_GRID)
    ax.tick_params(colors=C_TEXT)


def plot_training_curves(history, path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.4), dpi=130, facecolor="white")
    epochs = range(1, len(history.history["loss"]) + 1)
    _style_ax(ax1)
    ax1.plot(epochs, history.history["loss"], color=C_ACCENT, label="train")
    ax1.plot(epochs, history.history["val_loss"], color=C_DANGER, label="val")
    ax1.set_title("Loss", color=C_TEXT, fontsize=13, fontweight="bold")
    ax1.set_xlabel("epoch", color=C_TEXT)
    ax1.legend(frameon=False)

    _style_ax(ax2)
    ax2.plot(epochs, history.history["accuracy"], color=C_ACCENT, label="train")
    ax2.plot(epochs, history.history["val_accuracy"], color=C_DANGER, label="val")
    ax2.set_title("Accuracy", color=C_TEXT, fontsize=13, fontweight="bold")
    ax2.set_xlabel("epoch", color=C_TEXT)
    ax2.legend(frameon=False)

    fig.suptitle("AllerPredict 1D-CNN · 학습 곡선", color=C_TEXT, fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_confusion(cm, path):
    fig, ax = plt.subplots(figsize=(4.6, 4.2), dpi=130, facecolor="white")
    ax.imshow(cm, cmap="Blues")
    labels = ["반응 없음 (0)", "반응 발생 (1)"]
    ax.set_xticks([0, 1], labels, color=C_TEXT)
    ax.set_yticks([0, 1], labels, color=C_TEXT, rotation=90, va="center")
    ax.set_xlabel("예측", color=C_TEXT, fontweight="bold")
    ax.set_ylabel("실제", color=C_TEXT, fontweight="bold")
    vmax = cm.max() if cm.max() else 1
    for i in range(2):
        for j in range(2):
            ax.text(
                j, i, str(cm[i, j]), ha="center", va="center", fontsize=18,
                fontweight="bold", color="white" if cm[i, j] > vmax * 0.5 else C_TEXT,
            )
    ax.set_title("Confusion Matrix (test)", color=C_TEXT, fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_roc(fpr, tpr, auc, path):
    fig, ax = plt.subplots(figsize=(4.8, 4.4), dpi=130, facecolor="white")
    _style_ax(ax)
    ax.plot(fpr, tpr, color=C_ACCENT, linewidth=2.4, label=f"ROC (AUC = {auc:.3f})")
    ax.fill_between(fpr, tpr, color=C_ACCENT2, alpha=0.18)
    ax.plot([0, 1], [0, 1], color=C_DANGER, linestyle="--", linewidth=1.2, label="랜덤")
    ax.set_xlabel("False Positive Rate", color=C_TEXT)
    ax.set_ylabel("True Positive Rate", color=C_TEXT)
    ax.set_title("ROC Curve (test)", color=C_TEXT, fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_metrics(metrics: dict, path):
    fig, ax = plt.subplots(figsize=(7.2, 2.2), dpi=130, facecolor="white")
    ax.axis("off")
    cards = [
        ("Accuracy", f"{metrics['accuracy']:.3f}", C_ACCENT),
        ("Precision", f"{metrics['precision']:.3f}", C_SAFE),
        ("Recall", f"{metrics['recall']:.3f}", C_ACCENT),
        ("F1", f"{metrics['f1']:.3f}", C_SAFE),
        ("AUC", f"{metrics['auc']:.3f}", C_DANGER),
    ]
    n = len(cards)
    for i, (label, value, color) in enumerate(cards):
        x = i / n + 0.5 / n
        ax.text(x, 0.62, value, ha="center", va="center", fontsize=24, fontweight="bold",
                color=color, transform=ax.transAxes)
        ax.text(x, 0.24, label, ha="center", va="center", fontsize=12,
                color=C_TEXT, transform=ax.transAxes)
    ax.set_title("AllerPredict · 테스트 지표", color=C_TEXT, fontsize=13, fontweight="bold", loc="left")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="AllerPredict 1D-CNN 학습")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--synthetic-samples", type=int, default=2000)
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    print("[1/4] 데이터 준비 중...")
    x, y, meta = load_dataset(
        synthetic_samples=args.synthetic_samples,
        seed=args.seed,
        synthetic_only=args.synthetic_only,
    )
    print(f"      데이터 출처: {meta['source']} | 실데이터 {meta['real_samples']}건 "
          f"| 합성 {meta['synthetic_samples']}건 | 총 {meta['total_samples']}건 "
          f"| 양성비율 {meta['positive_rate']:.2f}")

    (xtr, ytr), (xva, yva), (xte, yte) = split_dataset(x, y, seed=args.seed)
    xtr = xtr.reshape(-1, NUM_ALLERGENS, 1)
    xva = xva.reshape(-1, NUM_ALLERGENS, 1)
    xte = xte.reshape(-1, NUM_ALLERGENS, 1)
    print(f"      train {len(xtr)} | val {len(xva)} | test {len(xte)}")

    print("[2/4] 모델 학습 중...")
    model = build_model()
    model.summary()
    history = model.fit(
        xtr, ytr,
        validation_data=(xva, yva),
        epochs=args.epochs,
        batch_size=args.batch_size,
        verbose=2,
    )

    print("[3/4] 평가 및 그래프 저장 중...")
    scores = model.predict(xte, verbose=0).reshape(-1)
    fpr, tpr, auc = roc_curve_manual(yte, scores)
    cm, pred = confusion_at(yte, scores, threshold=0.5)
    tn, fp, fn, tp = cm[0, 0], cm[0, 1], cm[1, 0], cm[1, 1]
    accuracy = (tp + tn) / max(1, len(yte))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    metrics = {
        "accuracy": accuracy, "precision": precision, "recall": recall,
        "f1": f1, "auc": auc,
    }

    plot_training_curves(history, os.path.join(ARTIFACTS_DIR, "training_curves.png"))
    plot_confusion(cm, os.path.join(ARTIFACTS_DIR, "confusion_matrix.png"))
    plot_roc(fpr, tpr, auc, os.path.join(ARTIFACTS_DIR, "roc_curve.png"))
    plot_metrics(metrics, os.path.join(ARTIFACTS_DIR, "metrics.png"))

    print("[4/4] 모델 저장 중...")
    model.save(MODEL_PATH)

    print("\n===== 완료 =====")
    print(f"  Accuracy  {accuracy:.3f}")
    print(f"  Precision {precision:.3f}")
    print(f"  Recall    {recall:.3f}")
    print(f"  F1        {f1:.3f}")
    print(f"  AUC       {auc:.3f}")
    print(f"  모델:   {MODEL_PATH}")
    print(f"  그래프: {ARTIFACTS_DIR}\\*.png")


if __name__ == "__main__":
    main()
