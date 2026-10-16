"""지정 프레임에서 화면 상태를 덤프하는 헤드리스 러너.

사용: run_dump.py --rom build/x.gba --out qa/logs/title --at 2400:title,2600:title2
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MESEN = Path(r"H:\Mesen\Mesen.exe")
PROJECT = Path(__file__).resolve().parents[2]
TEMPLATE = PROJECT / "workspace" / "tests" / "probe_frame_dump.lua"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--at", required=True,
                    help="프레임:이름 쉼표 구분 (예: 2400:title,2600:title2)")
    ap.add_argument("--max", type=int, default=0, help="0 이면 마지막 덤프 +30")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    shots = []
    for item in a.at.split(","):
        f, name = item.split(":")
        shots.append({"frame": int(f), "name": name})
    shots.sort(key=lambda s: s["frame"])
    max_frame = a.max or shots[-1]["frame"] + 30

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="mzm_dump_"))
    try:
        rom_tmp = tmp / "rom.gba"
        shutil.copy2(Path(a.rom).resolve(), rom_tmp)
        src = TEMPLATE.read_text(encoding="utf-8")
        src = src.replace("@@OUT_DIR@@", str(out).replace("\\", "/"))
        src = src.replace("@@FRAMES@@", "{" + ", ".join(
            "{frame=%d, name=%s}" % (s["frame"], json.dumps(s["name"])) for s in shots) + "}")
        src = src.replace("@@MAX_FRAME@@", str(max_frame))
        lua = tmp / "dump.lua"
        lua.write_text(src, encoding="utf-8")
        p = subprocess.run([str(MESEN), "--testRunner", str(lua), str(rom_tmp),
                            "--enableStdout"],
                           capture_output=True, text=True, timeout=a.timeout,
                           encoding="utf-8", errors="replace")
        for ln in (p.stdout or "").splitlines():
            if ln.strip() and not ln.startswith("["):
                print(ln)
        return p.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
