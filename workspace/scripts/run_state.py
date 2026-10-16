"""세이브스테이트를 로드해 프로브를 실행한다.

Mesen 은 세이브스테이트를 ROM 파일명 기준으로 찾으므로(SaveStates/<romname>_<슬롯>.mss),
ROM 을 임시 폴더에 복사할 때도 **원래 파일명을 유지**해야 한다.
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

MESEN = Path(r"H:\Mesen\Mesen.exe")
PROJECT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--slot", type=int, default=1)
    ap.add_argument("--loadat", type=int, default=300,
                    help="세이브스테이트를 로드할 프레임(게임 초기화 후여야 온전히 복원된다)")
    ap.add_argument("--wait", type=int, default=60,
                    help="세이브스테이트 로드 후 덤프까지 대기 프레임")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()

    rom = Path(a.rom).resolve()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="mzm_state_"))
    try:
        # ROM 이름을 그대로 유지해야 세이브스테이트 슬롯이 맞는다
        rom_tmp = tmp / rom.name
        shutil.copy2(rom, rom_tmp)

        src = Path(a.script).read_text(encoding="utf-8")
        src = src.replace("@@OUT_DIR@@", str(out).replace("\\", "/"))
        src = src.replace("@@MAX_FRAME@@", str(a.frames))
        src = src.replace("@@SLOT@@", str(a.slot))
        src = src.replace("@@WAIT@@", str(a.wait))
        src = src.replace("@@LOADAT@@", str(a.loadat))
        lua = tmp / "probe.lua"
        lua.write_text(src, encoding="utf-8")

        p = subprocess.run([str(MESEN), "--testRunner", str(lua), str(rom_tmp),
                            "--enableStdout"],
                           capture_output=True, text=True, timeout=a.timeout,
                           encoding="utf-8", errors="replace")
        if p.stdout:
            tail = [ln for ln in p.stdout.splitlines() if ln.strip()][-6:]
            print("\n".join(tail))
        return p.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
