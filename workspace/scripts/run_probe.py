"""Lua 프로브 실행기 — 스크린샷 목록 대신 MAX_FRAME 만 치환한다."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MESEN = Path(r"H:\Mesen\Mesen.exe")
PROJECT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(PROJECT / "original" / "Metroid - Zero Mission (Japan).gba"))
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", default=str(PROJECT / "qa" / "logs"))
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="mzm_probe_"))
    try:
        rom_tmp = tmp / "rom.gba"
        shutil.copy2(Path(a.rom), rom_tmp)
        src = Path(a.script).read_text(encoding="utf-8")
        src = src.replace("@@OUT_DIR@@", str(out).replace("\\", "/"))
        src = src.replace("@@MAX_FRAME@@", str(a.frames))
        s_tmp = tmp / "probe.lua"
        s_tmp.write_text(src, encoding="utf-8")

        cmd = [str(MESEN), "--testRunner", str(s_tmp), str(rom_tmp), "--enableStdout"]
        print("run:", " ".join(cmd))
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
        print("exit:", p.returncode)
        if p.stdout:
            print(p.stdout[-6000:])
        if p.stderr:
            print("--- stderr ---")
            print(p.stderr[-3000:])
        sys.exit(p.returncode)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
