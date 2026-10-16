"""번역 배치의 고유 한글을 수집해 코드를 배정한다.

배정은 누적된다. 이미 배정된 글자의 코드는 유지되고 새 글자만 뒤에 붙는다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hangul_alloc import Allocation, capacity  # noqa: E402
from rombuild import PROJECT  # noqa: E402

ALLOC_PATH = PROJECT / "workspace" / "text" / "translation" / "hangul_codes.json"
TOKEN_RE = re.compile(r"\{[^}]*\}")
HANGUL_RE = re.compile(r"[가-힣]")


def collect(texts) -> list[str]:
    """등장 순서를 유지하며 고유 한글을 모은다."""
    seen, out = set(), []
    for t in texts:
        for ch in HANGUL_RE.findall(TOKEN_RE.sub("", t)):
            if ch not in seen:
                seen.add(ch)
                out.append(ch)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="{id: ko} JSON 파일들 또는 원장")
    a = ap.parse_args()

    texts = []
    for p in a.inputs:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        if isinstance(data, dict) and "entries" in data:
            texts += [e["ko"] for e in data["entries"] if e.get("ko")]
        else:
            texts += list(data.values())

    chars = collect(texts)
    alloc = Allocation(ALLOC_PATH)
    before = len(alloc.char_to_code)
    added = alloc.assign(chars)
    alloc.save()

    print(f"입력 텍스트 {len(texts)}건, 고유 한글 {len(chars)}자")
    print(f"배정: 기존 {before}자 + 신규 {len(added)}자 = {len(alloc.char_to_code)}자 "
          f"(용량 {capacity()}자, 잔여 {capacity() - len(alloc.char_to_code)}자)")
    if added:
        codes = alloc.char_to_code
        sample = " ".join(f"{c}=0x{codes[c]:04X}" for c in added[:10])
        print(f"신규 예시: {sample}")
    print(f"-> {ALLOC_PATH}")


if __name__ == "__main__":
    main()
