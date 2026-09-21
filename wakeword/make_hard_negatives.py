import os
import shutil
import torch
import soundfile as sf
import numpy as np

from wake_listener import WakeWordModel, audio_to_features


BASE_DIR = r"C:\sobia\wakeword"

NEGATIVE_DIR = os.path.join(
    BASE_DIR,
    "negative"
)

HARD_DIR = os.path.join(
    BASE_DIR,
    "hard_negative"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

THRESHOLD = 0.80


# ============================================================
# SETUP
# ============================================================

os.makedirs(
    HARD_DIR,
    exist_ok=True
)


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
# FIND HARD NEGATIVES
# ============================================================

files = []

for filename in os.listdir(NEGATIVE_DIR):

    if not filename.lower().endswith(".wav"):
        continue

    path = os.path.join(
        NEGATIVE_DIR,
        filename
    )

    score = predict(path)

    if score >= THRESHOLD:

        files.append(
            (path, score)
        )


files.sort(
    key=lambda x: x[1],
    reverse=True
)


print("========================================")
print("HARD NEGATIVES")
print("========================================")

print(
    f"Found {len(files)} hard negatives."
)

print()


# ============================================================
# COPY HARD NEGATIVES
# ============================================================

for path, score in files:

    filename = os.path.basename(path)

    destination = os.path.join(
        HARD_DIR,
        filename
    )

    shutil.copy2(
        path,
        destination
    )

    print(
        f"{filename:25s} "
        f"{score:.4f}"
    )


print()
print("========================================")
print("DONE")
print("========================================")

print(
    f"Hard negatives saved to:"
)

print(
    HARD_DIR
)

print()
print(
    "These files are the negatives "
    "that currently fool the model."
)