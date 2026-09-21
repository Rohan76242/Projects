import os
import sys
import torch
import torchaudio
import soundfile as sf
from torch import nn


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"

POSITIVE_DIR = os.path.join(
    BASE_DIR,
    "positive"
)

HARD_NEGATIVE_DIR = os.path.join(
    BASE_DIR,
    "hard_negative"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

SAMPLE_RATE = 16000
NUM_SAMPLES = 16000


# ============================================================
# MFCC
# ============================================================

MFCC_TRANSFORM = torchaudio.transforms.MFCC(
    sample_rate=SAMPLE_RATE,
    n_mfcc=40,
    melkwargs={
        "n_fft": 400,
        "hop_length": 160,
        "n_mels": 64
    }
)


# ============================================================
# MODEL
# ============================================================


class WakeWordModel(nn.Module):

    def __init__(self):

        super().__init__()

        self.network = nn.Sequential(

            # BLOCK 1
            nn.Conv2d(
                1,
                16,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # BLOCK 2
            nn.Conv2d(
                16,
                32,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # BLOCK 3
            nn.Conv2d(
                32,
                64,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(64),
            nn.ReLU(),

            # BLOCK 4
            nn.Conv2d(
                64,
                96,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(96),
            nn.ReLU(),

            # GLOBAL POOL
            nn.AdaptiveAvgPool2d(
                (1, 1)
            ),

            nn.Flatten(),

            # CLASSIFIER
            nn.Linear(
                96,
                48
            ),

            nn.ReLU(),

            nn.Dropout(
                0.35
            ),

            nn.Linear(
                48,
                2
            )
        )

    def forward(self, x):

        return self.network(x)


# ============================================================
# FIND WAV FILES
# ============================================================

def find_wavs(folder):

    files = []

    if not os.path.exists(folder):
        return files

    for root, dirs, filenames in os.walk(folder):

        for filename in filenames:

            if filename.lower().endswith(".wav"):

                files.append(
                    os.path.join(
                        root,
                        filename
                    )
                )

    return sorted(files)


# ============================================================
# LOAD AUDIO
# ============================================================

def load_audio(path):

    audio, sr = sf.read(
        path,
        dtype="float32"
    )

    # Stereo -> mono
    if audio.ndim > 1:

        audio = audio.mean(axis=1)

    waveform = torch.from_numpy(
        audio
    ).float()

    waveform = waveform.unsqueeze(0)

    # Resample
    if sr != SAMPLE_RATE:

        waveform = torchaudio.functional.resample(
            waveform,
            sr,
            SAMPLE_RATE
        )

    # Normalize
    peak = waveform.abs().max()

    if peak > 0:

        waveform = waveform / peak

    # Pad
    if waveform.shape[1] < NUM_SAMPLES:

        waveform = torch.nn.functional.pad(
            waveform,
            (
                0,
                NUM_SAMPLES - waveform.shape[1]
            )
        )

    # Crop
    elif waveform.shape[1] > NUM_SAMPLES:

        waveform = waveform[
            :,
            :NUM_SAMPLES
        ]

    return waveform


# ============================================================
# PREDICT
# ============================================================

def predict(
    model,
    path,
    device
):

    waveform = load_audio(path)

    features = MFCC_TRANSFORM(
        waveform
    )

    # [1, 40, 101]
    # -> [1, 1, 40, 101]

    features = features.unsqueeze(0)

    features = features.to(device)

    with torch.no_grad():

        output = model(
            features
        )

        probabilities = torch.softmax(
            output,
            dim=1
        )

    wake_probability = (
        probabilities[0, 1].item()
    )

    return wake_probability


# ============================================================
# TEST DATASET
# ============================================================

def main():

    print()
    print("=" * 60)
    print("          SOBIA FULL WAKEWORD TEST")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Device: {device}"
    )

    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    if not os.path.exists(MODEL_PATH):

        print()
        print("ERROR: Model not found:")
        print(MODEL_PATH)
        return

    print()
    print("Loading model...")

    model = WakeWordModel().to(
        device
    )

    state_dict = torch.load(
        MODEL_PATH,
        map_location=device
    )

    model.load_state_dict(
        state_dict
    )

    model.eval()

    print("Model loaded successfully.")

    # --------------------------------------------------------
    # FIND FILES
    # --------------------------------------------------------

    positive_files = find_wavs(
        POSITIVE_DIR
    )

    hard_negative_files = find_wavs(
        HARD_NEGATIVE_DIR
    )

    print()
    print(
        f"Positive files: "
        f"{len(positive_files)}"
    )

    print(
        f"Hard negative files: "
        f"{len(hard_negative_files)}"
    )

    if len(positive_files) == 0:

        print()
        print("ERROR: No positive WAV files found.")
        return

    if len(hard_negative_files) == 0:

        print()
        print(
            "ERROR: No hard-negative WAV files found."
        )

        return

    # --------------------------------------------------------
    # RUN PREDICTIONS
    # --------------------------------------------------------

    print()
    print("Running predictions...")
    print()

    positive_scores = []
    negative_scores = []

    # --------------------------------------------------------
    # POSITIVES
    # --------------------------------------------------------

    print(
        "Testing positive samples..."
    )

    for i, path in enumerate(
        positive_files,
        start=1
    ):

        score = predict(
            model,
            path,
            device
        )

        positive_scores.append(
            score
        )

        print(
            f"\rPositive: "
            f"{i}/{len(positive_files)}",
            end=""
        )

    print()

    # --------------------------------------------------------
    # HARD NEGATIVES
    # --------------------------------------------------------

    print(
        "Testing hard negatives..."
    )

    for i, path in enumerate(
        hard_negative_files,
        start=1
    ):

        score = predict(
            model,
            path,
            device
        )

        negative_scores.append(
            score
        )

        print(
            f"\rHard negative: "
            f"{i}/{len(hard_negative_files)}",
            end=""
        )

    print()
    print()

    # ========================================================
    # THRESHOLD ANALYSIS
    # ========================================================

    print("=" * 60)
    print("             THRESHOLD ANALYSIS")
    print("=" * 60)

    best_threshold = None
    best_score = -1

    print()

    print(
        f"{'Threshold':<12}"
        f"{'Wake %':<12}"
        f"{'Neg %':<12}"
        f"{'Balanced %':<15}"
        f"{'FP':<8}"
        f"{'FN':<8}"
    )

    print("-" * 67)

    for threshold in [
        0.50,
        0.60,
        0.65,
        0.70,
        0.75,
        0.80,
        0.85,
        0.90,
        0.92,
        0.94,
        0.95,
        0.96,
        0.97,
        0.98,
        0.99
    ]:

        true_positive = sum(
            score >= threshold
            for score in positive_scores
        )

        false_negative = (
            len(positive_scores)
            -
            true_positive
        )

        true_negative = sum(
            score < threshold
            for score in negative_scores
        )

        false_positive = (
            len(negative_scores)
            -
            true_negative
        )

        wake_accuracy = (
            100.0
            * true_positive
            / len(positive_scores)
        )

        negative_accuracy = (
            100.0
            * true_negative
            / len(negative_scores)
        )

        balanced_score = (
            wake_accuracy
            +
            negative_accuracy
        ) / 2.0

        print(
            f"{threshold:<12.2f}"
            f"{wake_accuracy:<12.1f}"
            f"{negative_accuracy:<12.1f}"
            f"{balanced_score:<15.1f}"
            f"{false_positive:<8}"
            f"{false_negative:<8}"
        )

        # Prefer balanced accuracy
        # but avoid thresholds with poor wake detection.
        if (
            wake_accuracy >= 95.0
            and
            balanced_score > best_score
        ):

            best_score = balanced_score
            best_threshold = threshold

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 60)
    print("                 FINAL RESULT")
    print("=" * 60)

    print()

    if best_threshold is not None:

        print(
            f"Recommended threshold: "
            f"{best_threshold:.2f}"
        )

        print(
            f"Balanced accuracy: "
            f"{best_score:.1f}%"
        )

    else:

        print(
            "No threshold achieved "
            "95% wake-word detection."
        )

    # --------------------------------------------------------
    # SCORE RANGES
    # --------------------------------------------------------

    print()

    print(
        f"Positive minimum: "
        f"{min(positive_scores):.4f}"
    )

    print(
        f"Positive maximum: "
        f"{max(positive_scores):.4f}"
    )

    print(
        f"Negative minimum: "
        f"{min(negative_scores):.4f}"
    )

    print(
        f"Negative maximum: "
        f"{max(negative_scores):.4f}"
    )

    # --------------------------------------------------------
    # MOST DANGEROUS NEGATIVES
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("        TOP FALSE-TRIGGER CANDIDATES")
    print("=" * 60)
    print()

    negative_ranked = sorted(
        zip(
            negative_scores,
            hard_negative_files
        ),
        reverse=True
    )

    for score, path in negative_ranked[:10]:

        print(
            f"{score:.4f}  "
            f"{os.path.basename(path)}"
        )

    # --------------------------------------------------------
    # HARDEST POSITIVES
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("          LOWEST POSITIVE SCORES")
    print("=" * 60)
    print()

    positive_ranked = sorted(
        zip(
            positive_scores,
            positive_files
        )
    )

    for score, path in positive_ranked[:10]:

        print(
            f"{score:.4f}  "
            f"{os.path.basename(path)}"
        )

    print()
    print("=" * 60)
    print("                 TEST COMPLETE")
    print("=" * 60)
    print()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()