import os
import sys

import soundfile as sf
import torch
import torchaudio
import torch.nn.functional as F

from torch import nn


BASE_DIR = r"C:\sobia\wakeword"

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

SAMPLE_RATE = 16000
NUM_SAMPLES = 16000


class WakeWordModel(nn.Module):

    def __init__(self):

        super().__init__()

        self.network = nn.Sequential(

            # Block 1
            nn.Conv2d(1, 16, kernel_size=3, padding=1),   # 0
            nn.BatchNorm2d(16),                            # 1
            nn.ReLU(),                                     # 2
            nn.MaxPool2d(2),                                # 3

            # Block 2
            nn.Conv2d(16, 32, kernel_size=3, padding=1),   # 4
            nn.BatchNorm2d(32),                             # 5
            nn.ReLU(),                                      # 6
            nn.MaxPool2d(2),                                # 7

            # Block 3
            nn.Conv2d(32, 64, kernel_size=3, padding=1),   # 8
            nn.BatchNorm2d(64),                             # 9
            nn.ReLU(),                                      # 10

            # Global pooling
            nn.AdaptiveAvgPool2d((1, 1)),                   # 11

            # Classifier head
            nn.Flatten(),               # 12
            nn.Linear(64, 32),          # 13
            nn.ReLU(),                  # 14
            nn.Dropout(0.3),            # 15
            nn.Linear(32, 2)            # 16
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

                result.append(
                    os.path.join(
                        root,
                        file
                    )
                )

    return sorted(result)


def load_audio(path):

    print("Reading WAV file...")

    audio, sr = sf.read(
        path,
        dtype="float32"
    )

    if audio.ndim == 1:
        channels = 1
    else:
        channels = audio.shape[1]

    print(f"Sample rate: {sr}")
    print(f"Channels: {channels}")

    if audio.ndim == 1:
        waveform = torch.from_numpy(audio).unsqueeze(0)
    else:
        waveform = torch.from_numpy(audio.T)

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sr != SAMPLE_RATE:
        print(f"Resampling {sr} Hz -> {SAMPLE_RATE} Hz...")
        waveform = torchaudio.functional.resample(waveform, sr, SAMPLE_RATE)

    if waveform.shape[1] < NUM_SAMPLES:
        waveform = F.pad(waveform, (0, NUM_SAMPLES - waveform.shape[1]))
    else:
        waveform = waveform[:, :NUM_SAMPLES]

    print(f"Audio samples: {waveform.shape[1]}")

    print("Creating MFCC features...")

    mfcc_transform = torchaudio.transforms.MFCC(
        sample_rate=SAMPLE_RATE,
        n_mfcc=40,
        melkwargs={
            "n_fft": 400,
            "hop_length": 160,
            "n_mels": 64
        }
    )

    features = mfcc_transform(waveform)

    print(f"MFCC shape: {features.shape}")

    return features


def load_model(device):

    print("Loading model...")

    if not os.path.exists(MODEL_PATH):
        print()
        print("ERROR: Model file not found:")
        print(MODEL_PATH)
        return None

    model = WakeWordModel().to(device)

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device
    )

    model.load_state_dict(checkpoint)

    model.eval()

    print("Model loaded successfully.")

    return model


def test_audio(model, audio_path, device):

    print()
    print("==============================")
    print("Testing audio")
    print("==============================")
    print(f"File: {audio_path}")

    print()
    print("Loading audio...")

    features = load_audio(audio_path)

    features = features.unsqueeze(0)

    print(f"Network input shape: {features.shape}")

    features = features.to(device)

    print()
    print("Running prediction...")
    print("Running neural network...")

    with torch.no_grad():

        output = model(features)

        probabilities = torch.softmax(output, dim=1)

        prediction = output.argmax(dim=1).item()

        confidence = probabilities[0, prediction].item() * 100.0
        wake_probability = probabilities[0, 1].item() * 100.0
        negative_probability = probabilities[0, 0].item() * 100.0

    print()
    print("Raw output:")
    print(output)

    print()
    print("Probabilities:")
    print(probabilities)

    print()
    print("==============================")

    if prediction == 1:
        print("WAKE WORD DETECTED!")
    else:
        print("NOT A WAKE WORD")

    print(f"Prediction: {prediction}")
    print(f"Confidence: {confidence:.2f}%")
    print(f"Wake probability: {wake_probability:.2f}%")
    print(f"Negative probability: {negative_probability:.2f}%")
    print("==============================")


def main():

    print()
    print("==============================")
    print("     Z3RO WAKE WORD TESTER")
    print("==============================")
    print()

    if len(sys.argv) < 2:
        print('Usage: python test.py "C:\\path\\to\\audio.wav"')
        print()
        print("Example:")
        print(r'python test.py "C:\sobia\wakeword\positive\sobia_001.wav"')
        return

    audio_path = sys.argv[1]

    if not os.path.exists(audio_path):
        print()
        print("ERROR: Audio file does not exist:")
        print(audio_path)
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Device: {device}")
    print()

    model = load_model(device)

    if model is None:
        return

    test_audio(model, audio_path, device)


if __name__ == "__main__":
    main()