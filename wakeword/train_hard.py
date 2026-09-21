import os
import random

import numpy as np
import soundfile as sf
import torch
import torchaudio

from torch import nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"

POSITIVE_DIR = os.path.join(
    BASE_DIR,
    "positive"
)

NEGATIVE_DIR = os.path.join(
    BASE_DIR,
    "negative"
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

BATCH_SIZE = 16
EPOCHS = 40
LEARNING_RATE = 0.0005

# Hard negatives are sampled more frequently
HARD_NEGATIVE_WEIGHT = 4.0

SEED = 42


# ============================================================
# REPRODUCIBILITY
# ============================================================

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


# ============================================================
# MFCC
# ============================================================

MFCC = torchaudio.transforms.MFCC(
    sample_rate=SAMPLE_RATE,
    n_mfcc=40,
    melkwargs={
        "n_fft": 400,
        "hop_length": 160,
        "n_mels": 64
    }
)


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

    if audio.ndim > 1:

        audio = audio.mean(
            axis=1
        )

    waveform = torch.from_numpy(
        audio
    ).unsqueeze(0)

    if sr != SAMPLE_RATE:

        waveform = torchaudio.functional.resample(
            waveform,
            sr,
            SAMPLE_RATE
        )

    if waveform.shape[1] < NUM_SAMPLES:

        waveform = torch.nn.functional.pad(
            waveform,
            (
                0,
                NUM_SAMPLES - waveform.shape[1]
            )
        )

    else:

        waveform = waveform[
            :,
            :NUM_SAMPLES
        ]

    return waveform


# ============================================================
# DATASET
# ============================================================

class WakeWordDataset(Dataset):

    def __init__(
        self,
        files,
        labels
    ):

        self.files = files
        self.labels = labels

    def __len__(self):

        return len(self.files)

    def __getitem__(self, index):

        waveform = load_audio(
            self.files[index]
        )

        features = MFCC(
            waveform
        )

        label = torch.tensor(
            self.labels[index],
            dtype=torch.long
        )

        return features, label


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
# MAIN
# ============================================================

def main():

    print()
    print("========================================")
    print("       Z3RO HARD-NEGATIVE TRAINING")
    print("========================================")
    print()

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    positive_files = find_wavs(
        POSITIVE_DIR
    )

    negative_files = find_wavs(
        NEGATIVE_DIR
    )

    hard_files = find_wavs(
        HARD_NEGATIVE_DIR
    )

    # Make sure hard negatives are actually negatives
    hard_files = [
        path
        for path in hard_files
        if os.path.basename(path)
        in {
            os.path.basename(x)
            for x in negative_files
        }
    ]

    print(
        f"Positive samples: {len(positive_files)}"
    )

    print(
        f"Negative samples: {len(negative_files)}"
    )

    print(
        f"Hard negatives: {len(hard_files)}"
    )

    total = (
        len(positive_files)
        +
        len(negative_files)
    )

    print(
        f"Total samples: {total}"
    )

    print()

    if not positive_files:

        print(
            "ERROR: No positive WAV files."
        )

        return

    if not negative_files:

        print(
            "ERROR: No negative WAV files."
        )

        return

    # --------------------------------------------------------
    # FILES + LABELS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # HARD NEGATIVE NAMES
    # --------------------------------------------------------

    hard_names = {
        os.path.basename(path)
        for path in hard_files
    }

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    dataset = WakeWordDataset(
        files,
        labels
    )

    # --------------------------------------------------------
    # TRAIN / VALIDATION SPLIT
    # --------------------------------------------------------

    indices = list(
        range(len(dataset))
    )

    random.Random(SEED).shuffle(
        indices
    )

    train_size = int(
        len(indices) * 0.8
    )

    train_indices = indices[
        :train_size
    ]

    val_indices = indices[
        train_size:
    ]

    # --------------------------------------------------------
    # WEIGHTS FOR TRAINING
    # --------------------------------------------------------

    sample_weights = []

    for index in train_indices:

        filename = os.path.basename(
            files[index]
        )

        if filename in hard_names:

            sample_weights.append(
                HARD_NEGATIVE_WEIGHT
            )

        else:

            sample_weights.append(
                1.0
            )

    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(train_indices),
        replacement=True
    )

    train_subset = torch.utils.data.Subset(
        dataset,
        train_indices
    )

    val_subset = torch.utils.data.Subset(
        dataset,
        val_indices
    )

    train_loader = DataLoader(
        train_subset,
        batch_size=BATCH_SIZE,
        sampler=sampler
    )

    val_loader = DataLoader(
        val_subset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Using device: {device}"
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    model = WakeWordModel().to(
        device
    )

    criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=1e-4
    )

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    best_balanced_score = 0.0

    print()
    print(
        "Starting hard-negative training..."
    )
    print()

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
            * correct
            / total_count
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

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

                probabilities = torch.softmax(
                    outputs,
                    dim=1
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

                positive_mask = (
                    labels_batch == 1
                )

                negative_mask = (
                    labels_batch == 0
                )

                positive_total += (
                    positive_mask.sum().item()
                )

                negative_total += (
                    negative_mask.sum().item()
                )

                positive_correct += (
                    (
                        predictions[
                            positive_mask
                        ] == 1
                    )
                    .sum()
                    .item()
                )

                negative_correct += (
                    (
                        predictions[
                            negative_mask
                        ] == 0
                    )
                    .sum()
                    .item()
                )

        val_accuracy = (
            100.0
            * val_correct
            / val_total
        )

        positive_accuracy = (

            100.0
            * positive_correct
            / positive_total

            if positive_total > 0
            else 0.0
        )

        negative_accuracy = (

            100.0
            * negative_correct
            / negative_total

            if negative_total > 0
            else 0.0
        )

        balanced_score = (
            positive_accuracy
            +
            negative_accuracy
        ) / 2.0

        print(
            f"Epoch {epoch + 1:02d}/{EPOCHS} | "
            f"Loss: {total_loss / len(train_loader):.4f} | "
            f"Train: {train_accuracy:.1f}% | "
            f"Val: {val_accuracy:.1f}% | "
            f"Wake: {positive_accuracy:.1f}% | "
            f"Neg: {negative_accuracy:.1f}% | "
            f"Balanced: {balanced_score:.1f}%"
        )

        # ----------------------------------------------------
        # SAVE BEST MODEL
        # ----------------------------------------------------

        if balanced_score > best_balanced_score:

            best_balanced_score = (
                balanced_score
            )

            torch.save(
                model.state_dict(),
                MODEL_PATH
            )

            print(
                f"-> Best model saved "
                f"({best_balanced_score:.1f}%)"
            )

    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    print()
    print("========================================")
    print("Hard-negative training complete!")
    print("========================================")
    print()

    print(
        f"Best balanced score: "
        f"{best_balanced_score:.1f}%"
    )

    print()

    print(
        "Model saved to:"
    )

    print(
        MODEL_PATH
    )

    print()

    print(
        "Next step: run test_model.py"
    )


if __name__ == "__main__":
    main()