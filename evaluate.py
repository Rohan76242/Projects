import os
import soundfile as sf
import torch
import torchaudio

from torch import nn


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"

POSITIVE_DIR = os.path.join(BASE_DIR, "positive")
NEGATIVE_DIR = os.path.join(BASE_DIR, "negative")

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

SAMPLE_RATE = 16000
NUM_SAMPLES = 16000

# Detection threshold
THRESHOLD = 0.50


# ============================================================
# MODEL
# ============================================================

class WakeWordModel(nn.Module):

    def __init__(self):

        super().__init__()

        self.network = nn.Sequential(

            nn.Conv2d(
                1,
                16,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(16),

            nn.ReLU(),

            nn.MaxPool2d(2),

            nn.Conv2d(
                16,
                32,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(32),

            nn.ReLU(),

            nn.MaxPool2d(2),

            nn.Conv2d(
                32,
                64,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(64),

            nn.ReLU(),

            nn.AdaptiveAvgPool2d((1, 1)),

            nn.Flatten(),

            nn.Linear(
                64,
                32
            ),

            nn.ReLU(),

            nn.Dropout(0.3),

            nn.Linear(
                32,
                2
            )
        )

    def forward(self, x):

        return self.network(x)


# ============================================================
# FIND WAV FILES
# ============================================================

def find_wavs(folder):

    result = []

    for root, dirs, files in os.walk(folder):

        for file in files:

            if file.lower().endswith(".wav"):

                result.append(
                    os.path.join(
                        root,
                        file
                    )
                )

    return sorted(result)


# ============================================================
# AUDIO -> MFCC
# ============================================================

mfcc_transform = torchaudio.transforms.MFCC(
    sample_rate=SAMPLE_RATE,
    n_mfcc=40,
    melkwargs={
        "n_fft": 400,
        "hop_length": 160,
        "n_mels": 64
    }
)


def load_audio(path):

    audio, sr = sf.read(
        path,
        dtype="float32"
    )

    if audio.ndim == 1:

        waveform = torch.from_numpy(
            audio
        ).unsqueeze(0)

    else:

        waveform = torch.from_numpy(
            audio.T
        )

    # Stereo -> mono
    if waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True
        )

    # Resample
    if sr != SAMPLE_RATE:

        waveform = torchaudio.functional.resample(
            waveform,
            sr,
            SAMPLE_RATE
        )

    # Exactly 1 second
    if waveform.shape[1] < NUM_SAMPLES:

        waveform = torch.nn.functional.pad(
            waveform,
            (
                0,
                NUM_SAMPLES - waveform.shape[1]
            )
        )

    else:

        waveform = waveform[:, :NUM_SAMPLES]

    # MFCC
    features = mfcc_transform(
        waveform
    )

    # [1, 40, 101]
    return features


# ============================================================
# TEST ONE FILE
# ============================================================

def predict(model, path, device):

    features = load_audio(path)

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
        probabilities[0][1].item()
    )

    prediction = (
        1
        if wake_probability >= THRESHOLD
        else 0
    )

    return prediction, wake_probability


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("======================================")
    print("       Z3RO WAKE WORD EVALUATION")
    print("======================================")
    print()

    positive_files = find_wavs(
        POSITIVE_DIR
    )

    negative_files = find_wavs(
        NEGATIVE_DIR
    )

    print(
        f"Positive WAV files: {len(positive_files)}"
    )

    print(
        f"Negative WAV files: {len(negative_files)}"
    )

    print()

    if len(positive_files) == 0:

        print("ERROR: No positive WAV files found.")

        return

    if len(negative_files) == 0:

        print("ERROR: No negative WAV files found.")

        return

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

    print()
    print("Loading model...")

    model = WakeWordModel().to(
        device
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device
    )

    model.load_state_dict(
        checkpoint
    )

    model.eval()

    print(
        "Model loaded successfully."
    )

    # --------------------------------------------------------
    # POSITIVE TEST
    # --------------------------------------------------------

    print()
    print("--------------------------------------")
    print("Testing POSITIVE samples")
    print("--------------------------------------")

    positive_correct = 0
    positive_wrong = 0

    positive_probabilities = []

    false_negative_files = []

    for i, path in enumerate(
        positive_files,
        start=1
    ):

        try:

            prediction, probability = predict(
                model,
                path,
                device
            )

            positive_probabilities.append(
                probability
            )

            if prediction == 1:

                positive_correct += 1

            else:

                positive_wrong += 1

                false_negative_files.append(
                    (
                        path,
                        probability
                    )
                )

        except Exception as e:

            print()
            print(
                f"ERROR: {path}"
            )

            print(e)

        if i % 25 == 0 or i == len(positive_files):

            print(
                f"Progress: "
                f"{i}/{len(positive_files)}"
            )

    # --------------------------------------------------------
    # NEGATIVE TEST
    # --------------------------------------------------------

    print()
    print("--------------------------------------")
    print("Testing NEGATIVE samples")
    print("--------------------------------------")

    negative_correct = 0
    negative_wrong = 0

    negative_probabilities = []

    false_positive_files = []

    for i, path in enumerate(
        negative_files,
        start=1
    ):

        try:

            prediction, probability = predict(
                model,
                path,
                device
            )

            negative_probabilities.append(
                probability
            )

            if prediction == 0:

                negative_correct += 1

            else:

                negative_wrong += 1

                false_positive_files.append(
                    (
                        path,
                        probability
                    )
                )

        except Exception as e:

            print()
            print(
                f"ERROR: {path}"
            )

            print(e)

        if i % 25 == 0 or i == len(negative_files):

            print(
                f"Progress: "
                f"{i}/{len(negative_files)}"
            )

    # --------------------------------------------------------
    # CALCULATE RESULTS
    # --------------------------------------------------------

    positive_total = len(
        positive_files
    )

    negative_total = len(
        negative_files
    )

    total = (
        positive_total
        +
        negative_total
    )

    correct = (
        positive_correct
        +
        negative_correct
    )

    overall_accuracy = (
        100.0
        *
        correct
        /
        total
    )

    positive_accuracy = (
        100.0
        *
        positive_correct
        /
        positive_total
    )

    negative_accuracy = (
        100.0
        *
        negative_correct
        /
        negative_total
    )

    avg_positive = (
        sum(positive_probabilities)
        /
        len(positive_probabilities)
    )

    avg_negative = (
        sum(negative_probabilities)
        /
        len(negative_probabilities)
    )

    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    print()
    print()
    print("======================================")
    print("           FINAL RESULTS")
    print("======================================")

    print()

    print(
        f"Positive: "
        f"{positive_correct}/{positive_total}"
    )

    print(
        f"Negative: "
        f"{negative_correct}/{negative_total}"
    )

    print()

    print(
        f"Positive accuracy: "
        f"{positive_accuracy:.1f}%"
    )

    print(
        f"Negative accuracy: "
        f"{negative_accuracy:.1f}%"
    )

    print(
        f"Overall accuracy: "
        f"{overall_accuracy:.1f}%"
    )

    print()

    print(
        f"Average positive wake probability: "
        f"{avg_positive:.3f}"
    )

    print(
        f"Average negative wake probability: "
        f"{avg_negative:.3f}"
    )

    print()

    print(
        f"False negatives: "
        f"{len(false_negative_files)}"
    )

    print(
        f"False positives: "
        f"{len(false_positive_files)}"
    )

    # --------------------------------------------------------
    # FALSE POSITIVES
    # --------------------------------------------------------

    if false_positive_files:

        print()
        print("======================================")
        print("        FALSE POSITIVES")
        print("======================================")

        for path, probability in sorted(
            false_positive_files,
            key=lambda x: x[1],
            reverse=True
        )[:30]:

            print(
                f"{probability:.4f}  {path}"
            )

    # --------------------------------------------------------
    # FALSE NEGATIVES
    # --------------------------------------------------------

    if false_negative_files:

        print()
        print("======================================")
        print("        FALSE NEGATIVES")
        print("======================================")

        for path, probability in sorted(
            false_negative_files,
            key=lambda x: x[1]
        )[:30]:

            print(
                f"{probability:.4f}  {path}"
            )

    # --------------------------------------------------------
    # INTERPRETATION
    # --------------------------------------------------------

    print()
    print("======================================")
    print("          INTERPRETATION")
    print("======================================")

    if overall_accuracy >= 95:

        print(
            "EXCELLENT: Model is looking strong."
        )

    elif overall_accuracy >= 90:

        print(
            "GOOD: Model is usable, but can still improve."
        )

    elif overall_accuracy >= 80:

        print(
            "FAIR: More training/data is recommended."
        )

    else:

        print(
            "PROBLEM: Model needs improvement."
        )

    if negative_accuracy < 90:

        print(
            "WARNING: Too many false positives."
        )

        print(
            "Add more varied negative samples."
        )

    if positive_accuracy < 90:

        print(
            "WARNING: Too many false negatives."
        )

        print(
            "Add more varied positive samples."
        )

    print()
    print("======================================")
    print("Evaluation complete.")
    print("======================================")


if __name__ == "__main__":

    main()