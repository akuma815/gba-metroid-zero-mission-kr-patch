"""코드 배열 <-> 사람이 편집 가능한 토큰 문자열 (전단사).

토큰 정책 (제어코드 의미는 실증 확정, workspace/analysis/POC.md CTRL 절):
  {x:NN}   0x80NN  줄 시작 X 좌표   -- 번역 시 재계산 대상 (layout.py)
  {c:NN}   0x81NN  색상 팔레트 인덱스 -- 순서·값 보존
  {xm:NN}  0x83NN  줄 중간 X 재설정  -- 순서 보존, 좌표는 재검토 대상
  {br}     0xFE00  줄바꿈
  {end}    0xFF00  메시지 종료
  {u:XXXX} 매핑 없는 코드 (한자·아이콘 등) -- 경계와 폭이 확정돼 원시 보존이 안전
  {lb} {rb}  리터럴 '{' '}' 이스케이프

전단사 보장: encode(decode(codes)) == codes 를 전 코퍼스에서 검증한다
(workspace/tests/test_tokens.py).
"""
import re

from charmap import ascii_to_code, decode_code, encode_char

CTRL_X_LINE = 0x80
CTRL_COLOR = 0x81
CTRL_X_MID = 0x83
NEWLINE = 0xFE00
TERMINATOR = 0xFF00

_TOKEN_RE = re.compile(r"\{(x|c|xm|u):([0-9A-Fa-f]+)\}|\{(br|end|lb|rb)\}")


def codes_to_text(codes: list[int]) -> str:
    """코드 배열을 토큰 문자열로. 종료자도 {end} 로 명시 보존한다."""
    out = []
    for w in codes:
        if w == TERMINATOR:
            out.append("{end}")
            continue
        if w == NEWLINE:
            out.append("{br}")
            continue
        hb = w >> 8
        if hb == CTRL_X_LINE:
            out.append("{x:%02X}" % (w & 0xFF))
            continue
        if hb == CTRL_COLOR:
            out.append("{c:%02X}" % (w & 0xFF))
            continue
        if hb == CTRL_X_MID:
            out.append("{xm:%02X}" % (w & 0xFF))
            continue
        ch = decode_code(w)
        if ch is None:
            out.append("{u:%04X}" % w)
            continue
        if ch == "{":
            out.append("{lb}")
        elif ch == "}":
            out.append("{rb}")
        else:
            out.append(ch)
    return "".join(out)


def text_to_codes(text: str) -> list[int]:
    """토큰 문자열을 코드 배열로. 매핑 불가 문자는 ValueError."""
    codes: list[int] = []
    i = 0
    while i < len(text):
        m = _TOKEN_RE.match(text, i)
        if m:
            kind, val, simple = m.group(1), m.group(2), m.group(3)
            if simple == "br":
                codes.append(NEWLINE)
            elif simple == "end":
                codes.append(TERMINATOR)
            elif simple == "lb":
                codes.append(ascii_to_code("{"))
            elif simple == "rb":
                codes.append(ascii_to_code("}"))
            elif kind == "x":
                codes.append((CTRL_X_LINE << 8) | int(val, 16))
            elif kind == "c":
                codes.append((CTRL_COLOR << 8) | int(val, 16))
            elif kind == "xm":
                codes.append((CTRL_X_MID << 8) | int(val, 16))
            elif kind == "u":
                codes.append(int(val, 16))
            i = m.end()
            continue

        ch = text[i]
        if ch == "\n":
            codes.append(NEWLINE)
            i += 1
            continue
        c = encode_char(ch)
        if c is None:
            raise ValueError(f"매핑 없는 문자 {ch!r} (U+{ord(ch):04X}) at {i}")
        codes.append(c)
        i += 1
    return codes


def strip_controls(text: str) -> str:
    """표시 문자만 남긴다(길이·가독 확인용)."""
    return _TOKEN_RE.sub(lambda m: "" if m.group(3) not in ("lb", "rb")
                         else ("{" if m.group(3) == "lb" else "}"), text)
