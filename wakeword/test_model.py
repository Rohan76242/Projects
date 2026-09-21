import os
import glob

import numpy as np
import soundfile as sf
import torch

from wake_listener import WakeWordModel, audio_to_features


BASE_DIR = r"C:\sobia\wakeword"

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

POSITIVE_DIR = os.path.join(
    BASE_DIR,
    "positive"
)

NEGATIVE_DIR = os.path.join(
    BASE_DIR,
    "negative"
)


THRESHOLD = 0.80


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading model...")

device = torch.device("cpu")

model = WakeWordModel().to(device)

model.load_state_dict(
    torch.load(
        MODEL_PATH,
        map_location=device
    )
)

model.eval()

print("Model loaded.")
print()


# ============================================================
# PREDICT
# ============================================================

def predict(path):

    audio, sr = sf.read(
        path,
        dtype="float32"
    )

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    features = audio_to_features(
        audio
    ).to(device)

    with torch.no_grad():

        output = model(
            features
        )

        probability = torch.softmax(
            output,
            dim=1
        )[0][1].item()

    return probability


# ============================================================
# POSITIVE TEST
# ============================================================

positive_files = sorted(
    glob.glob(
        os.path.join(
            POSITIVE_DIR,
            "*.wav"
        )
    )
)

print("========================================")
print("POSITIVE TEST")
print("========================================")

positive_scores = []

for path in positive_files:

    score = predict(path)

    positive_scores.append(score)

print(
    f"Positive samples: {len(positive_files)}"
)

print(
    f"Average wake probability: "
    f"{np.mean(positive_scores):.4f}"
)

print(
    f"Minimum wake probability: "
    f"{np.min(positive_scores):.4f}"
)

print(
    f"Positive samples >= {THRESHOLD}: "
    f"{sum(s >= THRESHOLD for s in positive_scores)}"
)

print()


# ============================================================
# NEGATIVE TEST
# ============================================================

negative_files = sorted(
    glob.glob(
        os.path.join(
            NEGATIVE_DIR,
            "*.wav"
        )
    )
)

print("========================================")
print("NEGATIVE TEST")
print("========================================")

negative_scores = []

for path in negative_files:

    score = predict(path)

    negative_scores.append(
        (path, score)
    )


scores = [
    score
    for path, score in negative_scores
]

false_positives = [
    (path, score)
    for path, score in negative_scores
    if score >= THRESHOLD
]

print(
    f"Negative samples: {len(negative_files)}"
)

print(
    f"Average wake probability: "
    f"{np.mean(scores):.4f}"
)

print(
    f"Maximum wake probability: "
    f"{np.max(scores):.4f}"
)

print(
    f"Negative samples >= {THRESHOLD}: "
    f"{len(false_positives)}"
)

print()


# ============================================================
# WORST NEGATIVES
# ============================================================

print("========================================")
print("TOP 20 NEGATIVE FALSE-POSITIVE RISKS")
print("========================================")

for path, score in sorted(
    false_positives,
    key=lambda x: x[1],
    reverse=True
)[:20]:

    print(
        f"{os.path.basename(path):25s} "
        f"{score:.4f}"
    )

print()


# ============================================================
# SUMMARY
# ============================================================

positive_rate = (
    sum(
        s >= THRESHOLD
        for s in positive_scores
    )
    / len(positive_scores)
    * 100
)

false_positive_rate = (
    len(false_positives)
    / len(negative_files)
    * 100
)

print("========================================")
print("FINAL RESULT")
print("========================================")

print(
    f"Positive detection rate: "
    f"{positive_rate:.1f}%"
)

print(
    f"Negative false-positive rate: "
    f"{false_positive_rate:.1f}%"
)

print()

if (
    positive_rate >= 90
    and false_positive_rate <= 5
):

    print("🔥 MODEL LOOKS READY FOR LIVE TESTING.")

else:

    print("⚠️ MODEL NEEDS MORE WORK.")

print()