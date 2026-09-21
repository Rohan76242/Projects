import os
import shutil
import soundfile as sf
import numpy as np

BASE_DIR = r"C:\sobia\wakeword"

FOLDERS = ["positive", "negative"]

TARGET_SAMPLE_RATE = 16000
TARGET_DURATION_SECONDS = 1.2
TARGET_SAMPLES = int(TARGET_SAMPLE_RATE * TARGET_DURATION_SECONDS)


def backup_folder(folder_path, backup_path):
    if os.path.exists(backup_path):
        print(f"  Backup already exists at {backup_path}, skipping backup step.")
        return
    print(f"  Backing up {folder_path} -> {backup_path}")
    shutil.copytree(folder_path, backup_path)


def standardize_file(path):
    audio, sr = sf.read(path, dtype="float32")

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    length = len(audio)

    if length == TARGET_SAMPLES:
        return audio

    if length > TARGET_SAMPLES:
        start = (length - TARGET_SAMPLES) // 2
        audio = audio[start:start + TARGET_SAMPLES]
    else:
        pad_amount = TARGET_SAMPLES - length
        audio = np.pad(audio, (0, pad_amount))

    return audio


def process_folder(folder_name):
    folder_path = os.path.join(BASE_DIR, folder_name)
    backup_path = os.path.join(BASE_DIR, f"{folder_name}_backup")

    if not os.path.exists(folder_path):
        print(f"Skipping missing folder: {folder_path}")
        return

    print(f"\n=== {folder_name} ===")
    backup_folder(folder_path, backup_path)

    changed = 0
    unchanged = 0
    failed = 0

    for root, dirs, files in os.walk(folder_path):
        for fname in files:
            if not fname.lower().endswith(".wav"):
                continue

            path = os.path.join(root, fname)

            try:
                original_info = sf.info(path)
                original_frames = original_info.frames

                standardized = standardize_file(path)

                sf.write(path, standardized, TARGET_SAMPLE_RATE, subtype="PCM_16")

                if original_frames == TARGET_SAMPLES:
                    unchanged += 1
                else:
                    changed += 1

            except Exception as e:
                print(f"  FAILED on {fname}: {e}")
                failed += 1

    print(f"  Standardized: {changed} files")
    print(f"  Already correct length: {unchanged} files")
    if failed:
        print(f"  FAILED: {failed} files")


def main():
    print(f"Target: {TARGET_SAMPLES} samples ({TARGET_DURATION_SECONDS}s at {TARGET_SAMPLE_RATE}Hz)")

    for folder in FOLDERS:
        process_folder(folder)

    print("\nDone. Originals backed up to positive_backup/ and negative_backup/.")
    print("Next step: retrain with 'python train.py'")


if __name__ == "__main__":
    main()