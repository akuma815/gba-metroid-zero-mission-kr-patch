"""메뉴 QA 러너 — 입력 계획과 캡처 시점을 Lua 로 주입해 화면을 수집한다.

계획은 (프레임, 버튼목록) 과 (프레임, 이름) 목록으로 준다.
버튼 이름은 emu.getInput 이 돌려주는 키를 쓴다: a b l r start select up down left right
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


def lua_plan(presses, shots) -> str:
    lines = []
    for f, btns in presses:
        items = ", ".join(json.dumps(b) for b in btns)
        lines.append(f"press[{f}] = {{{items}}}")
    for f, name in shots:
        lines.append(f"shots[{f}] = {json.dumps(name)}")
    return "\n".join(lines)


def run(rom: Path, out: Path, presses, shots, max_frame: int, timeout=300):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="mzm_qa_"))
    try:
        rom_tmp = tmp / "rom.gba"
        shutil.copy2(rom, rom_tmp)
        src = (PROJECT / "workspace" / "tests" / "qa_menu.lua").read_text(encoding="utf-8")
        src = src.replace("@@OUT_DIR@@", str(out).replace("\\", "/"))
        src = src.replace("@@MAX_FRAME@@", str(max_frame))
        src = src.replace("@@PLAN@@", lua_plan(presses, shots))
        s = tmp / "qa.lua"
        s.write_text(src, encoding="utf-8")

        cmd = [str(MESEN), "--testRunner", str(s), str(rom_tmp), "--enableStdout"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        if p.stdout:
            print(p.stdout[-3000:])
        if p.stderr:
            print("--- stderr ---")
            print(p.stderr[-2000:])
        return p.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(PROJECT / "build" / "mzm_ko.gba"))
    ap.add_argument("--out", default=str(PROJECT / "qa" / "screenshots" / "menu"))
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    # 타이틀은 2400 프레임 근처. START 를 여러 프레임에 걸쳐 눌러 확실히 통과시킨다.
    presses = [(f, ["start"]) for f in range(2450, 2470)]
    # 파일 선택 화면이 나온 뒤를 넓게 캡처한다(전이 타이밍 미상)
    shots = [(f, "after_start") for f in (2500, 2560, 2620, 2700, 2800, 2900, 3000)]
    rc = run(Path(a.rom), Path(a.out), presses, shots, 3050, a.timeout)
    print("exit:", rc)
    for f in sorted(Path(a.out).glob("*.png")):
        print("  ", f.name, f.stat().st_size)


if __name__ == "__main__":
    main()
