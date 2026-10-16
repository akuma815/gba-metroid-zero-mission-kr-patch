"""코드 <-> 문자 매핑.

폰트는 0x40 코드 블록마다 앞 32슬롯만 인쇄에 쓴다((code & 0x20) == 0).
그 결과 ASCII 는 5비트 단위로 블록에 흩어져 배치된다.

  code = (ascii & 0x1F) | ((ascii >> 5) << 6)
  ascii = (code & 0x1F) | ((code >> 6) << 5)

근거: workspace/font/ascii_sheet.png 육안 확인 + 런타임 일치
  (M=0x008D, MISSILE TANK / '('=0x0048, '1'=0x0051).

가나는 0x0140 부터 블록 단위로 배열된다. 아래 표는 폰트 시트 판독으로 만들었고
런타임 추적으로 일부가 교차 검증됐다(0x0150=ー, 0x0152=イ, 0x015D=ス,
0x0184=ト, 0x018F=マ, 0x0192=メ, 0x019A=レ, 0x019B=ロ, 0x01C4=ド).
한자는 코드 쌍(짝수=좌반부)이며 매핑이 아직 없다 -> 원시 토큰으로 남긴다.
"""

TERMINATOR = 0xFF00
NEWLINE = 0xFE00


def is_printable_code(code: int) -> bool:
    return (code & 0x20) == 0


def ascii_to_code(ch: str) -> int | None:
    a = ord(ch)
    if not 0x20 <= a <= 0x7F:
        return None
    return (a & 0x1F) | ((a >> 5) << 6)


def code_to_ascii(code: int) -> str | None:
    """가변폭 ASCII 계열 코드(0x0040-0x00DF)를 문자로 되돌린다."""
    if not is_printable_code(code):
        return None
    if not 0x0040 <= code <= 0x00DF:
        return None
    a = (code & 0x1F) | ((code >> 6) << 5)
    if 0x20 <= a <= 0x7E:
        return chr(a)
    return None


# --- 고정폭 ASCII 세트 (0x0400-0x041F) ------------------------------------
# 0x40 블록과 자형은 거의 같지만 폭이 8px 고정이다(0x40 블록은 4~8px 가변).
# 일본어 본문에서 숫자·기호 정렬에 쓰이며 0x0400(공백)이 본문 최빈 코드다.
# 구분을 위해 전각 유니코드로 표기한다. 근거: work/check_400_width.py
MONO_BASE = 0x0400


def code_to_mono(code: int) -> str | None:
    if not MONO_BASE <= code <= MONO_BASE + 0x1F:
        return None
    a = 0x20 + (code & 0x1F)
    return "　" if a == 0x20 else chr(0xFF00 + (a - 0x20))


def mono_to_code(ch: str) -> int | None:
    o = ord(ch)
    if o == 0x3000:
        return MONO_BASE
    if 0xFF01 <= o <= 0xFF1F:
        return MONO_BASE + (o - 0xFF00)
    return None


