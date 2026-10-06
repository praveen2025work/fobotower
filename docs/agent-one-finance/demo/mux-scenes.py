import json, subprocess, sys, os, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
ids = sys.argv[1].split(",")
os.makedirs("out", exist_ok=True)
for i in ids:
    r = json.load(open(f"raw/{i}.json"))
    subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{r['start']:.2f}", "-i", r["path"], "-i", f"{i}.wav",
        "-t", f"{r['dur']:.2f}", "-filter_complex", "[1:a]adelay=300|300,apad[a]", "-map", "0:v", "-map", "[a]",
        "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1", f"out/{i}.mp4"], check=True)
    print("ok", i)
