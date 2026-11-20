"""Adaptação do texto para fala (antes do TTS).

Transforma a resposta do LLM em algo que soa natural quando lido em voz alta:
  * remove markdown, emojis, links e listas;
  * expande siglas e abreviações ("SP156", "SMS", "Av.", "nº", "m³");
  * escreve por extenso datas, horas, dinheiro, porcentagens, ordinais e números;
  * lê telefones e códigos longos dígito a dígito ("0800 779 0156");
  * quebra frases longas para o TTS respirar.
"""
from __future__ import annotations

import re
import unicodedata

from num2words import num2words

LANG = "pt_BR"

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
DIGITOS = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]

# Siglas lidas letra a letra ou com pronúncia própria. A ordem importa.
SIGLAS = [
    (r"\bSP\s?156\b", "esse pê cento e cinquenta e seis"),
    (r"\bSMS\b", "esse eme esse"),
    (r"\bLGPD\b", "éle gê pê dê"),
    (r"\bCPF\b", "cê pê éfe"),
    (r"\bRG\b", "érre gê"),
    (r"\bCEP\b", "cep"),
    (r"\bCET\b", "cê ê tê"),
    (r"\bGCM\b", "gê cê eme"),
    (r"\bUBS\b", "u bê esse"),
    (r"\bSAMU\b", "Samu"),
    (r"\bENEL\b", "Enel"),
    (r"\bSABESP\b", "Sabesp"),
    (r"\bSP\b", "São Paulo"),
    (r"\bIA\b", "inteligência artificial"),
]

ABREVIACOES = [
    (r"\bAv\.\s?", "avenida "),
    (r"\bR\.\s(?=[A-ZÁÉÍÓÚ])", "rua "),
    (r"\bn(?:º|°|\.)\s?(?=\d)", "número "),
    (r"\betc\.?", "etcétera"),
    (r"\bp/\s?", "para "),
    (r"\bc/\s?", "com "),
    (r"\bDr\.\s?", "doutor "),
    (r"\bSra\.\s?", "senhora "),
    (r"\bSr\.\s?", "senhor "),
    (r"\bkm/h\b", "quilômetros por hora"),
    (r"\b1\s?m³", "um metro cúbico"),
    (r"(?<=\d)\s?m³", " metros cúbicos"),
    (r"\bm³", "metros cúbicos"),
    (r"(?<=\d)\s?km\b", " quilômetros"),
    (r"(?<=\d)\s?kg\b", " quilos"),
    (r"(?<=\d)\s?mm\b", " milímetros"),
]

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF‍️⌀-⏿⬀-⯿]+"
)


def _n(value: int | float, to: str = "cardinal") -> str:
    return num2words(value, lang=LANG, to=to)


def digits(seq: str) -> str:
    return " ".join(DIGITOS[int(d)] for d in seq if d.isdigit())


def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "o site da Prefeitura", text)
    text = re.sub(r"\bwww\.\S+", "o site da Prefeitura", text)
    text = re.sub(r"\b[\w-]+(?:\.[\w-]+)*\.(?:gov|com|org)(?:\.br)?(?:/\S*)?", "o site da Prefeitura", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"(\*\*|__|\*|_|~~)(.+?)\1", r"\2", text)
    text = text.replace("|", " ").replace(">", " ")
    return text


def remove_emojis(text: str) -> str:
    return _EMOJI.sub("", text)


def _date(m: re.Match) -> str:
    d, mth, y = int(m.group(1)), int(m.group(2)), m.group(3)
    if not (1 <= d <= 31 and 1 <= mth <= 12):
        return m.group(0)
    dia = "primeiro" if d == 1 else _n(d)
    out = f"{dia} de {MESES[mth - 1]}"
    if y:
        yy = int(y)
        yy = yy + 2000 if yy < 100 else yy
        out += f" de {_n(yy)}"
    return out


def _time(m: re.Match) -> str:
    h = int(m.group(1))
    mins = int(m.group(3)) if m.group(3) else 0
    if m.group(2) == "h" and not m.group(3):
        return "uma hora" if h == 1 else ("duas horas" if h == 2 else f"{_n(h)} horas")
    if h > 23 or mins > 59:
        return m.group(0)
    hora = "uma hora" if h == 1 else ("meia-noite" if h == 0 else f"{_n(h)} horas")
    if h == 2:
        hora = "duas horas"
    if mins:
        hora += f" e {_n(mins)}"
    return hora


