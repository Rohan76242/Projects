import os
import torch
import torchaudio

from torch import nn
from torch.utils.data import Dataset, DataLoader, random_split


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"

POSITIVE_DIR = os.path.join(BASE_DIR, "positive")
NEGATIVE_DIR = os.path.join(BASE_DIR, "negative")

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

SAMPLE_RATE = 16000
CLIP_SECONDS = 1
TARGET_LENGTH = SAMPLE_RATE * CLIP_SECONDS

BATCH_SIZE = 16
EPOCHS = 20
LEARNING_RATE = 0.001

RANDOM_SEED = 42


# ============================================================
# DATASET
# ============================================================

class WakeWordDataset(Dataset):

    def __init__(self, files, labels):
        self.files = files
        self.labels = labels

    def __len__(self):
        return len(self.files)

    def __getitem__(self, index):

        path = self.files[index]
        label = self.labels[index]

        waveform, sample_rate = torchaudio.load(path)

        # Convert stereo -> mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(
                dim=0,
                keepdim=True
            )

        # Resample if necessary
        if sample_rate != SAMPLE_RATE:
            waveform = torchaudio.functional.resample(
                waveform,
                sample_rate,
                SAMPLE_RATE
            )

        # Exactly 1 second
        if waveform.shape[1] < TARGET_LENGTH:

            waveform = torch.nn.functional.pad(
                waveform,
                (0, TARGET_LENGTH - waveform.shape[1])
            )

        else:

            waveform = waveform[:, :TARGET_LENGTH]

        return (
            waveform,
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

        self.features = nn.Sequential(

            nn.Conv1d(
                1,
                16,
                kernel_size=80,
                stride=16
            ),

            nn.ReLU(),

            nn.MaxPool1d(4),

            nn.Conv1d(
                16,
                32,
                kernel_size=9,
                stride=2
            ),

            nn.ReLU(),

            nn.MaxPool1d(4),

            nn.Conv1d(
                32,
                64,
                kernel_size=5,
                stride=2
            ),

            nn.ReLU(),

            nn.AdaptiveAvgPool1d(1)
        )

        self.classifier = nn.Sequential(

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

        x = self.features(x)

        return self.classifier(x)


# ============================================================
# FIND AUDIO FILES
# ============================================================

def find_wav_files(directory):

    files = []

    if not os.path.exists(directory):
        return files

    for root, _, filenames in os.walk(directory):

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
# MAIN
# ============================================================

def main():

    print()
    print("========================================")
    print("       Z3RO WAKE WORD TRAINER")
    print("========================================")
    print()

    # --------------------------------------------------------
    # Check directories
    # --------------------------------------------------------

    os.makedirs(
        POSITIVE_DIR,
        exist_ok=True
    )

    os.makedirs(
        NEGATIVE_DIR,
        exist_ok=True
    )

    print("Positive directory:")
    print(POSITIVE_DIR)
    print()

    print("Negative directory:")
    print(NEGATIVE_DIR)
    print()

    # --------------------------------------------------------
    # Find WAV files
    # --------------------------------------------------------

    print("Searching for audio files...")
    print()

    positive_files = find_wav_files(
        POSITIVE_DIR
    )

    negative_files = find_wav_files(
        NEGATIVE_DIR
    )

    print(
        f"Positive samples: {len(positive_files)}"
    )

    print(
        f"Negative samples: {len(negative_files)}"
    )

    print(
        f"Total samples: "
        f"{len(positive_files) + len(negative_files)}"
    )

    # --------------------------------------------------------
    # Validate dataset
    # --------------------------------------------------------

    if len(positive_files) == 0:

        print()
        print("ERROR:")
        print("No positive WAV files found.")
        print()
        print(
            "Put wake-word recordings inside:"
        )
        print(POSITIVE_DIR)

        return

    if len(negative_files) == 0:

        print()
        print("ERROR:")
        print("No negative WAV files found.")
        print()
        print(
            "Put non-wake-word recordings inside:"
        )
        print(NEGATIVE_DIR)

        return

    if len(positive_files) < 5:

        print()
        print(
            "WARNING: Very few positive samples."
        )
        print(
            "Training may not generalize well."
        )

    if len(negative_files) < 5:

        print()
        print(
            "WARNING: Very few negative samples."
        )
        print(
            "Training may not generalize well."
        )

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    files = (
        positive_files +
        negative_files
    )

    labels = (
        [1] * len(positive_files)
        +
        [0] * len(negative_files)
    )

    print()
    print("Class distribution:")
    print(
        f"Wake word : {len(positive_files)}"
    )
    print(
        f"Negative  : {len(negative_files)}"
    )

    dataset = WakeWordDataset(
        files,
        labels
    )

    # --------------------------------------------------------
    # Train / validation split
    # --------------------------------------------------------

    torch.manual_seed(
        RANDOM_SEED
    )

    train_size = int(
        len(dataset) * 0.8
    )

    val_size = (
        len(dataset) -
        train_size
    )

    if train_size == 0 or val_size == 0:

        print()
        print(
            "ERROR: Dataset is too small "
            "for an 80/20 train/validation split."
        )

        return

    train_dataset, val_dataset = random_split(
        dataset,
        [
            train_size,
            val_size
        ],
        generator=torch.Generator().manual_seed(
            RANDOM_SEED
        )
    )

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

    # --------------------------------------------------------
    # Device
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print(
        f"Using device: {device}"
    )

    if device.type == "cuda":

        print(
            f"GPU: "
            f"{torch.cuda.get_device_name(0)}"
        )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = WakeWordModel().to(
        device
    )

    # --------------------------------------------------------
    # Class weights
    # --------------------------------------------------------

    class_counts = torch.bincount(
        torch.tensor(
            labels,
            dtype=torch.long
        ),
        minlength=2
    )

    class_weights = (
        len(labels)
        /
        (
            2.0 *
            class_counts.float()
        )
    )

    class_weights = class_weights.to(
        device
    )

    print()
    print("Class weights:")
    print(class_weights)

    criterion = nn.CrossEntropyLoss(
        weight=class_weights
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )

    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    print()
    print("========================================")
    print("           STARTING TRAINING")
    print("========================================")
    print()

    for epoch in range(EPOCHS):

        # ====================================================
        # TRAINING
        # ====================================================

        model.train()

        total_loss = 0.0

        correct = 0
        total = 0

        for audio, labels_batch in train_loader:

            audio = audio.to(
                device
            )

            labels_batch = labels_batch.to(
                device
            )

            optimizer.zero_grad()

            outputs = model(
                audio
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
                predictions ==
                labels_batch
            ).sum().item()

            total += labels_batch.size(0)

        train_accuracy = (
            100.0 *
            correct /
            total
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

            for audio, labels_batch in val_loader:

                audio = audio.to(
                    device
                )

                labels_batch = labels_batch.to(
                    device
                )

                outputs = model(
                    audio
                )

                predictions = outputs.argmax(
                    dim=1
                )

                val_correct += (
                    predictions ==
                    labels_batch
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
                    ).sum().item()
                )

                negative_correct += (
                    (
                        predictions[
                            negative_mask
                        ] == 0
                    ).sum().item()
                )

        val_accuracy = (
            100.0 *
            val_correct /
            val_total
        )

        positive_accuracy = (
            100.0 *
            positive_correct /
            positive_total
            if positive_total > 0
            else 0.0
        )

        negative_accuracy = (
            100.0 *
            negative_correct /
            negative_total
            if negative_total > 0
            else 0.0
        )

        average_loss = (
            total_loss /
            len(train_loader)
        )

        print(
            f"Epoch "
            f"{epoch + 1:02d}/{EPOCHS} | "
            f"Loss: {average_loss:.4f} | "
            f"Train: {train_accuracy:.1f}% | "
            f"Val: {val_accuracy:.1f}% | "
            f"Wake: {positive_accuracy:.1f}% | "
            f"Neg: {negative_accuracy:.1f}%"
        )

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    torch.save(
        model.state_dict(),
        MODEL_PATH
    )

    print()
    print("========================================")
    print("          TRAINING COMPLETE")
    print("========================================")
    print()

    print("Model saved to:")
    print(MODEL_PATH)

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()