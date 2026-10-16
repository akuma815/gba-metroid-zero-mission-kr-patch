"""GBA BIOS LZ77 (형식 0x10) 해제·압축.

헤더 4바이트: [0x10][해제크기 24bit LE]
이후 블록: 플래그 1바이트(비트7부터), 비트=0 이면 리터럴 1바이트,
비트=1 이면 2바이트 참조 (상위 4비트 = 길이-3, 나머지 12비트 = 거리-1).
"""
import struct


class Lz77Error(Exception):
    pass


def decompress(data: bytes, offset: int = 0) -> bytes:
    if data[offset] != 0x10:
        raise Lz77Error(f"LZ77 헤더 아님: 0x{data[offset]:02X} @0x{offset:X}")
    size = struct.unpack_from("<I", data, offset)[0] >> 8
    out = bytearray()
    p = offset + 4
    while len(out) < size:
        flags = data[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                b0, b1 = data[p], data[p + 1]
                p += 2
                length = (b0 >> 4) + 3
                dist = (((b0 & 0xF) << 8) | b1) + 1
                if dist > len(out):
                    raise Lz77Error(f"거리 초과 {dist} > {len(out)}")
                start = len(out) - dist
                for i in range(length):
                    out.append(out[start + i])
            else:
                out.append(data[p])
                p += 1
    return bytes(out[:size]), p - offset


MIN_DISTANCE = 2
MAX_LEN = 18
WINDOW = 0x1000


def _matches(data: bytes, min_dist: int) -> list[tuple[int, int]]:
    """위치마다 (최장 일치 길이, 그 거리)."""
    n = len(data)
    out = []
    for pos in range(n):
        best_len, best_dist = 0, 0
        lo = max(0, pos - WINDOW)
        for start in range(pos - min_dist, lo - 1, -1):
            ln = 0
            while (ln < MAX_LEN and pos + ln < n
                   and data[start + ln] == data[pos + ln]):
                ln += 1
            if ln > best_len:
                best_len, best_dist = ln, pos - start
                if ln == MAX_LEN:
                    break
        out.append((best_len, best_dist))
    return out


def compress(data: bytes, vram_safe: bool = True, optimal: bool = False) -> bytes:
    """LZ77 압축.

    vram_safe=True 면 거리 1 참조를 만들지 않는다. GBA BIOS 의 VRAM 대상 해제
    루틴은 16비트 단위로 쓰기 때문에 직전 바이트(거리 1)를 참조하면 아직 기록되지
    않은 값을 읽어 결과가 달라진다. 자체 해제기로는 왕복이 통과해도 게임에서는
    깨지므로 기본값으로 막는다(메뉴 그래픽 교체에서 실제로 겪은 문제).

    optimal=True 면 탐욕 대신 최소 비용 경로를 고른다(리터럴 9비트 / 참조 17비트).
    최장 일치를 무조건 쓰면 다음 위치의 더 긴 일치를 놓쳐 손해가 날 때가 있다.
    원본 압축 크기 안에 못 들어갈 때 쓴다.

    원본과 바이트 동일 재현은 보장하지 않는다. 사용 전 실제 소비자(게임 화면)로
    확인해야 하며, 자체 왕복만으로는 호환성을 증명하지 못한다.
    """
    min_dist = MIN_DISTANCE if vram_safe else 1
    n = len(data)
    m = _matches(data, min_dist)
    out = bytearray(struct.pack("<I", (n << 8) | 0x10))

    if optimal:
        INF = 1 << 30
        cost = [INF] * (n + 1)
        take = [0] * (n + 1)          # 0=리터럴, >0=참조 길이
        cost[n] = 0
        for i in range(n - 1, -1, -1):
            best, sel = 9 + cost[i + 1], 0
            ml = min(m[i][0], n - i)
            for ln in range(3, ml + 1):
                c = 17 + cost[i + ln]
                if c < best:
                    best, sel = c, ln
            cost[i], take[i] = best, sel
        plan = []
        i = 0
        while i < n:
            ln = take[i]
            plan.append((ln, m[i][1]) if ln else (0, 0))
            i += ln if ln else 1
    else:
        plan = []
        i = 0
        while i < n:
            ln, dist = m[i]
            if ln >= 3:
                plan.append((ln, dist))
                i += ln
            else:
                plan.append((0, 0))
                i += 1

    src = 0
    for k in range(0, len(plan), 8):
        flags_at = len(out)
        out.append(0)
        flags = 0
        for bit, (ln, dist) in enumerate(plan[k:k + 8]):
            if ln:
                flags |= 0x80 >> bit
                out.append(((ln - 3) << 4) | (((dist - 1) >> 8) & 0xF))
                out.append((dist - 1) & 0xFF)
                src += ln
            else:
                out.append(data[src])
                src += 1
        out[flags_at] = flags
    return bytes(out)