def _money(m: re.Match) -> str:
    inteiro = int(m.group(1).replace(".", ""))
    cent = int(m.group(2)) if m.group(2) else 0
    out = f"{_n(inteiro)} {'real' if inteiro == 1 else 'reais'}"
    if cent:
        out += f" e {_n(cent)} {'centavo' if cent == 1 else 'centavos'}"
    return out


def _ordinal(m: re.Match) -> str:
    words = _n(int(m.group(1)), "ordinal").split()
    if m.group(2) == "ª":
        words = [w[:-1] + "a" if w.endswith("o") else w for w in words]
    return " ".join(words)


def _phone(m: re.Match) -> str:
    groups = re.findall(r"\d+", m.group(0))
    out = []
    for g in groups:
        if g == "0800":
            out.append("zero oitocentos")
        elif len(g) == 2:  # DDD é lido como número: "onze"
            out.append(_n(int(g)))
        else:
            out.append(digits(g))
    return ", ".join(out)


def _number(m: re.Match) -> str:
    raw = m.group(0)
    if "," in raw:
        inteiro, dec = raw.split(",", 1)
        return f"{_n(int(inteiro.replace('.', '')))} vírgula {' '.join(_n(int(c)) for c in dec) if dec.startswith('0') else _n(int(dec))}"
    clean = raw.replace(".", "")
    # Sequências longas sem separador de milhar são códigos ou telefones: dígito a dígito.
    if "." not in raw and len(clean) >= 5:
        return digits(clean)
    return _n(int(clean))


def normalize_numbers(text: str) -> str:
    # Telefones: 0800 779 0156, (11) 3230-5156, 0800-011-0156
    text = re.sub(r"\b0800(?:[\s-]\d{2,4}){2,3}\b", _phone, text)
    text = re.sub(r"\(?\b\d{2}\)?\s\d{4,5}-\d{4}\b", _phone, text)
    text = re.sub(r"\b\d{4,5}-\d{4}\b", _phone, text)
    # Datas e horas
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", _date, text)
    text = re.sub(r"\b(\d{1,2})([h:])(\d{2})?(?:min)?\b", _time, text)
    # Dinheiro e porcentagem
    text = re.sub(r"R\$\s?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?", _money, text)
    text = re.sub(r"(\d+(?:,\d+)?)\s?%", lambda m: f"{m.group(1)} por cento", text)
    # Ordinais: 1º, 2ª
    text = re.sub(r"\b(\d+)\s?([ºª])", _ordinal, text)
    # Demais números (com milhar ou decimal)
    text = re.sub(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b|\b\d+(?:,\d+)?\b", _number, text)
    return text


def expand_abbreviations(text: str) -> str:
    for pat, rep in ABREVIACOES:
        text = re.sub(pat, rep, text)
    for pat, rep in SIGLAS:
        text = re.sub(pat, rep, text)
    return text


def split_long_sentences(text: str, max_words: int = 32) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for s in sentences:
        words = s.split()
        if len(words) <= max_words:
            out.append(s)
            continue
        # Quebra em vírgulas ou conectivos para o TTS respirar.
        parts = re.split(r",\s+|;\s+|\s+(?=e depois|mas |porém )", s)
        buf: list[str] = []
        for p in parts:
            buf.append(p)
            if len(" ".join(buf).split()) >= max_words // 2:
                chunk = ", ".join(buf).rstrip(".") + "."
                out.append(chunk[:1].upper() + chunk[1:])
                buf = []
        if buf:
            chunk = ", ".join(buf)
            out.append(chunk[:1].upper() + chunk[1:])
    return " ".join(out)


def adapt_for_speech(text: str, max_chars: int = 600) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = strip_markdown(text)
    text = remove_emojis(text)
    text = expand_abbreviations(text)
    text = normalize_numbers(text)
    text = re.sub(r"\s*\n+\s*", ". ", text)
    text = re.sub(r"\s*[:;]\s*", ", ", text)
    text = re.sub(r"[()\[\]{}\"“”]", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\.\s*\.", ".", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\bem o site\b", "no site", text)
    text = re.sub(r"\bde o site\b", "do site", text)
    text = split_long_sentences(text)
    if len(text) > max_chars:
        cut = text[:max_chars]
        last = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        text = cut[: last + 1] if last > 0 else cut
    if text and text[-1] not in ".!?":
        text += "."
    return text