# --- 가나 ---------------------------------------------------------------
# 블록 시작 코드 -> 32칸 배열. 빈 칸은 None.
# 히라가나(0x0200/0x0240/0x0280) 블록은 가타카나(0x0140/0x0180/0x01C0)와 같은 상대 배치를 갖는다.
# 근거: workspace/font/kana_sheet.png, dakuten_sheet.png, hira_sheet.png
_KANA_BLOCKS: dict[int, list[str | None]] = {
    0x0140: [
        None, "・", "「", "」", "、", "゛", "゜", "ァ", "ィ", "ゥ", "ェ", "ォ",
        "ャ", "ュ", "ョ", "ッ", "ー", "ア", "イ", "ウ", "エ", "オ", "カ", "キ",
        "ク", "ケ", "コ", "サ", "シ", "ス", "セ", "ソ",
    ],
    0x0180: [
        "タ", "チ", "ツ", "テ", "ト", "ナ", "ニ", "ヌ", "ネ", "ノ", "ハ", "ヒ",
        "フ", "ヘ", "ホ", "マ", "ミ", "ム", "メ", "モ", "ヤ", "ユ", "ヨ", "ラ",
        "リ", "ル", "レ", "ロ", "ワ", "ン", None, None,
    ],
    # 탁음·반탁음 가타카나: タ행(5) / 공백5 / ハ행 탁음·반탁음(10) / 공백2 / カ행·サ행 탁음(10)
    0x01C0: [
        "ダ", "ヂ", "ヅ", "デ", "ド", None, None, None, None, None,
        "バ", "ビ", "ブ", "ベ", "ボ", "パ", "ピ", "プ", "ペ", "ポ", None, None,
        "ガ", "ギ", "グ", "ゲ", "ゴ", "ザ", "ジ", "ズ", "ゼ", "ゾ",
    ],
    0x0200: [
        None, None, None, None, None, None, "を", "ぁ", "ぃ", "ぅ", "ぇ", "ぉ",
        "ゃ", "ゅ", "ょ", "っ", None, "あ", "い", "う", "え", "お", "か", "き",
        "く", "け", "こ", "さ", "し", "す", "せ", "そ",
    ],
    0x0240: [
        "た", "ち", "つ", "て", "と", "な", "に", "ぬ", "ね", "の", "は", "ひ",
        "ふ", "へ", "ほ", "ま", "み", "む", "め", "も", "や", "ゆ", "よ", "ら",
        "り", "る", "れ", "ろ", "わ", "ん", None, None,
    ],
    0x0280: [
        "だ", "ぢ", "づ", "で", "ど", None, None, None, None, None,
        "ば", "び", "ぶ", "べ", "ぼ", "ぱ", "ぴ", "ぷ", "ぺ", "ぽ", None, None,
        "が", "ぎ", "ぐ", "げ", "ご", "ざ", "じ", "ず", "ぜ", "ぞ",
    ],
}

CODE_TO_KANA: dict[int, str] = {}
for _base, _row in _KANA_BLOCKS.items():
    for _i, _ch in enumerate(_row):
        if _ch is not None:
            CODE_TO_KANA[_base + _i] = _ch

KANA_TO_CODE = {v: k for k, v in CODE_TO_KANA.items()}


# --- 한글 (번역으로 배정된 전각 코드) --------------------------------------
# 배정표는 workspace/text/translation/hangul_codes.json 이 소유한다.
# 순환 import 를 피하려고 지연 로딩한다.
_HANGUL_CACHE: dict | None = None


def _hangul_maps():
    global _HANGUL_CACHE
    if _HANGUL_CACHE is None:
        from pathlib import Path

        from hangul_alloc import Allocation

        p = Path(__file__).resolve().parents[1] / "text" / "translation" / "hangul_codes.json"
        alloc = Allocation(p)
        _HANGUL_CACHE = {"c2h": alloc.code_to_char, "h2c": alloc.char_to_code}
    return _HANGUL_CACHE


def reload_hangul():
    """배정표를 다시 읽는다(배정 직후 호출)."""
    global _HANGUL_CACHE
    _HANGUL_CACHE = None


def decode_code(code: int) -> str | None:
    """단일 코드를 문자로. 매핑이 없으면 None."""
    ch = code_to_ascii(code)
    if ch is not None:
        return ch
    ch = code_to_mono(code)
    if ch is not None:
        return ch
    ch = CODE_TO_KANA.get(code)
    if ch is not None:
        return ch
    return _hangul_maps()["c2h"].get(code)


def encode_char(ch: str) -> int | None:
    """문자를 코드로. 매핑이 없으면 None."""
    c = ascii_to_code(ch) if ch.isascii() else None
    if c is not None:
        return c
    c = mono_to_code(ch)
    if c is not None:
        return c
    c = KANA_TO_CODE.get(ch)
    if c is not None:
        return c
    return _hangul_maps()["h2c"].get(ch)


def decode_stream(codes: list[int], raw_fmt="<{:04X}>") -> str:
    """코드 배열을 사람이 읽는 문자열로. 미매핑 코드는 원시 토큰으로 남긴다."""
    out = []
    for w in codes:
        if w == TERMINATOR:
            break
        if w == NEWLINE:
            out.append("\n")
            continue
        if (w >> 8) in (0x80, 0x81, 0x83):
            out.append(raw_fmt.format(w))
            continue
        ch = decode_code(w)
        out.append(ch if ch is not None else raw_fmt.format(w))
    return "".join(out)
