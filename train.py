import os
import soundfile as sf
import torch
import torchaudio

from torch import nn
from torch.utils.data import Dataset, DataLoader, random_split


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

BATCH_SIZE = 16
EPOCHS = 40
LEARNING_RATE = 0.001


# ============================================================
# DATASET
# ============================================================

class WakeWordDataset(Dataset):

    def __init__(self, files, labels):

        self.files = files
        self.labels = labels

        self.mfcc = torchaudio.transforms.MFCC(
            sample_rate=SAMPLE_RATE,
            n_mfcc=40,
            melkwargs={
                "n_fft": 400,
                "hop_length": 160,
                "n_mels": 64
            }
        )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, index):

        path = self.files[index]
        label = self.labels[index]

        audio, sr = sf.read(
            path,
            dtype="float32"
        )

        # Convert numpy -> tensor
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
        features = self.mfcc(waveform)

        return (
            features,
            torch.tensor(
                label,
                dtype=torch.long
            )
        )


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

            nn.AdaptiveAvgPool2d(
                (1, 1)
            ),

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
# MAIN TRAINING
# ============================================================

def main():

    print("==============================")
    print("   Z3RO WAKE WORD TRAINING")
    print("==============================")

    positive_files = find_wavs(
        POSITIVE_DIR
    )

    negative_files = find_wavs(
        NEGATIVE_DIR
    )

    print()

    print(
        f"Positive samples: {len(positive_files)}"
    )

    print(
        f"Negative samples: {len(negative_files)}"
    )

    total = (
        len(positive_files)
        +
        len(negative_files)
    )

    print(
        f"Total samples: {total}"
    )

    # Check dataset

    if len(positive_files) == 0:

        print()
        print("ERROR: No positive WAV files found.")
        print(POSITIVE_DIR)

        return

    if len(negative_files) == 0:

        print()
        print("ERROR: No negative WAV files found.")
        print(NEGATIVE_DIR)

        return

    # Files + labels

    files = (
        positive_files
        +
        negative_files
    )

    labels = (
        [1] * len(positive_files)
        +
        [0] * len(negative_files)
    )

    # Dataset

    dataset = WakeWordDataset(
        files,
        labels
    )

    # Train / validation split

    train_size = int(
        len(dataset) * 0.8
    )

    val_size = (
        len(dataset)
        -
        train_size
    )

    train_dataset, val_dataset = random_split(
        dataset,
        [
            train_size,
            val_size
        ],
        generator=torch.Generator().manual_seed(42)
    )

    # DataLoaders

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    # Device

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print(
        f"Using device: {device}"
    )

    # Model

    model = WakeWordModel().to(
        device
    )

    # Loss

    criterion = nn.CrossEntropyLoss()

    # Optimizer

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )

    best_accuracy = 0.0

    print()
    print("Starting training...")
    print()

    # ========================================================
    # TRAINING LOOP
    # ========================================================

    for epoch in range(EPOCHS):

        model.train()

        total_loss = 0.0

        correct = 0
        total_count = 0

        for features, labels_batch in train_loader:

            features = features.to(
                device
            )

            labels_batch = labels_batch.to(
                device
            )

            optimizer.zero_grad()

            outputs = model(
                features
            )

            loss = criterion(
                outputs,
                labels_batch
            )

            loss.backward()

            optimizer.step()

            total_loss += loss.item()

            predictions = outputs.argmax(
                dim=1
            )

            correct += (
                predictions == labels_batch
            ).sum().item()

            total_count += (
                labels_batch.size(0)
            )

        train_accuracy = (
            100.0
            *
            correct
            /
            total_count
        )

        # ====================================================
        # VALIDATION
        # ====================================================

        model.eval()

        val_correct = 0
        val_total = 0

        positive_correct = 0
        positive_total = 0

        negative_correct = 0
        negative_total = 0

        with torch.no_grad():

            for features, labels_batch in val_loader:

                features = features.to(
                    device
                )

                labels_batch = labels_batch.to(
                    device
                )

                outputs = model(
                    features
                )

                predictions = outputs.argmax(
                    dim=1
                )

                val_correct += (
                    predictions == labels_batch
                ).sum().item()

                val_total += (
                    labels_batch.size(0)
                )

                # Positive

                positive_mask = (
                    labels_batch == 1
                )

                positive_total += (
                    positive_mask.sum().item()
                )

                positive_correct += (
                    (
                        predictions[positive_mask]
                        == 1
                    )
                    .sum()
                    .item()
                )

                # Negative

                negative_mask = (
                    labels_batch == 0
                )

                negative_total += (
                    negative_mask.sum().item()
                )

                negative_correct += (
                    (
                        predictions[negative_mask]
                        == 0
                    )
                    .sum()
                    .item()
                )

        val_accuracy = (
            100.0
            *
            val_correct
            /
            val_total
        )

        positive_accuracy = (

            100.0
            *
            positive_correct
            /
            positive_total

            if positive_total > 0

            else 0
        )

        negative_accuracy = (

            100.0
            *
            negative_correct
            /
            negative_total

            if negative_total > 0

            else 0
        )

        print(
            f"Epoch {epoch + 1:02d}/{EPOCHS} | "
            f"Loss: {total_loss / len(train_loader):.4f} | "
            f"Train: {train_accuracy:.1f}% | "
            f"Val: {val_accuracy:.1f}% | "
            f"Wake: {positive_accuracy:.1f}% | "
            f"Neg: {negative_accuracy:.1f}%"
        )

        # ====================================================
        # SAVE BEST MODEL
        # ====================================================

        if val_accuracy > best_accuracy:

            best_accuracy = val_accuracy

            torch.save(
                model.state_dict(),
                MODEL_PATH
            )

            print(
                f"-> Best model saved "
                f"({best_accuracy:.1f}%)"
            )

    # ========================================================
    # DONE
    # ========================================================

    print()
    print("==============================")
    print("Training complete!")
    print("==============================")

    print()

    print(
        f"Best validation accuracy: "
        f"{best_accuracy:.1f}%"
    )

    print()

    print("Model saved to:")

    print(MODEL_PATH)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()