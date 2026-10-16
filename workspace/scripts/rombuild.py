"""ROM 빌드 공통 모듈 — 불변 원본에서 시작하는 Expected Write 빌더.

규칙:
- 원본 ROM은 SHA-256으로 지원 리비전을 확인한 뒤에만 읽는다.
- 모든 변경은 (offset, expected_original_bytes, new_bytes) 3요소를 갖는다.
  expected가 원본과 다르면 실패한다.
- 같은 바이트에 두 writer가 겹치면 실패한다.
- 빌드 끝에 원본 대비 실제 차이가 선언된 변경 범위와 정확히 일치하는지 확인한다.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SOURCE_ROM = PROJECT / "original" / "Metroid - Zero Mission (Japan).gba"
SOURCE_SHA256 = "d087ca6e2d1808109a579c2283e944d81c8426d37de564f99ea9273087c2172a"
ROM_SIZE = 8388608


class BuildError(Exception):
    pass


def load_source(path: Path = SOURCE_ROM) -> bytes:
    if not path.is_file():
        raise BuildError(f"원본 ROM 없음: {path}")
    data = path.read_bytes()
    if len(data) != ROM_SIZE:
        raise BuildError(f"크기 불일치: {len(data)} != {ROM_SIZE}")
    got = hashlib.sha256(data).hexdigest()
    if got != SOURCE_SHA256:
        raise BuildError(f"지원하지 않는 리비전 SHA-256={got}")
    return data


class RomBuilder:
    def __init__(self, source: bytes | None = None):
        self.source = bytes(load_source() if source is None else source)
        self.buf = bytearray(self.source)
        self._writers: dict[int, str] = {}
        self.changes: list[tuple[int, int, str]] = []

    def write(self, offset: int, new: bytes, expected: bytes | None = None, who: str = "?"):
        """offset에 new를 쓴다. expected가 주어지면 원본 바이트와 대조한다."""
        end = offset + len(new)
        if offset < 0 or end > ROM_SIZE:
            raise BuildError(f"[{who}] 범위 초과 0x{offset:X}+{len(new)}")
        if expected is not None:
            actual = self.source[offset:end]
            if actual != expected:
                raise BuildError(
                    f"[{who}] Expected Write 불일치 @0x{offset:X}\n"
                    f"  기대: {expected.hex()}\n  실제: {actual.hex()}"
                )
        for i in range(offset, end):
            prev = self._writers.get(i)
            if prev is not None and prev != who:
                raise BuildError(f"writer 충돌 @0x{i:X}: {prev} vs {who}")
            self._writers[i] = who
        self.buf[offset:end] = new
        self.changes.append((offset, len(new), who))

    def verify(self):
        """선언되지 않은 차이가 없는지 확인한다."""
        declared = set(self._writers)
        undeclared = [
            i for i in range(ROM_SIZE)
            if self.buf[i] != self.source[i] and i not in declared
        ]
        if undeclared:
            raise BuildError(f"미선언 차이 {len(undeclared)}바이트, 최초 0x{undeclared[0]:X}")
        return True

    def save(self, path: Path) -> Path:
        self.verify()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(self.buf))
        return path

    def summary(self) -> str:
        changed = sum(1 for i in self._writers if self.buf[i] != self.source[i])
        lines = [f"변경 선언 {len(self.changes)}건, 실제 변경 {changed}바이트"]
        for off, n, who in self.changes:
            lines.append(f"  0x{off:06X} +{n:<6d} {who}")
        lines.append("SHA-256: " + hashlib.sha256(bytes(self.buf)).hexdigest())
        return "\n".join(lines)


# --- 폰트 헬퍼 (workspace/analysis/text_map.json 의 확정 구조) ---

FONT_BASE = 0x4154BC
FONT_BOTTOM_DELTA = 0x400


def glyph_offsets(code: int) -> tuple[int, int]:
    """코드의 (상단 타일, 하단 타일) ROM 오프셋."""
    if code & 0x20:
        raise BuildError(f"인쇄 불가 코드 0x{code:04X} ((code & 0x20) != 0)")
    top = FONT_BASE + code * 32
    return top, top + FONT_BOTTOM_DELTA
