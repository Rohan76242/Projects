import os
import soundfile as sf
import torch
import torchaudio
import torch.nn.functional as F
from torch import nn

BASE_DIR = r"C:\sobia\wakeword"
MODEL_PATH = os.path.join(BASE_DIR, "wakeword_model.pth")
POSITIVE_DIR = os.path.join(BASE_DIR, "positive")
NEGATIVE_DIR = os.path.join(BASE_DIR, "negative")

SAMPLE_RATE = 16000
NUM_SAMPLES = 16000


class WakeWordModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),

            nn.AdaptiveAvgPool2d((1, 1)),

            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 2)
        )

    def forward(self, x):
        return self.network(x)


def find_wavs(folder):
    result = []
    if not os.path.exists(folder):
        return result
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(".wav"):
                result.append(os.path.join(root, file))
    return sorted(result)


def load_audio(path):
    audio, sr = sf.read(path, dtype="float32")

    if audio.ndim == 1:
        waveform = torch.from_numpy(audio).unsqueeze(0)
    else:
        waveform = torch.from_numpy(audio.T)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

    if sr != SAMPLE_RATE:
        waveform = torchaudio.functional.resample(waveform, sr, SAMPLE_RATE)

    peak = waveform.abs().max()
    if peak > 0:
        waveform = waveform / peak

    if waveform.shape[1] < NUM_SAMPLES:
        waveform = F.pad(waveform, (0, NUM_SAMPLES - waveform.shape[1]))
    else:
        waveform = waveform[:, :NUM_SAMPLES]

    mfcc_transform = torchaudio.transforms.MFCC(
        sample_rate=SAMPLE_RATE,
        n_mfcc=40,
        melkwargs={"n_fft": 400, "hop_length": 160, "n_mels": 64}
    )

    features = mfcc_transform(waveform)
    return features


def get_wake_probability(model, path, device):
    features = load_audio(path).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(features)
        probs = torch.softmax(output, dim=1)
        return probs[0, 1].item()


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    model = WakeWordModel().to(device)
    checkpoint = torch.load(MODEL_PATH, map_location=device)
    model.load_state_dict(checkpoint)
    model.eval()
    print("Model loaded.\n")

    pos_files = find_wavs(POSITIVE_DIR)
    neg_files = find_wavs(NEGATIVE_DIR)

    print(f"Scoring {len(pos_files)} positive files...")
    pos_scores = [get_wake_probability(model, f, device) for f in pos_files]

    print(f"Scoring {len(neg_files)} negative files...")
    neg_scores = [get_wake_probability(model, f, device) for f in neg_files]

    print("\n" + "=" * 60)
    print("THRESHOLD SWEEP")
    print("=" * 60)
    print(f"{'Threshold':>10} | {'Pos detect rate':>16} | {'Neg false-pos rate':>18}")
    print("-" * 60)

    best_threshold = None

    for threshold_pct in range(50, 100):
        threshold = threshold_pct / 100.0

        pos_hits = sum(1 for s in pos_scores if s >= threshold)
        neg_hits = sum(1 for s in neg_scores if s >= threshold)

        pos_rate = 100.0 * pos_hits / len(pos_scores) if pos_scores else 0.0
        neg_rate = 100.0 * neg_hits / len(neg_scores) if neg_scores else 0.0

        marker = ""
        if neg_rate < 2.0 and best_threshold is None:
            best_threshold = threshold
            marker = "  <-- first threshold under 2% FP"

        print(f"{threshold:>10.2f} | {pos_rate:>15.1f}% | {neg_rate:>17.1f}%{marker}")

    print("=" * 60)

    if best_threshold is not None:
        print(f"\nLowest threshold keeping FP rate under 2%: {best_threshold:.2f}")
        pos_hits = sum(1 for s in pos_scores if s >= best_threshold)
        pos_rate = 100.0 * pos_hits / len(pos_scores) if pos_scores else 0.0
        print(f"At that threshold, positive detection rate would be: {pos_rate:.1f}%")
    else:
        print("\nNo threshold under 1.00 achieves a <2% false-positive rate.")


if __name__ == "__main__":
    main()