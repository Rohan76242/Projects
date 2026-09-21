"""
Augments existing WAV files to multiply your dataset size and add
variation, which helps the model generalize instead of memorizing
exact recording conditions.

Run from your project root (C:\\sobia\\wakeword):

    python augment_data.py

It reads from positive/ and negative/ and writes augmented copies into
positive_aug/ and negative_aug/ so your originals are untouched.
After running, merge positive_aug into positive and negative_aug into
negative (or point train.py at both folders) before retraining.

Requires: pip install soundfile numpy librosa
"""

import os
import numpy as np
import soundfile as sf
import librosa

SOURCE_FOLDERS = {
    "positive": "positive_aug",
    "negative": "negative_aug",
}

SAMPLE_RATE = 16000


def load_wav(path):
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
    return audio


def add_noise(audio, noise_level):
    noise = np.random.randn(len(audio)).astype(np.float32)
    return audio + noise_level * noise


def pitch_shift(audio, n_steps):
    return librosa.effects.pitch_shift(audio, sr=SAMPLE_RATE, n_steps=n_steps)


def time_stretch(audio, rate):
    stretched = librosa.effects.time_stretch(audio, rate=rate)
    # Pad or trim back to original length
    if len(stretched) < len(audio):
        stretched = np.pad(stretched, (0, len(audio) - len(stretched)))
    else:
        stretched = stretched[: len(audio)]
    return stretched


def change_volume(audio, factor):
    return np.clip(audio * factor, -1.0, 1.0)


def augment_file(audio):
    """Returns a dict of {suffix: augmented_audio}."""
    variants = {}

    variants["noise_low"] = add_noise(audio, 0.005)
    variants["noise_high"] = add_noise(audio, 0.02)

    try:
        variants["pitch_up"] = pitch_shift(audio, 2)
        variants["pitch_down"] = pitch_shift(audio, -2)
    except Exception as e:
        print(f"  pitch shift failed: {e}")

    try:
        variants["stretch_fast"] = time_stretch(audio, 1.1)
        variants["stretch_slow"] = time_stretch(audio, 0.9)
    except Exception as e:
        print(f"  time stretch failed: {e}")

    variants["quiet"] = change_volume(audio, 0.6)
    variants["loud"] = change_volume(audio, 1.4)

    return variants


def process_folder(src_folder, dst_folder):
    if not os.path.exists(src_folder):
        print(f"Skipping missing folder: {src_folder}")
        return

    os.makedirs(dst_folder, exist_ok=True)

    files = sorted(f for f in os.listdir(src_folder) if f.lower().endswith(".wav"))
    print(f"\nProcessing {len(files)} files from {src_folder} -> {dst_folder}")

    for fname in files:
        path = os.path.join(src_folder, fname)
        base = os.path.splitext(fname)[0]

        try:
            audio = load_wav(path)
        except Exception as e:
            print(f"  Failed to load {fname}: {e}")
            continue

        variants = augment_file(audio)

        for suffix, aug_audio in variants.items():
            out_name = f"{base}_{suffix}.wav"
            out_path = os.path.join(dst_folder, out_name)
            sf.write(out_path, aug_audio, SAMPLE_RATE, subtype="PCM_16")

        print(f"  {fname}: wrote {len(variants)} variants")


def main():
    for src, dst in SOURCE_FOLDERS.items():
        process_folder(src, dst)

    print("\nDone. Review positive_aug/ and negative_aug/, then merge them")
    print("into positive/ and negative/ (or point train.py at both) and retrain.")


if __name__ == "__main__":
    main()
