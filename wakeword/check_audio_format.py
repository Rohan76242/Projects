import os
import soundfile as sf

FOLDERS = ["positive", "negative"]

def main():
    for folder in FOLDERS:
        if not os.path.exists(folder):
            print(f"Skipping missing folder: {folder}")
            continue

        print(f"\n=== {folder} ===")
        seen = {}

        files = sorted(os.listdir(folder))
        for fname in files:
            if not fname.lower().endswith(".wav"):
                continue

            path = os.path.join(folder, fname)
            info = sf.info(path)

            key = (info.samplerate, info.channels, info.subtype, round(info.duration, 3))

            if key not in seen:
                seen[key] = []
            seen[key].append(fname)

        print(f"Found {len(seen)} distinct format group(s):")
        for key, flist in seen.items():
            samplerate, channels, subtype, duration = key
            print(f"  samplerate={samplerate} channels={channels} subtype={subtype} duration={duration}s "
                  f"-> {len(flist)} files (e.g. {flist[0]} .. {flist[-1]})")

if __name__ == "__main__":
    main()
