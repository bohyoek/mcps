"""영상 렌더링 — index.html을 프레임 단위로 찍어 mp4로 만든다.

실행 (레포 루트):
  .venv/Scripts/python video/render.py preview 1.5 9.5 20 ...   → video/preview/t_XX.png (확인용 프레임)
  .venv/Scripts/python video/render.py video                     → video/frames.mp4 (무음, 30fps)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FPS = 30


def total():
    js = (HERE / "timeline.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"window\.TIMELINE = (.*);", js, re.S).group(1))["total"]


def open_page(p):
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto((HERE / "index.html").as_uri() + "?render=1", wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(300)
    return b, pg


def preview(times):
    out = HERE / "preview"
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b, pg = open_page(p)
        for t in times:
            pg.evaluate(f"__render({t})")
            pg.screenshot(path=str(out / f"t_{float(t):06.2f}.png"))
        b.close()


def video():
    n = int(total() * FPS)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-vcodec", "mjpeg", "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(HERE / "frames.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b, pg = open_page(p)
        for f in range(n):
            pg.evaluate(f"__render({f / FPS})")
            proc.stdin.write(pg.screenshot(type="jpeg", quality=93))
            if f % 300 == 0:
                print(f"{f}/{n} 프레임", flush=True)
        b.close()
    proc.stdin.close()
    proc.wait()
    print("완료", HERE / "frames.mp4", n, "프레임")


def sheet():
    """preview/*.png 를 한 장(3열)으로 모은 확인용 시트"""
    import shutil
    import tempfile
    files = sorted((HERE / "preview").glob("t_*.png"))
    with tempfile.TemporaryDirectory() as d:
        for i, f in enumerate(files):
            shutil.copy(f, Path(d) / f"img{i:03d}.png")
        rows = (len(files) + 2) // 3
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(Path(d) / "img%03d.png"),
                        "-vf", f"scale=640:360,tile=3x{rows}", "-frames:v", "1", str(HERE / "preview" / "sheet.png")], check=True)


if __name__ == "__main__":
    if sys.argv[1] == "preview":
        preview(sys.argv[2:])
        sheet()
    else:
        video()
