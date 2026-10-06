"""Joins the clips from record-silent.mjs into one silent MP4 and prints each
scene's start time (for the presenter script).

    python build-silent.py <raw dir> <output.mp4>

Needs ffmpeg: on PATH, or from the imageio-ffmpeg package.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FF = shutil.which("ffmpeg") or "ffmpeg"

FADE = 0.25   # a short fade in and out on every scene


def main(raw: Path, out: Path) -> None:
    scenes = json.loads((Path(__file__).parent / "silent-scenes.json").read_text())
    tmp = Path(tempfile.mkdtemp())
    parts, at = [], 0.0
    for s in scenes:
        r = json.loads((raw / f"{s['id']}.json").read_text())
        part = tmp / f"{s['id']}.mp4"
        d = r["dur"]
        subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{r['start']:.2f}", "-i", r["path"], "-t", f"{d:.2f}",
                        "-vf", f"fade=in:st=0:d={FADE},fade=out:st={d - FADE:.2f}:d={FADE},fps=30,format=yuv420p",
                        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(part)], check=True)
        parts.append(part)
        print(f"{s['id']}  {int(at // 60)}:{at % 60:05.2f}  {d:5.1f}s  {s['title']}")
        at += d
    (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
                    "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    print(f"total {int(at // 60)}:{at % 60:04.1f} → {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
