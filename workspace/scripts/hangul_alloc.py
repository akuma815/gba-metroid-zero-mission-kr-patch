"""한글 코드 할당 — 번역 코퍼스의 고유 글자에 전각 코드 쌍을 배정한다.

배정 규칙
- 전각은 코드 쌍(짝수=좌반부, 홀수=우반부)이므로 짝수 코드만 배정한다.
- 인쇄 가능 코드는 (code & 0x20) == 0 이라 0x40 블록마다 앞 32개만 쓴다.
  그중 짝수 16개가 전각 슬롯이 된다.
- 보존 구간: ASCII 가변폭(0x0040-0x00DF), 가나(0x0140-0x029F),
  기호·버튼 아이콘(0x02C0-0x031F), 고정폭 ASCII(0x0400-0x041F).
- 한글 배정 구간: 0x0440 이상의 인쇄 가능 짝수 코드.
  기존 한자 글리프를 덮어쓰지만 lang0/lang1 텍스트를 전량 한국어로 교체하므로
  해당 한자는 더 이상 소비되지 않는다.

배정표는 파일로 고정해 재현 가능하게 하고, 한 번 배정된 글자의 코드는 바꾸지 않는다
(코드가 바뀌면 이미 적용된 번역의 의미가 달라진다).
"""
import json
from pathlib import Path

ALLOC_START = 0x0440
ALLOC_END = 0x1600


def is_printable(code: int) -> bool:
    return (code & 0x20) == 0


def slot_iter(start: int = ALLOC_START, end: int = ALLOC_END):
    """전각 좌반부로 쓸 수 있는 짝수 코드를 순서대로 낸다."""
    c = start
    while c < end:
        if is_printable(c) and is_printable(c + 1) and c % 2 == 0:
            yield c
        c += 2


def capacity(start: int = ALLOC_START, end: int = ALLOC_END) -> int:
    return sum(1 for _ in slot_iter(start, end))


class Allocation:
    def __init__(self, path: Path):
        self.path = path
        self.char_to_code: dict[str, int] = {}
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.char_to_code = {k: int(v, 16) if isinstance(v, str) else v
                                 for k, v in data["chars"].items()}

    @property
    def code_to_char(self) -> dict[int, str]:
        return {v: k for k, v in self.char_to_code.items()}

    def assign(self, chars: list[str]) -> list[str]:
        """새 글자를 배정한다. 기존 배정은 유지. 반환은 새로 배정된 글자."""
        used = set(self.char_to_code.values())
        free = (c for c in slot_iter() if c not in used)
        added = []
        for ch in chars:
            if ch in self.char_to_code:
                continue
            try:
                code = next(free)
            except StopIteration:
                raise RuntimeError(
                    f"한글 슬롯 부족: 용량 {capacity()}자, 요청 {len(self.char_to_code) + 1}자")
            self.char_to_code[ch] = code
            added.append(ch)
        return added

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = dict(sorted(self.char_to_code.items(), key=lambda kv: kv[1]))
        self.path.write_text(json.dumps({
            "schema_version": 1,
            "note": "글자->전각 좌반부 코드. 우반부는 code+1. 한 번 배정된 코드는 바꾸지 않는다.",
            "range": {"start": f"0x{ALLOC_START:04X}", "end": f"0x{ALLOC_END:04X}",
                      "capacity": capacity()},
            "count": len(ordered),
            "chars": {k: f"0x{v:04X}" for k, v in ordered.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    print(f"배정 가능 슬롯: {capacity()}자 "
          f"(0x{ALLOC_START:04X}-0x{ALLOC_END:04X}, 전각 코드 쌍)")
