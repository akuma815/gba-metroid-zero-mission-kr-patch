"""Mesen 2 헤드리스 실행 러너.

Lua 템플릿의 플레이스홀더를 치환해 임시 스크립트를 만들고,
공백 없는 경로로 ROM을 복사한 뒤 --testRunner 로 실행한다.

PowerShell 5.1의 인용 문제를 피하려고 subprocess 리스트 인자를 사용한다.
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


def lua_table(shots):
    items = ", ".join(
        "{frame=%d, name=%s}" % (s["frame"], json.dumps(s["name"])) for s in shots
    )
    return "{" + items + "}"


def run(rom: Path, template: Path, out_dir: Path, shots, timeout=300):
    # Mesen의 CWD가 아니라 프로젝트 기준으로 저장되도록 절대 경로로 고정한다
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="mzm_mesen_"))
    try:
        # 공백 없는 임시 경로로 ROM 복사 (Mesen 인자 파싱 안정화)
        rom_tmp = tmp / "rom.gba"
        shutil.copy2(rom, rom_tmp)

        script = template.read_text(encoding="utf-8")
        script = script.replace("@@OUT_DIR@@", str(out_dir).replace("\\", "/"))
        script = script.replace("@@SHOTS@@", lua_table(shots))
        script_tmp = tmp / "script.lua"
        script_tmp.write_text(script, encoding="utf-8")

        cmd = [str(MESEN), "--testRunner", str(script_tmp), str(rom_tmp), "--enableStdout"]
        print("run:", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        print("exit:", proc.returncode)
        if proc.stdout:
            print("--- stdout ---")
            print(proc.stdout[-4000:])
        if proc.stderr:
            print("--- stderr ---")
            print(proc.stderr[-2000:])
        return proc.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(PROJECT / "original" / "Metroid - Zero Mission (Japan).gba"))
    ap.add_argument("--template", default=str(PROJECT / "workspace" / "tests" / "boot_capture.lua"))
    ap.add_argument("--out", default=str(PROJECT / "qa" / "screenshots" / "baseline"))
    ap.add_argument("--frames", default="120,300,600,900,1200",
                    help="쉼표 구분 프레임 번호")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    shots = [{"frame": int(f), "name": "f"} for f in args.frames.split(",")]
    rc = run(Path(args.rom), Path(args.template), Path(args.out), shots, args.timeout)
    sys.exit(rc)


if __name__ == "__main__":
    main()
