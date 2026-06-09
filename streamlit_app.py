import re
import math
import random
import sqlite3
from io import BytesIO
from datetime import datetime

import fitz
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="股票報表系統", layout="wide", initial_sidebar_state="expanded")

DB_PATH = "stock_data.db"


def apply_app_style():
    st.markdown(
        """
        <style>
        :root {
            --app-text: #262b3a;
            --app-muted: #667085;
            --app-accent: #ff4b4b;
            --app-line: #e7e7ec;
            --app-info-bg: #eaf3ff;
            --app-info-text: #0054b8;
        }

        .stApp {
            background: #ffffff;
            color: var(--app-text);
        }

        section.main > div.block-container {
            max-width: 1360px;
            padding-top: 3.1rem;
            padding-left: 2.6rem;
            padding-right: 2.6rem;
            padding-bottom: 4rem;
        }

        h1 {
            color: var(--app-text);
            font-size: 3.15rem !important;
            line-height: 1.15 !important;
            font-weight: 800 !important;
            letter-spacing: 0 !important;
            margin-bottom: 1.7rem !important;
        }

        h2, h3 {
            color: var(--app-text);
            font-weight: 800 !important;
            letter-spacing: 0 !important;
        }

        h2 {
            font-size: 2.15rem !important;
            margin-top: 1.7rem !important;
        }

        h3 {
            font-size: 1.95rem !important;
        }

        [data-testid="stMetric"] {
            padding: 0;
        }

        [data-testid="stMetricLabel"] {
            color: var(--app-text);
            font-size: 1rem;
            font-weight: 500;
        }

        [data-testid="stMetricValue"] {
            color: var(--app-text);
            font-size: 2.45rem;
            line-height: 1.25;
            letter-spacing: 0;
        }

        [data-testid="stMetricDelta"] {
            color: var(--app-muted);
            font-size: 0.95rem;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.85rem;
            border-bottom: 2px solid var(--app-line);
            margin-top: 1.4rem;
        }

        button[data-baseweb="tab"] {
            padding: 0 0 0.8rem 0;
            color: var(--app-text);
            font-size: 1rem;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--app-accent);
            border-bottom: 3px solid var(--app-accent);
        }

        button[kind="primary"], div.stButton > button[kind="primary"] {
            background: var(--app-accent);
            border: 1px solid var(--app-accent);
            color: #ffffff;
            border-radius: 9px;
            font-weight: 700;
        }

        div.stButton > button {
            min-height: 2.7rem;
            border-radius: 9px;
        }

        [data-testid="stAlert"] {
            background: var(--app-info-bg);
            color: var(--app-info-text);
            border: 0;
            border-radius: 9px;
            padding: 1rem 1.15rem;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--app-line);
            border-radius: 9px;
            overflow: hidden;
        }

        [data-testid="stSidebar"] {
            background: #fbfbfd;
            border-right: 1px solid var(--app-line);
        }

        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            font-size: 1.05rem !important;
            margin-top: 1rem !important;
            margin-bottom: 0.45rem !important;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {
            color: var(--app-text);
        }

        [data-testid="stSidebar"] .stRadio {
            margin-bottom: 1.2rem;
        }

        [data-testid="stFileUploader"] section {
            border: 1px dashed #d4d9e4;
            border-radius: 9px;
            background: #fbfcff;
        }

        .stCaptionContainer, [data-testid="stCaptionContainer"] {
            color: var(--app-muted);
        }

        @media (max-width: 900px) {
            section.main > div.block-container {
                padding-left: 1.3rem;
                padding-right: 1.3rem;
                padding-top: 2rem;
            }

            h1 {
                font-size: 2.45rem !important;
            }

            [data-testid="stMetricValue"] {
                font-size: 2rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_app_style()

BROKERS = [
    "元大投顧", "元大證券", "凱基投顧", "凱基證券", "富邦投顧", "富邦證券",
    "永豐投顧", "永豐金證券", "國泰證券", "國泰投顧", "群益投顧", "群益證券",
    "統一投顧", "統一證券", "兆豐投顧", "兆豐證券", "第一金投顧", "第一金證券",
    "玉山投顧", "玉山證券", "台新投顧", "台新證券", "中信投顧", "中國信託證券",
    "華南投顧", "華南證券", "華南永昌", "華南永昌投顧", "華南永昌證券",
    "元富投顧", "元富證券", "日盛投顧", "日盛證券",
    "康和證券", "宏遠投顧", "宏遠證券", "新光投顧", "新光證券", "國票投顧",
    "國票證券", "台中銀證券", "上海商銀證券", "合庫證券", "摩根大通", "摩根士丹利",
    "高盛", "野村", "花旗", "瑞銀", "匯豐", "麥格理", "美銀", "美林", "里昂", "大和",
    "J.P. Morgan", "JP Morgan", "Morgan Stanley", "Goldman Sachs", "Nomura",
    "Citi", "Citigroup", "UBS", "HSBC", "CLSA", "Daiwa", "Macquarie",
    "BofA", "Bank of America", "Merrill Lynch",
]

BROKER_ALIASES = {
    "元大": "元大",
    "凱基": "凱基",
    "富邦": "富邦",
    "永豐": "永豐",
    "國泰": "國泰",
    "群益": "群益",
    "統一": "統一",
    "兆豐": "兆豐",
    "玉山": "玉山",
    "台新": "台新",
    "中信": "中信",
    "中國信託": "中國信託",
    "華南投顧": "華南投顧",
    "華南證券": "華南證券",
    "華南永昌": "華南永昌",
    "元富": "元富",
    "國票": "國票",
    "宏遠": "宏遠",
    "新光": "新光",
    "合庫": "合庫",
    "康和": "康和",
    "日盛": "日盛",
}

RATING_TERMS = [
    "買進", "加碼", "增持", "推薦", "優於大盤", "持有", "中立", "觀望", "減碼", "賣出", "不推薦", "劣於大盤",
    "Buy", "Hold", "Neutral", "Sell", "Overweight", "Equal-weight", "Equal Weight", "Underweight",
    "Outperform", "Market Perform", "Underperform", "Not Rated", "NR", "OW", "EW", "UW",
]

RATING_MAP = {
    "buy": "Buy",
    "hold": "Hold",
    "neutral": "Neutral",
    "sell": "Sell",
    "overweight": "Overweight",
    "equal-weight": "Equal-weight",
    "equal weight": "Equal-weight",
    "underweight": "Underweight",
    "outperform": "Outperform",
    "market perform": "Market Perform",
    "underperform": "Underperform",
    "not rated": "Not Rated",
    "nr": "Not Rated",
    "ow": "Overweight",
    "ew": "Equal-weight",
    "uw": "Underweight",
}

BAD_STOCK_CONTEXT = [
    "電話", "地址", "傳真", "email", "e-mail", "著作權", "免責", "聲明", "服務據點",
    "phone", "tel", "fax", "analyst", "account", "research account", "copyright", "disclaimer",
]


def init_state():
    st.session_state.setdefault("rows", [])
    st.session_state.setdefault("processed_files", set())
    st.session_state.setdefault("pending", [])
    st.session_state.setdefault("sort_desc", True)


def extract_pdf_text(uploaded_file):
    data = uploaded_file.read()
    uploaded_file.seek(0)
    doc = fitz.open(stream=BytesIO(data), filetype="pdf")
    parts = []
    for page_index in range(min(len(doc), 5)):
        parts.append(doc[page_index].get_text())
    return "\n".join(parts)[:12000]


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def number(value):
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def format_num(value):
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def extract_stock_code(text):
    patterns = [
        r"\((\d{4})\s*\.\s*(?:TW|TWO|TT)\)",
        r"\b(\d{4})\s*(?:TW|TWO|TT)\b",
        r"(?:股票代號|證券代號|代號|Ticker|Stock\s*Code)\s*[:：]?\s*(\d{4})",
        r"\((\d{4})\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    for match in re.finditer(r"\b\d{4}\b", text):
        value = int(match.group(0))
        before = text[max(0, match.start() - 20):match.start()].lower()
        after = text[match.end():match.end() + 80].lower()
        nearby = before + match.group(0) + after
        if 1900 <= value <= 2100:
            continue
        if (match.start() > 0 and text[match.start() - 1] in "-/") or (match.end() < len(text) and text[match.end()] in "-/"):
            continue
        if any(key in nearby for key in BAD_STOCK_CONTEXT):
            continue
        if any(key in before for key in ["目標", "target", "price", "tp"]):
            continue
        return match.group(0)
    return ""


def find_stock_mentions(text):
    patterns = [
        r"\((\d{4})\s*\.\s*(?:TW|TWO|TT)\)",
        r"\b(\d{4})\s*(?:TW|TWO|TT)\b",
        r"(?:股票代號|證券代號|代號|Ticker|Stock\s*Code)\s*[:：]?\s*(\d{4})",
        r"\((\d{4})\)",
    ]
    mentions = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            code = match.group(1)
            if 1900 <= int(code) <= 2100:
                continue
            mentions.append({"stock": code, "start": match.start()})

    mentions.sort(key=lambda item: item["start"])

    unique_mentions = []
    seen = set()
    for mention in mentions:
        if mention["stock"] in seen:
            continue
        seen.add(mention["stock"])
        unique_mentions.append(mention)

    if unique_mentions:
        return unique_mentions

    broad_context = text[:12000]
    for match in re.finditer(r"\b\d{4}\b", broad_context):
        code = match.group(0)
        value = int(code)
        if 1900 <= value <= 2100:
            continue
        if (match.start() > 0 and broad_context[match.start() - 1] in "-/") or (
            match.end() < len(broad_context) and broad_context[match.end()] in "-/"
        ):
            continue

        before = broad_context[max(0, match.start() - 40):match.start()].lower()
        after = broad_context[match.end():match.end() + 100].lower()
        nearby = before + code + after
        if any(key in nearby for key in BAD_STOCK_CONTEXT):
            continue
        if any(key in before for key in ["目標", "target", "price", "tp", "eps"]):
            continue
        if re.search(r"%|％|[-/]\d{1,4}|億|元|\.\d", after[:12]):
            continue
        if any(key in nearby for key in ["買進", "中立", "賣出", "評等", "建議", "推薦", "公司", "個股", "股票", "ticker", "tt", ".tw", ".two"]):
            mentions.append({"stock": code, "start": match.start()})

    mentions.sort(key=lambda item: item["start"])
    unique_mentions = []
    seen = set()
    for mention in mentions:
        if mention["stock"] in seen:
            continue
        seen.add(mention["stock"])
        unique_mentions.append(mention)

    if unique_mentions:
        return unique_mentions

    fallback = extract_stock_code(text)
    if fallback:
        return [{"stock": fallback, "start": 0}]
    return []


def stock_section(text, mentions, index):
    start = max(0, mentions[index]["start"] - 400)
    if index + 1 < len(mentions):
        end = mentions[index + 1]["start"]
    else:
        end = min(len(text), mentions[index]["start"] + 3200)
    return text[start:end]


def segments_after_pattern(text, label_pattern, length=100):
    pattern = rf"{label_pattern}\s*(?:至|為|到|:|：|=)?\s*(?:NT\$|TWD|新台幣|台幣|\$)?\s*"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        yield text[match.end():match.end() + length]


def price_candidates(segment, min_value=50):
    values = []
    for match in re.finditer(r"\d+(?:\.\d+)?", segment):
        before = segment[max(0, match.start() - 12):match.start()]
        after = segment[match.end():match.end() + 16]
        context = before + match.group(0) + after

        if re.search(r"\d{2,4}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{1,4}", context):
            continue
        if re.search(r"\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?", context):
            continue
        if re.search(r"年|月|日", after[:4]):
            continue
        if re.search(r"\d+\s*[-－]\s*\d+", context):
            continue
        if re.search(r"%|％", after):
            continue

        value = number(match.group(0))
        if value is not None and min_value <= value:
            values.append(value)
    return values


def extract_target_price(text):
    text = normalize_text(text).replace(",", "")
    labels = [
        r"目標(?:價|價格)",
        r"Target\s*Price",
        r"Price\s*Target",
        r"\bTP\b",
    ]
    candidates = []
    for label in labels:
        for segment in segments_after_pattern(text, label, 60):
            if re.search(r"評等|推薦|建議|買進|賣出|持有|中立|日期|報告|研究", segment[:20]):
                continue
            if re.match(r"\s*\d{4}\s*年\s*\d{1,2}\s*月", segment):
                continue
            stop = re.search(
                r"EPS|收盤|大盤|市值|股本|日期|評等|QoQ|YoY|毛利|營收|電話|地址|傳真|"
                r"Email|E-mail|電子信箱|免責|聲明|服務據點|研究員|分析師",
                segment,
                re.I,
            )
            scoped = segment[:stop.start()] if stop else segment
            candidates.extend(price_candidates(scoped, 50))

    return max(candidates) if candidates else None


def rating_value_pattern():
    return "|".join(re.escape(term) for term in sorted(RATING_TERMS, key=len, reverse=True))


def normalize_rating(value):
    rating = re.sub(r"\s+", " ", value or "").strip(" :：/-")
    return RATING_MAP.get(rating.lower(), rating)


def rating_term_pattern(term):
    escaped = re.escape(term)
    if re.search(r"[A-Za-z]", term):
        return rf"(?<![A-Za-z]){escaped}(?![A-Za-z])"
    return escaped


def first_rating_term(segment):
    best = None
    for term in RATING_TERMS:
        match = re.search(rating_term_pattern(term), segment, re.IGNORECASE)
        if not match:
            continue
        candidate = (match.start(), -len(term), normalize_rating(match.group(0)))
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else ""


def extract_rating(text):
    text = normalize_text(text)
    labels = [
        "投資建議", "投資評等", "評等", "建議", "推薦",
        "Recommendation", "Rating", "Investment Rating",
    ]
    for label in labels:
        for match in re.finditer(re.escape(label), text, re.IGNORECASE):
            segment = text[match.start():match.end() + 90]
            rating = first_rating_term(segment)
            if rating:
                return rating

    advisory_patterns = [
        r"不推薦[^。；;]{0,30}",
        r"不建議[^。；;]{0,30}",
        r"建議[^。；;]{0,30}",
        r"推薦[^。；;]{0,30}",
    ]
    for pattern in advisory_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        rating = first_rating_term(match.group(0))
        if rating:
            return rating
        return "不推薦" if match.group(0).startswith(("不推薦", "不建議")) else "有建議/推薦"

    value_pattern = rating_value_pattern()
    patterns = [
        rf"(?:投資建議|投資評等|評等|建議|推薦|Recommendation|Rating|Investment\s*Rating)\s*[:：=]?\s*({value_pattern})",
        rf"({value_pattern})\s*(?:評等|建議|推薦|rating|recommendation)",
        rf"\b({value_pattern})\b",
        r"(?:建議|推薦)[^。；;]{0,20}(?:買進|加碼|增持|持有|觀望|減碼|賣出)",
        r"(?:不建議|不推薦)[^。；;]{0,20}(?:買進|投資|追價)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_rating(match.group(1) if match.lastindex else match.group(0))
    return ""


def extract_rating_near_stock(text, stock_code):
    if not stock_code:
        return extract_rating(text)

    stock_pattern = rf"(?<!\d){re.escape(stock_code)}(?!\d)"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(stock_pattern, line):
            continue
        rating = extract_rating(line)
        if rating:
            return rating
        section = " ".join(lines[max(0, index - 2):index + 4])
        if any(keyword in section.lower() for keyword in BAD_STOCK_CONTEXT):
            continue
        rating = extract_rating(section)
        if rating:
            return rating

    positions = [match.start() for match in re.finditer(re.escape(stock_code), text)]
    for position in positions:
        section = text[max(0, position - 800):position + 1200]
        if any(keyword in section.lower() for keyword in BAD_STOCK_CONTEXT):
            continue
        rating = extract_rating(section)
        if rating:
            return rating
    return extract_rating(text[:5000])


def broker_from_known_names(value):
    compact_value = re.sub(r"\s+", "", value or "").lower()
    plain_value = value or ""
    for broker in sorted(BROKERS, key=len, reverse=True):
        compact_broker = re.sub(r"\s+", "", broker).lower()
        if broker.lower() in plain_value.lower() or compact_broker in compact_value:
            return broker
    for alias, display_name in BROKER_ALIASES.items():
        compact_alias = re.sub(r"\s+", "", alias).lower()
        if compact_alias in compact_value:
            return display_name
    return ""


def clean_broker(value):
    text = re.sub(r"\s+", " ", value or "").strip()
    lowered = text.lower()
    compact = re.sub(r"\s+", "", text).lower()
    is_ownership_line = re.search(r"(?:著作權|版權|copyright).{0,30}(?:為|屬於|belongs?to)?.{0,30}(?:投顧|證券|securities|capital|research)", compact, re.IGNORECASE)
    if any(keyword in lowered for keyword in BAD_STOCK_CONTEXT) and not is_ownership_line:
        return ""
    known_broker = broker_from_known_names(text)
    if known_broker:
        return known_broker
    if any(keyword in text for keyword in ["本研究報告", "公司報告", "投資建議", "投資評等", "股票代號", "證券代號"]):
        return ""
    text = re.sub(r"^(?:公司資料|資料來源|來源|出刊|研究|報告)(?:及|與|/|-)*", "", text)
    return re.split(r"[，,。；;:/：｜|]", text)[0].strip()[:30]


def extract_broker(text, filename=""):
    combined = f"{filename}\n{text}"[:12000]
    compact = re.sub(r"\s+", "", combined).lower()
    for broker in sorted(BROKERS, key=len, reverse=True):
        if broker.lower() in combined.lower() or re.sub(r"\s+", "", broker).lower() in compact:
            compact_broker = re.sub(r"\s+", "", broker).lower()
            broker_index = compact.find(compact_broker)
            nearby = compact[max(0, broker_index - 80):broker_index + 120]
            is_ownership_line = re.search(
                rf"(?:著作權|版權|copyright).{{0,20}}(?:為|屬於|belongs?to)?.{{0,20}}{re.escape(compact_broker)}",
                nearby,
                re.IGNORECASE,
            )
            if any(keyword in nearby for keyword in ["免責", "聲明", "服務據點"]) and not is_ownership_line:
                continue
            return broker

    broker_context = compact[:5000] + compact[-4000:]
    for alias, display_name in BROKER_ALIASES.items():
        compact_alias = re.sub(r"\s+", "", alias).lower()
        if compact_alias not in broker_context:
            continue
        alias_index = broker_context.find(compact_alias)
        nearby = broker_context[max(0, alias_index - 80):alias_index + 120]
        if any(keyword in nearby for keyword in ["免責", "聲明", "服務據點", "電話", "地址", "傳真", "analyst", "account"]):
            continue
        if any(keyword in nearby for keyword in ["投顧", "證券", "研究", "報告", "research"]):
            return display_name

    patterns = [
        r"(?:券商|研究機構|報告機構|出具機構|機構|Broker|Research)\s*[:：=]?\s*([^\n\r]{2,40})",
        r"(?:本報告由|本報告僅供)\s*([^\n\r]{2,30}(?:投顧|證券))",
        r"([\u4e00-\u9fffA-Za-z .&]{2,30}(?:投顧|證券|Securities|Capital|Research))",
    ]
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            broker = clean_broker(match.group(1))
            if broker and "股票代號" not in broker and "證券代號" not in broker:
                return broker
    return ""


def extract_report_date(text):
    text = text[:5000]
    patterns = [
        r"(?:資料日期|報告日期|出刊日期|發布日期|日期|Date)\s*[:：]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
        r"(?:資料日期|報告日期|出刊日期|發布日期|日期)\s*[:：]?\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        r"(?:資料日期|報告日期|出刊日期|發布日期|日期)\s*[:：]?\s*(民國\s*\d{2,3}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
        r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        r"(民國\s*\d{2,3}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(1))
    return ""


def parse_report(uploaded_file):
    text = extract_pdf_text(uploaded_file)
    stock_code = extract_stock_code(text)
    return {
        "file_name": uploaded_file.name,
        "stock": stock_code,
        "target": extract_target_price(text),
        "rating": extract_rating_near_stock(text, stock_code),
        "broker": extract_broker(text, uploaded_file.name),
        "date": extract_report_date(text),
        "raw_text": text,
    }


def parse_report_from_text(text, filename, stock_hint=""):
    stock_code = stock_hint or extract_stock_code(text)
    return {
        "file_name": filename,
        "stock": stock_code,
        "target": extract_target_price(text),
        "rating": extract_rating_near_stock(text, stock_code),
        "broker": extract_broker(text, filename),
        "date": extract_report_date(text),
        "raw_text": text,
    }


def parse_reports(uploaded_file):
    text = extract_pdf_text(uploaded_file)
    mentions = find_stock_mentions(text)

    if len(mentions) <= 1:
        stock_hint = mentions[0]["stock"] if mentions else ""
        return [parse_report_from_text(text, uploaded_file.name, stock_hint)]

    global_broker = extract_broker(text, uploaded_file.name)
    global_date = extract_report_date(text)
    reports = []

    for index, mention in enumerate(mentions):
        section = stock_section(text, mentions, index)
        target = extract_target_price(section)
        if target is None:
            target = extract_target_price(text[mention["start"]:mention["start"] + 2200])

        reports.append({
            "file_name": uploaded_file.name,
            "stock": mention["stock"],
            "target": target,
            "rating": extract_rating(section) or extract_rating_near_stock(text, mention["stock"]),
            "broker": extract_broker(section, uploaded_file.name) or global_broker,
            "date": extract_report_date(section) or global_date,
            "raw_text": section,
        })

    return reports


@st.cache_data(ttl=300, show_spinner=False)
def fetch_quote(stock_code):
    symbols = [stock_code] if "." in stock_code else [f"{stock_code}.TW", f"{stock_code}.TWO"]
    for symbol in symbols:
        quote = fetch_quote_yfinance(symbol)
        if quote["price"]:
            return quote

        quote = fetch_quote_yahoo_chart(symbol)
        if quote["price"]:
            return quote

        quote = fetch_quote_yahoo_page(symbol)
        if quote["price"]:
            return quote

    return {"price": None, "name": "", "symbol": "", "source": ""}


def fetch_quote_yfinance(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if hist is not None and not hist.empty:
            price = float(hist["Close"].iloc[-1])
            name = ""
            try:
                info = ticker.get_info()
                name = info.get("longName") or info.get("shortName") or ""
            except Exception:
                name = ""
            return {"price": price, "name": name, "symbol": symbol, "source": "yfinance"}
    except Exception:
        pass
    return {"price": None, "name": "", "symbol": symbol, "source": ""}


def yahoo_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "application/json,text/html,application/xhtml+xml",
    }


def fetch_quote_yahoo_chart(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "1d", "interval": "1d"}
    try:
        response = requests.get(url, params=params, headers=yahoo_headers(), timeout=10)
        response.raise_for_status()
        data = response.json()
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            return {"price": None, "name": "", "symbol": symbol, "source": ""}
        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice")
        name = meta.get("shortName") or meta.get("longName") or ""
        if price:
            return {"price": float(price), "name": name, "symbol": symbol, "source": "yahoo_chart"}
    except Exception:
        pass
    return {"price": None, "name": "", "symbol": symbol, "source": ""}


def fetch_quote_yahoo_page(symbol):
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    try:
        response = requests.get(url, headers=yahoo_headers(), timeout=12)
        response.raise_for_status()
        text = re.sub(r"\s+", " ", response.text)
        code = re.search(r"\d{4}", symbol)
        code_text = code.group(0) if code else ""
        name = ""
        name_match = re.search(rf"#?\s*([^<#\s]+)\s+{code_text}\b", text)
        if name_match:
            name = name_match.group(1)

        patterns = [
            rf"{code_text}\b[\s\S]{{0,260}}?加入自選股\s*([\d,]+(?:\.\d+)?)",
            r"(?:成交|股價)\s*([-\d,]+(?:\.\d+)?)",
            r"即時行情[\s\S]{0,180}?成交\s*([-\d,]+(?:\.\d+)?)",
            r"收盤\s*\|[\s\S]{0,180}?成交\s*([-\d,]+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            price = number(match.group(1))
            if price and 0 < price < 10000:
                return {"price": float(price), "name": name, "symbol": symbol, "source": "yahoo_page"}
    except Exception:
        pass
    return {"price": None, "name": "", "symbol": symbol, "source": ""}


def row_key(row):
    target = row.get("目標價")
    rating = row.get("建議/推薦", row.get("評等", ""))
    return (
        row.get("檔名", ""),
        row.get("股票", ""),
        row.get("券商", "-"),
        row.get("資料日期", "-"),
        rating or "",
        rating if target is None else float(target),
    )


def add_row(stock, company, broker, date, current, target):
    if not stock or current is None or target is None:
        return False
    row = {
        "股票": stock,
        "公司": company or "-",
        "券商": broker or "-",
        "資料日期": date or "-",
        "目前價": float(current),
        "目標價": float(target),
    }
    row["漲幅"] = ((row["目標價"] - row["目前價"]) / row["目前價"]) * 100

    existing = {row_key(item) for item in st.session_state.rows}
    if row_key(row) in existing:
        return False

    st.session_state.rows.append(row)
    return True


def process_uploads(files):
    added = 0
    pending = 0
    skipped = 0

    for uploaded_file in files:
        file_key = (uploaded_file.name, uploaded_file.size)
        if file_key in st.session_state.processed_files:
            skipped += 1
            continue

        st.session_state.processed_files.add(file_key)
        parsed_reports = parse_reports(uploaded_file)
        for parsed in parsed_reports:
            quote = fetch_quote(parsed["stock"]) if parsed["stock"] else {"price": None, "name": "", "symbol": ""}

            if parsed["stock"] and parsed["target"] and quote["price"]:
                if add_row(
                    parsed["stock"],
                    quote["name"],
                    parsed["broker"],
                    parsed["date"],
                    quote["price"],
                    parsed["target"],
                ):
                    added += 1
                else:
                    skipped += 1
            else:
                parsed["reason"] = "Yahoo Finance 抓不到現價或欄位不足"
                st.session_state.pending.append(parsed)
                pending += 1

    return added, pending, skipped


def init_tab_state():
    st.session_state.setdefault("single_rows", [])
    st.session_state.setdefault("single_pending", [])
    st.session_state.setdefault("single_processed_files", set())
    st.session_state.setdefault("multi_rows", [])
    st.session_state.setdefault("multi_pending", [])
    st.session_state.setdefault("multi_processed_files", set())


def add_row_to(bucket, stock, company, broker, date, current, target, rating="", file_name="", raw_text=""):
    if not stock or current is None:
        return False
    target_value = None if target is None else float(target)

    row = {
        "檔名": file_name or "",
        "股票": stock,
        "公司": company or "-",
        "券商": broker or "-",
        "資料日期": date or "-",
        "建議/推薦": rating or "",
        "目前價": float(current),
        "目標價": target_value,
        "原文": raw_text or "",
    }
    row["漲幅"] = None if target_value is None else ((target_value - row["目前價"]) / row["目前價"]) * 100

    rows = st.session_state[bucket]
    existing = {row_key(item) for item in rows}
    if row_key(row) in existing:
        return False

    rows.append(row)
    return True


def process_single_uploads(files):
    return process_tab_uploads(files, "single_rows", "single_pending", "single_processed_files", parse_report)


def process_multi_uploads(files):
    return process_tab_uploads(files, "multi_rows", "multi_pending", "multi_processed_files", parse_reports)


def process_tab_uploads(files, row_key_name, pending_key_name, processed_key_name, parser):
    added = 0
    pending = 0
    skipped = 0

    for uploaded_file in files:
        file_key = (uploaded_file.name, uploaded_file.size)
        if file_key in st.session_state[processed_key_name]:
            skipped += 1
            continue

        st.session_state[processed_key_name].add(file_key)
        parsed_items = parser(uploaded_file)
        if isinstance(parsed_items, dict):
            parsed_items = [parsed_items]

        for parsed in parsed_items:
            quote = fetch_quote(parsed["stock"]) if parsed["stock"] else {"price": None, "name": "", "symbol": ""}
            if parsed["stock"] and quote["price"]:
                if add_row_to(
                    row_key_name,
                    parsed["stock"],
                    quote["name"],
                    parsed["broker"],
                    parsed["date"],
                    quote["price"],
                    parsed["target"],
                    parsed.get("rating", ""),
                    parsed.get("file_name", ""),
                    parsed.get("raw_text", ""),
                ):
                    added += 1
                else:
                    skipped += 1
            else:
                parsed["reason"] = "Yahoo Finance 抓不到現價或股票代碼不足"
                st.session_state[pending_key_name].append(parsed)
                pending += 1

    return added, pending, skipped


def render_pending(pending_key_name, row_key_name, prefix):
    if not st.session_state[pending_key_name]:
        return

    st.subheader("待確認資料")
    for index, item in enumerate(st.session_state[pending_key_name]):
        title = f"{item.get('stock') or '-'} / {item.get('broker') or '-'} / {item.get('date') or '-'} / 目 {format_num(item.get('target'))}"
        with st.expander(title):
            st.caption(item.get("reason", ""))
            quote = fetch_quote(item["stock"]) if item.get("stock") else {"price": None, "name": "", "symbol": ""}
            st.write(f"Yahoo 現價：{format_num(quote['price']) or '抓不到'}")
            c1, c2 = st.columns([1, 1])
            manual_price = c1.text_input("手動目前價", key=f"{prefix}_pending_price_{index}")
            if c2.button("加入表格", key=f"{prefix}_add_pending_{index}"):
                price = quote["price"] or number(manual_price)
                if add_row_to(row_key_name, item["stock"], quote["name"], item["broker"], item["date"], price, item["target"], item.get("rating", ""), item.get("file_name", ""), item.get("raw_text", "")):
                    st.session_state[pending_key_name].pop(index)
                    st.rerun()
                else:
                    st.warning("資料不足或重複")
            with st.expander("PDF 文字"):
                st.text_area("內容", item.get("raw_text", ""), height=180, key=f"{prefix}_raw_{index}")


def render_table_and_chart(row_key_name, chart_title="漲幅圖表", positive_only=False):
    left, right = st.columns([3, 1])

    with left:
        st.subheader("資料表")
        rows = st.session_state[row_key_name]
        if rows:
            df = pd.DataFrame(rows).sort_values("漲幅", ascending=False)
            display_df = df.copy()
            display_df["目前價"] = display_df["目前價"].map(lambda value: f"{value:.2f}")
            display_df["目標價"] = display_df["目標價"].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
            display_df["漲幅"] = display_df["漲幅"].map(lambda value: "" if pd.isna(value) else f"{value:.1f}%")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("尚無資料")

    with right:
        st.subheader(chart_title)
        rows = st.session_state[row_key_name]
        if rows:
            chart_df = pd.DataFrame(rows)[["股票", "漲幅"]].dropna(subset=["漲幅"])
            if positive_only:
                chart_df = chart_df[chart_df["漲幅"] > 0]
            if chart_df.empty:
                st.info("沒有正漲幅資料")
            else:
                chart_df = chart_df.sort_values("漲幅", ascending=False)
                st.bar_chart(chart_df.set_index("股票"))
        else:
            st.info("尚無資料")


def render_manual_add(row_key_name, prefix):
    st.subheader("手動新增")
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    manual_stock = col1.text_input("股票", key=f"{prefix}_manual_stock")
    manual_company = col2.text_input("公司", key=f"{prefix}_manual_company")
    manual_broker = col3.text_input("券商", key=f"{prefix}_manual_broker")
    manual_date = col4.text_input("資料日期", key=f"{prefix}_manual_date")
    manual_rating = col5.text_input("建議/推薦", key=f"{prefix}_manual_rating")
    manual_current = col6.text_input("目前價", key=f"{prefix}_manual_current")
    manual_target = col7.text_input("目標價", key=f"{prefix}_manual_target")

    if st.button("新增", type="primary", key=f"{prefix}_manual_add"):
        current = number(manual_current)
        company = manual_company
        if current is None and manual_stock:
            quote = fetch_quote(manual_stock)
            current = quote["price"]
            if quote["name"] and not company:
                company = quote["name"]
        target = number(manual_target)
        if add_row_to(row_key_name, manual_stock, company, manual_broker, manual_date, current, target, manual_rating):
            st.success("已新增")
        else:
            st.warning("資料不足或重複")


SAMPLE_ROWS = [
    {"股票": "2308", "公司": "Delta Electronics, Inc.", "券商": "宏遠投顧", "資料日期": "2026/05/04", "建議/推薦": "買進", "目前價": 2370.0, "目標價": 2600.0},
    {"股票": "6805", "公司": "Fositek Corp.", "券商": "統一投顧", "資料日期": "2026/03/06", "建議/推薦": "買進", "目前價": 1950.0, "目標價": 2600.0},
    {"股票": "6488", "公司": "GlobalWafers Co., Ltd.", "券商": "統一投顧", "資料日期": "2025/08/06", "建議/推薦": "買進", "目前價": 811.0, "目標價": 880.0},
    {"股票": "1301", "公司": "Formosa Plastics Corp.", "券商": "華南投顧", "資料日期": "2026年05月11日", "建議/推薦": "買進", "目前價": 48.9, "目標價": None},
    {"股票": "3037", "公司": "Unimicron Technology Corp.", "券商": "Morgan Stanley", "資料日期": "-", "建議/推薦": "Overweight", "目前價": 933.0, "目標價": None},
]


def row_with_gain(row):
    item = dict(row)
    current = number(item.get("目前價"))
    target = number(item.get("目標價"))
    item["目前價"] = current
    item["目標價"] = target
    item["漲幅"] = None if current is None or target is None or current == 0 else ((target - current) / current) * 100
    return item


def parse_report_date_value(value):
    text = str(value or "").strip()
    if not text or text == "-":
        return pd.NaT
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if not match:
        match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not match:
        return pd.NaT
    year, month, day = map(int, match.groups())
    return pd.Timestamp(datetime(year, month, day))


def history_period(days):
    if days <= 31:
        return "1mo"
    if days <= 95:
        return "3mo"
    if days <= 190:
        return "6mo"
    if days <= 370:
        return "1y"
    if days <= 740:
        return "2y"
    return "5y"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_history(stock_code, days):
    symbols = [stock_code] if "." in str(stock_code) else [f"{stock_code}.TW", f"{stock_code}.TWO"]
    for symbol in symbols:
        try:
            hist = yf.Ticker(symbol).history(period=history_period(days), auto_adjust=False)
            if hist is None or hist.empty or "Close" not in hist:
                continue
            close = hist["Close"].dropna().tail(days)
            if len(close) >= 2:
                return pd.DataFrame({"收盤價": close.astype(float)})
        except Exception:
            continue
    return pd.DataFrame(columns=["收盤價"])


def max_drawdown(close):
    if close.empty:
        return None
    peak = close.cummax()
    drawdown = (close / peak - 1) * 100
    return float(drawdown.min())


def history_metrics(stock_code, days):
    hist = fetch_history(stock_code, days)
    if hist.empty:
        return {"歷史報酬": None, "波動": None, "最大回撤": None, "低基期位置": None, "history": hist}
    close = hist["收盤價"]
    returns = close.pct_change().dropna()
    historical_return = ((close.iloc[-1] / close.iloc[0]) - 1) * 100 if len(close) >= 2 else None
    volatility = returns.std() * (252 ** 0.5) * 100 if not returns.empty else None
    low = close.min()
    high = close.max()
    base_position = None if high == low else ((close.iloc[-1] - low) / (high - low)) * 100
    return {
        "歷史報酬": None if historical_return is None else float(historical_return),
        "波動": None if volatility is None or pd.isna(volatility) else float(volatility),
        "最大回撤": max_drawdown(close),
        "低基期位置": None if base_position is None or pd.isna(base_position) else float(base_position),
        "history": hist,
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_profile(stock_code, days):
    symbols = [stock_code] if "." in str(stock_code) else [f"{stock_code}.TW", f"{stock_code}.TWO"]
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=history_period(days), auto_adjust=False)
            if hist is None or hist.empty:
                continue

            avg_volume_lots = None
            if "Volume" in hist:
                volume = hist["Volume"].dropna().tail(20)
                if not volume.empty:
                    avg_volume_lots = float(volume.mean() / 1000)

            market_cap_million = None
            try:
                info = ticker.get_info()
                market_cap = info.get("marketCap")
                if market_cap:
                    market_cap_million = float(market_cap / 1_000_000)
            except Exception:
                market_cap_million = None

            return {
                "平均成交張數": avg_volume_lots,
                "市值百萬元": market_cap_million,
                "行情代號": symbol,
            }
        except Exception:
            continue
    return {"平均成交張數": None, "市值百萬元": None, "行情代號": ""}


def text_window(text, start, radius=42):
    clean = re.sub(r"\s+", " ", text or "").strip()
    return clean[max(0, start - radius):start + radius].strip()


def extract_percent_after(patterns, text):
    clean = re.sub(r"\s+", " ", text or "")
    for pattern in patterns:
        for match in re.finditer(pattern, clean, re.IGNORECASE):
            value = number(match.group(1))
            if value is not None:
                return float(value), text_window(clean, match.start())
    return None, ""


def yfinance_symbols(stock_code):
    return [stock_code] if "." in str(stock_code) else [f"{stock_code}.TW", f"{stock_code}.TWO"]


def financial_values(statement, aliases):
    if statement is None or statement.empty:
        return []
    normalized = {str(index).lower().replace(" ", ""): index for index in statement.index}
    row_name = None
    for alias in aliases:
        key = alias.lower().replace(" ", "")
        if key in normalized:
            row_name = normalized[key]
            break
    if row_name is None:
        return []

    columns = list(statement.columns)
    try:
        columns = sorted(columns, key=lambda value: pd.to_datetime(value), reverse=True)
    except Exception:
        pass

    values = []
    for column in columns:
        value = number(statement.loc[row_name, column])
        if value is not None and not pd.isna(value):
            values.append(float(value))
    return values


def rate_change(new, old):
    if new is None or old in (None, 0):
        return None
    return (new / old - 1) * 100


def format_money_short(value):
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    return f"{value:,.0f}"


def holder_pct_change(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.replace("%", "").replace("+", "").strip()
    parsed = number(value)
    if parsed is None:
        return None
    return float(parsed)


def stock_id(value):
    return str(value or "").split(".")[0].strip()


def init_stock_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monthly_revenue (
                stock_id TEXT NOT NULL,
                date TEXT,
                revenue_year INTEGER NOT NULL,
                revenue_month INTEGER NOT NULL,
                revenue REAL NOT NULL,
                source TEXT DEFAULT 'import',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (stock_id, revenue_year, revenue_month)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS institutional_buy_sell (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                name TEXT NOT NULL,
                buy REAL DEFAULT 0,
                sell REAL DEFAULT 0,
                source TEXT DEFAULT 'import',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (stock_id, date, name)
            )
            """
        )


def database_counts():
    init_stock_database()
    with sqlite3.connect(DB_PATH) as conn:
        revenue_count = conn.execute("SELECT COUNT(*) FROM monthly_revenue").fetchone()[0]
        institutional_count = conn.execute("SELECT COUNT(*) FROM institutional_buy_sell").fetchone()[0]
    return revenue_count, institutional_count


def load_monthly_revenue_from_db(code):
    init_stock_database()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT stock_id, date, revenue_year, revenue_month, revenue
            FROM monthly_revenue
            WHERE stock_id = ?
            ORDER BY revenue_year, revenue_month
            """,
            conn,
            params=(stock_id(code),),
        )


def load_institutional_from_db(code, days=21):
    init_stock_database()
    start_date = (pd.Timestamp.today().normalize() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT stock_id, date, name, buy, sell
            FROM institutional_buy_sell
            WHERE stock_id = ? AND date >= ?
            ORDER BY date, name
            """,
            conn,
            params=(stock_id(code), start_date),
        )


def save_monthly_revenue_to_db(df, source="import"):
    if df.empty:
        return 0
    work = df.copy()
    if "stock_id" not in work and "data_id" in work:
        work["stock_id"] = work["data_id"]
    required = {"stock_id", "revenue_year", "revenue_month", "revenue"}
    if not required.issubset(work.columns):
        return 0
    if "date" not in work:
        work["date"] = work.apply(lambda row: f"{int(row['revenue_year']):04d}-{int(row['revenue_month']):02d}-01", axis=1)

    rows = []
    for _, row in work.iterrows():
        revenue = number(row.get("revenue"))
        year = number(row.get("revenue_year"))
        month = number(row.get("revenue_month"))
        if revenue is None or year is None or month is None:
            continue
        rows.append((stock_id(row.get("stock_id")), str(row.get("date") or ""), int(year), int(month), float(revenue), source))

    init_stock_database()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO monthly_revenue
                (stock_id, date, revenue_year, revenue_month, revenue, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            rows,
        )
    return len(rows)


def save_institutional_to_db(df, source="import"):
    if df.empty:
        return 0
    work = df.copy()
    if "stock_id" not in work and "data_id" in work:
        work["stock_id"] = work["data_id"]
    required = {"stock_id", "date", "name", "buy", "sell"}
    if not required.issubset(work.columns):
        return 0

    rows = []
    for _, row in work.iterrows():
        buy = number(row.get("buy")) or 0
        sell = number(row.get("sell")) or 0
        date_value = pd.to_datetime(row.get("date"), errors="coerce")
        if pd.isna(date_value):
            continue
        rows.append((stock_id(row.get("stock_id")), date_value.strftime("%Y-%m-%d"), str(row.get("name")), float(buy), float(sell), source))

    init_stock_database()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO institutional_buy_sell
                (stock_id, date, name, buy, sell, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            rows,
        )
    return len(rows)


def read_uploaded_csv(uploaded_file):
    raw = uploaded_file.getvalue()
    for encoding in ["utf-8-sig", "utf-8", "cp950", "big5"]:
        try:
            return pd.read_csv(BytesIO(raw), encoding=encoding)
        except Exception:
            continue
    return pd.DataFrame()


def configured_finmind_password():
    try:
        return str(st.secrets.get("FINMIND_UPDATE_PASSWORD", "")).strip()
    except Exception:
        return ""


def finmind_headers(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def finmind_data(dataset, stock_code, start_date, end_date=None, token=""):
    params = {
        "dataset": dataset,
        "data_id": str(stock_code).split(".")[0],
        "start_date": start_date,
    }
    if end_date:
        params["end_date"] = end_date
    if token:
        params["token"] = token

    try:
        response = requests.get(
            "https://api.finmindtrade.com/api/v4/data",
            params=params,
            headers=finmind_headers(token),
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_finmind_revenue_signal(stock_code, token="", allow_api=False):
    df = load_monthly_revenue_from_db(stock_code)
    source_name = "SQLite"
    if df.empty and allow_api:
        start_date = (pd.Timestamp.today().normalize() - pd.DateOffset(years=6)).strftime("%Y-%m-%d")
        df = finmind_data("TaiwanStockMonthRevenue", stock_code, start_date, token=token)
        if not df.empty:
            save_monthly_revenue_to_db(df, source="finmind")
            df = load_monthly_revenue_from_db(stock_code)
            source_name = "FinMind API -> SQLite"

    if df.empty or "revenue" not in df:
        return {
            "營收條件": False,
            "營收特徵": "SQLite 無資料",
            "營收原因": "本機資料庫沒有月營收資料；可匯入 CSV，或勾選缺資料時用 FinMind 更新",
            "營收MoM": None,
            "累積YoY": None,
        }

    df = df.copy()
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
    df["revenue_month"] = pd.to_numeric(df["revenue_month"], errors="coerce")
    df["revenue_year"] = pd.to_numeric(df["revenue_year"], errors="coerce")
    df["date_dt"] = pd.to_datetime(df.get("date"), errors="coerce")
    df = df.dropna(subset=["revenue", "revenue_month", "revenue_year", "date_dt"]).sort_values("date_dt")
    if df.empty:
        return {
            "營收條件": False,
            "營收特徵": "SQLite 資料不足",
            "營收原因": "本機月營收資料欄位不完整",
            "營收MoM": None,
            "累積YoY": None,
        }

    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) >= 2 else None
    mom = rate_change(latest["revenue"], previous["revenue"]) if previous is not None else None

    latest_year = int(latest["revenue_year"])
    latest_month = int(latest["revenue_month"])
    current_ytd = df[(df["revenue_year"] == latest_year) & (df["revenue_month"] <= latest_month)]["revenue"].sum()
    previous_ytd = df[(df["revenue_year"] == latest_year - 1) & (df["revenue_month"] <= latest_month)]["revenue"].sum()
    cumulative_yoy = rate_change(current_ytd, previous_ytd) if previous_ytd else None

    revenue_high = latest["revenue"] >= df["revenue"].max()
    feature = ""
    if revenue_high:
        feature = "月營收創高"
        reason = f"{source_name}：{latest_year}/{latest_month:02d} 月營收 {format_money_short(latest['revenue'])}，為資料庫區間最高"
    elif mom is not None and mom >= 10:
        feature = "月營收 MoM +10%"
        reason = f"{source_name}：{latest_year}/{latest_month:02d} 月營收 {format_money_short(latest['revenue'])}，月增 {mom:.1f}%"
    elif cumulative_yoy is not None and cumulative_yoy >= 10:
        feature = "累積 YoY +10%"
        reason = f"{source_name}：{latest_year} 年累積至 {latest_month} 月營收年增 {cumulative_yoy:.1f}%"
    else:
        reason = (
            f"{latest_year}/{latest_month:02d} 月營收未達策略門檻"
            f"；MoM {mom:.1f}%" if mom is not None else f"{latest_year}/{latest_month:02d} 月營收未達策略門檻"
        )
        if cumulative_yoy is not None:
            reason += f"，累積 YoY {cumulative_yoy:.1f}%"

    return {
        "營收條件": bool(feature),
        "營收特徵": feature or "未通過",
        "營收原因": reason,
        "營收MoM": mom,
        "累積YoY": cumulative_yoy,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_finmind_institutional_signal(stock_code, token="", allow_api=False):
    df = load_institutional_from_db(stock_code)
    source_name = "SQLite"
    if df.empty and allow_api:
        end_date = pd.Timestamp.today().normalize()
        start_date = (end_date - pd.Timedelta(days=21)).strftime("%Y-%m-%d")
        df = finmind_data(
            "TaiwanStockInstitutionalInvestorsBuySell",
            stock_code,
            start_date,
            end_date.strftime("%Y-%m-%d"),
            token,
        )
        if not df.empty:
            save_institutional_to_db(df, source="finmind")
            df = load_institutional_from_db(stock_code)
            source_name = "FinMind API -> SQLite"

    if df.empty or not {"date", "name", "buy", "sell"}.issubset(df.columns):
        return {
            "法人買入": False,
            "法人原因": "本機資料庫沒有法人買賣資料；可匯入 CSV，或勾選缺資料時用 FinMind 更新",
            "外資投信買超張數": None,
        }

    df = df.copy()
    df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
    df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_dt"])
    target = df[df["name"].isin(["Foreign_Investor", "Investment_Trust"])]
    if target.empty:
        return {
            "法人買入": False,
            "法人原因": "法人資料沒有 Foreign_Investor / Investment_Trust 類別",
            "外資投信買超張數": None,
        }

    latest_date = target["date_dt"].max()
    latest_rows = target[target["date_dt"] == latest_date]
    net_shares = float((latest_rows["buy"] - latest_rows["sell"]).sum())
    net_lots = net_shares / 1000
    return {
        "法人買入": net_lots > 0,
        "法人原因": f"{source_name}：{latest_date.strftime('%Y/%m/%d')} 外資+投信買超 {net_lots:,.0f} 張",
        "外資投信買超張數": net_lots,
    }


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_yfinance_strategy_signals(stock_code, finmind_token="", allow_finmind_update=False):
    revenue_signal = fetch_finmind_revenue_signal(stock_code, finmind_token, allow_finmind_update)
    institutional_signal = fetch_finmind_institutional_signal(stock_code, finmind_token, allow_finmind_update)
    fallback = {
        "三率三升": False,
        "三率原因": "yfinance 無法取得季財報",
        "營收條件": revenue_signal["營收條件"],
        "營收特徵": revenue_signal["營收特徵"],
        "營收原因": revenue_signal["營收原因"],
        "營收MoM": revenue_signal["營收MoM"],
        "累積YoY": revenue_signal["累積YoY"],
        "法人買入": institutional_signal["法人買入"],
        "法人原因": institutional_signal["法人原因"],
        "外資投信買超張數": institutional_signal["外資投信買超張數"],
        "策略資料來源": "三率:yfinance 無資料 / 營收與法人:SQLite",
    }

    for symbol in yfinance_symbols(stock_code):
        try:
            ticker = yf.Ticker(symbol)
            statement = None
            for attr in ["quarterly_income_stmt", "quarterly_financials"]:
                try:
                    candidate = getattr(ticker, attr)
                    if candidate is not None and not candidate.empty:
                        statement = candidate
                        break
                except Exception:
                    continue

            revenue = financial_values(statement, ["Total Revenue", "Operating Revenue", "Revenue"])
            gross_profit = financial_values(statement, ["Gross Profit"])
            operating_income = financial_values(statement, ["Operating Income", "Operating Income Or Loss"])
            net_income = financial_values(statement, ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"])
            if not any([revenue, gross_profit, operating_income, net_income]):
                continue

            gross_margin = [gross_profit[i] / revenue[i] * 100 for i in range(min(len(gross_profit), len(revenue))) if revenue[i]]
            operating_margin = [operating_income[i] / revenue[i] * 100 for i in range(min(len(operating_income), len(revenue))) if revenue[i]]
            net_margin = [net_income[i] / revenue[i] * 100 for i in range(min(len(net_income), len(revenue))) if revenue[i]]

            three_rate_pass = (
                len(gross_margin) >= 2
                and len(operating_margin) >= 2
                and len(net_margin) >= 2
                and gross_margin[0] > gross_margin[1]
                and operating_margin[0] > operating_margin[1]
                and net_margin[0] > net_margin[1]
            )
            if len(gross_margin) >= 2 and len(operating_margin) >= 2 and len(net_margin) >= 2:
                three_rate_reason = (
                    f"yfinance 季財報：毛利率 {gross_margin[1]:.1f}%→{gross_margin[0]:.1f}%、"
                    f"營益率 {operating_margin[1]:.1f}%→{operating_margin[0]:.1f}%、"
                    f"淨利率 {net_margin[1]:.1f}%→{net_margin[0]:.1f}%"
                )
            else:
                three_rate_reason = "yfinance 季財報缺少營收、毛利、營業利益或淨利欄位，無法判斷三率三升"

            return {
                "三率三升": three_rate_pass,
                "三率原因": three_rate_reason,
                "營收條件": revenue_signal["營收條件"],
                "營收特徵": revenue_signal["營收特徵"],
                "營收原因": revenue_signal["營收原因"],
                "營收MoM": revenue_signal["營收MoM"],
                "累積YoY": revenue_signal["累積YoY"],
                "法人買入": institutional_signal["法人買入"],
                "法人原因": institutional_signal["法人原因"],
                "外資投信買超張數": institutional_signal["外資投信買超張數"],
                "策略資料來源": f"三率:yfinance:{symbol} / 營收與法人:SQLite",
            }
        except Exception:
            continue

    return fallback


def scenario_rate(name):
    return {"樂觀": 1.0, "中性": 0.85, "悲觀": 0.65}.get(name, 0.85)


def rating_score(value):
    text = str(value or "").lower()
    positive = ["買進", "加碼", "增持", "推薦", "優於大盤", "buy", "overweight", "outperform", "ow"]
    neutral = ["持有", "中立", "觀望", "hold", "neutral", "equal-weight", "equal weight", "market perform", "ew"]
    negative = ["賣出", "減碼", "不推薦", "劣於大盤", "sell", "underweight", "underperform", "uw"]
    if any(term in text for term in positive):
        return 12.0
    if any(term in text for term in neutral):
        return 3.0
    if any(term in text for term in negative):
        return -12.0
    return 0.0


def build_selection_universe(rows, use_sample, recent_only, recent_days, stock_filter, broker_filter, history_days, scenario):
    source_rows = [row_with_gain(row) for row in rows]
    if use_sample:
        source_rows.extend(row_with_gain(row) for row in SAMPLE_ROWS)

    if not source_rows:
        return pd.DataFrame()

    df = pd.DataFrame(source_rows)
    defaults = {
        "檔名": "",
        "股票": "",
        "公司": "-",
        "券商": "-",
        "資料日期": "-",
        "建議/推薦": "",
        "目前價": None,
        "目標價": None,
        "漲幅": None,
        "狀態": "已入表",
        "備註": "",
        "原文": "",
    }
    for column, default in defaults.items():
        if column not in df:
            df[column] = default
    df["股票"] = df["股票"].astype(str)
    df["券商"] = df["券商"].fillna("-").replace("", "-")
    df["公司"] = df["公司"].fillna("-").replace("", "-")
    df["建議/推薦"] = df["建議/推薦"].fillna("")
    df["狀態"] = df["狀態"].fillna("已入表")
    df["備註"] = df["備註"].fillna("")
    df["原文"] = df["原文"].fillna("")
    df["資料日期_dt"] = df["資料日期"].map(parse_report_date_value)

    if recent_only:
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=recent_days)
        df = df[df["資料日期_dt"].notna() & (df["資料日期_dt"] >= cutoff)]

    stock_codes = [code.strip() for code in re.split(r"[,，\s]+", stock_filter or "") if code.strip()]
    if stock_codes:
        df = df[df["股票"].isin(stock_codes)]

    if broker_filter:
        df = df[df["券商"].isin(broker_filter)]

    if df.empty:
        return df.reset_index(drop=True)

    metrics = []
    rate = scenario_rate(scenario)
    for _, row in df.iterrows():
        item = history_metrics(row["股票"], history_days)
        current = number(row.get("目前價"))
        target = number(row.get("目標價"))
        scenario_target = None if current is None or target is None else current + ((target - current) * rate)
        scenario_return = None if current is None or scenario_target is None or current == 0 else ((scenario_target - current) / current) * 100
        metrics.append({
            "情境目標價": scenario_target,
            "情境報酬": scenario_return,
            "歷史報酬": item["歷史報酬"],
            "波動": item["波動"],
            "最大回撤": item["最大回撤"],
            "低基期位置": item["低基期位置"],
        })

    metric_df = pd.DataFrame(metrics, index=df.index)
    df = pd.concat([df.reset_index(drop=True), metric_df.reset_index(drop=True)], axis=1)
    df["建議分數"] = df["建議/推薦"].map(rating_score)
    df["智慧分數"] = (
        df["情境報酬"].fillna(0)
        + df["歷史報酬"].fillna(0) * 0.35
        - df["波動"].fillna(df["波動"].median() if df["波動"].notna().any() else 0) * 0.12
        + df["最大回撤"].fillna(0) * 0.18
        + df["建議分數"].fillna(0)
    )
    return df


def pending_report_rows():
    rows = []
    for item in st.session_state.get("auto_pending", []):
        stock = item.get("stock", "")
        target = number(item.get("target"))
        current = None
        rows.append({
            "檔名": item.get("file_name", ""),
            "股票": stock,
            "公司": "-",
            "券商": item.get("broker") or "-",
            "資料日期": item.get("date") or "-",
            "建議/推薦": item.get("rating") or "",
            "目前價": current,
            "目標價": target,
            "漲幅": None,
            "狀態": "待確認",
            "備註": item.get("reason", "Yahoo Finance 抓不到現價或欄位不足"),
            "原文": item.get("raw_text", ""),
        })
    return rows


def aggregate_stock_universe(report_df, history_days, scenario, low_base_limit=35, min_volume_lots=200, min_market_cap_million=200000, finmind_token="", allow_finmind_update=False):
    if report_df.empty:
        return report_df.copy()

    grouped_rows = []
    rate = scenario_rate(scenario)
    for stock, group in report_df.groupby("股票", sort=False):
        current_values = group["目前價"].dropna()
        current = float(current_values.iloc[-1]) if not current_values.empty else None
        target_values = group["目標價"].dropna()
        avg_target = float(target_values.mean()) if not target_values.empty else None
        high_target = float(target_values.max()) if not target_values.empty else None

        broker_list = sorted({value for value in group["券商"].dropna().astype(str) if value and value != "-"})
        rating_list = sorted({value for value in group["建議/推薦"].dropna().astype(str) if value})
        latest_date = group["資料日期_dt"].dropna().max()
        latest_date_text = "-"
        if pd.notna(latest_date):
            latest_date_text = latest_date.strftime("%Y/%m/%d")
        elif group["資料日期"].notna().any():
            latest_date_text = str(group["資料日期"].dropna().iloc[-1])

        scenario_target = None if current is None or avg_target is None else current + ((avg_target - current) * rate)
        scenario_return = None if current is None or scenario_target is None or current == 0 else ((scenario_target - current) / current) * 100
        gain = None if current is None or avg_target is None or current == 0 else ((avg_target - current) / current) * 100

        representative = group.iloc[-1].copy()
        item = history_metrics(stock, history_days)
        market = fetch_market_profile(stock, history_days)
        rating_text = " / ".join(rating_list)
        broker_text = " / ".join(broker_list)
        signals = fetch_yfinance_strategy_signals(stock, finmind_token, allow_finmind_update)
        low_base_pass = item["低基期位置"] is not None and item["低基期位置"] <= low_base_limit
        volume_pass = market["平均成交張數"] is not None and market["平均成交張數"] >= min_volume_lots
        market_cap_pass = market["市值百萬元"] is not None and market["市值百萬元"] >= min_market_cap_million
        strategy_pass = (
            low_base_pass
            and signals["三率三升"]
            and signals["營收條件"]
            and signals["法人買入"]
            and volume_pass
            and market_cap_pass
        )
        grouped_rows.append({
            "股票": str(stock),
            "公司": representative.get("公司", "-"),
            "券商": broker_text or "-",
            "資料日期": latest_date_text,
            "資料日期_dt": latest_date if pd.notna(latest_date) else pd.NaT,
            "建議/推薦": rating_text,
            "目前價": current,
            "目標價": avg_target,
            "最高目標價": high_target,
            "漲幅": gain,
            "情境目標價": scenario_target,
            "情境報酬": scenario_return,
            "歷史報酬": item["歷史報酬"],
            "波動": item["波動"],
            "最大回撤": item["最大回撤"],
            "低基期位置": item["低基期位置"],
            "低基期": low_base_pass,
            "三率三升": signals["三率三升"],
            "三率原因": signals["三率原因"],
            "營收條件": signals["營收條件"],
            "營收特徵": signals["營收特徵"],
            "營收原因": signals["營收原因"],
            "營收MoM": signals["營收MoM"],
            "累積YoY": signals["累積YoY"],
            "法人買入": signals["法人買入"],
            "法人原因": signals["法人原因"],
            "外資投信買超張數": signals["外資投信買超張數"],
            "策略資料來源": signals["策略資料來源"],
            "平均成交張數": market["平均成交張數"],
            "市值百萬元": market["市值百萬元"],
            "策略通過": strategy_pass,
            "建議分數": max([rating_score(value) for value in rating_list] or [0]),
            "報告筆數": len(group),
            "券商數": len(broker_list),
        })

    df = pd.DataFrame(grouped_rows)
    if df.empty:
        return df
    df["智慧分數"] = (
        df["情境報酬"].fillna(0)
        + df["歷史報酬"].fillna(0) * 0.35
        - df["波動"].fillna(df["波動"].median() if df["波動"].notna().any() else 0) * 0.12
        + df["最大回撤"].fillna(0) * 0.18
        + df["建議分數"].fillna(0)
        + df["報告筆數"].fillna(0) * 0.6
        + df["低基期"].astype(float).fillna(0) * 8
        + df["三率三升"].astype(float).fillna(0) * 8
        + df["營收條件"].astype(float).fillna(0) * 8
        + df["法人買入"].astype(float).fillna(0) * 6
        + df["策略通過"].astype(float).fillna(0) * 15
    )
    return df


def filter_selection(df, min_return, max_volatility, max_drawdown_limit, max_stocks, apply_strategy=True, min_volume_lots=200, min_market_cap_million=200000, low_base_limit=35):
    if df.empty:
        return df
    selected = df.copy()
    return_mask = (
        selected["情境報酬"].isna()
        | (selected["情境報酬"] >= min_return)
        | ((selected["建議分數"] > 0) & (min_return <= 0))
    )
    volatility_mask = selected["波動"].isna() | (selected["波動"] <= max_volatility)
    drawdown_mask = selected["最大回撤"].isna() | (selected["最大回撤"] >= max_drawdown_limit)
    selected = selected[return_mask & volatility_mask & drawdown_mask]

    if apply_strategy:
        strategy_mask = (
            (selected["低基期位置"].notna() & (selected["低基期位置"] <= low_base_limit))
            & selected["三率三升"].fillna(False)
            & selected["營收條件"].fillna(False)
            & selected["法人買入"].fillna(False)
            & (selected["平均成交張數"].notna() & (selected["平均成交張數"] >= min_volume_lots))
            & (selected["市值百萬元"].notna() & (selected["市值百萬元"] >= min_market_cap_million))
        )
        selected = selected[strategy_mask]

    return selected.sort_values("智慧分數", ascending=False).head(max_stocks)


def add_weights(df, mode):
    if df.empty:
        return df
    result = df.copy()
    if mode == "依智慧分數":
        score = result["智慧分數"].clip(lower=0)
        if score.sum() > 0:
            result["權重"] = score / score.sum() * 100
        else:
            result["權重"] = 100 / len(result)
    elif mode == "依情境報酬":
        returns = result["情境報酬"].fillna(0).clip(lower=0)
        result["權重"] = returns / returns.sum() * 100 if returns.sum() > 0 else 100 / len(result)
    else:
        result["權重"] = 100 / len(result)
    return result


def format_analysis_df(df):
    display = df.copy()
    for column in ["目前價", "目標價", "最高目標價", "情境目標價", "目標金額", "實際投入金額", "未用餘額", "買進手續費"]:
        if column in display:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    for column in ["漲幅", "情境報酬", "歷史報酬", "波動", "最大回撤", "低基期位置", "營收MoM", "累積YoY", "智慧分數", "權重"]:
        if column in display:
            suffix = "%" if column != "智慧分數" else ""
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.1f}{suffix}")
    for column in ["平均成交張數", "外資投信買超張數"]:
        if column in display:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:,.0f}")
    if "市值百萬元" in display:
        display["市值百萬元"] = display["市值百萬元"].map(lambda value: "" if pd.isna(value) else f"{value:,.0f}")
    for column in ["低基期", "三率三升", "營收條件", "法人買入", "策略通過"]:
        if column in display:
            display[column] = display[column].map(lambda value: "✅" if bool(value) else "—")
    return display


def tw_symbol(stock_code):
    code = str(stock_code or "").strip()
    return code if "." in code else f"{code}.TW"


def stable_seed(value):
    return sum((index + 1) * ord(char) for index, char in enumerate(str(value or ""))) % 100000


def synthetic_history(row, days):
    current = number(row.get("目前價")) or 100.0
    score = rating_score(row.get("建議/推薦"))
    target = number(row.get("目標價"))
    implied = 0 if not target or not current else (target / current - 1)
    rng = random.Random(stable_seed(row.get("股票")))
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=max(30, int(days)), freq="B")
    start_price = current / max(0.45, 1 + implied * 0.45 + (score / 100))
    prices = []
    price = start_price
    for index, _ in enumerate(dates):
        drift = (current / start_price - 1) / max(len(dates), 1)
        wave = math.sin(index / 8 + rng.random()) * 0.004
        noise = rng.uniform(-0.012, 0.012)
        price = max(1, price * (1 + drift + wave + noise))
        prices.append(price)
    prices[-1] = current
    return pd.DataFrame({"收盤價": prices}, index=dates)


def analysis_history(row, days):
    hist = fetch_history(row.get("股票"), days)
    if hist.empty:
        return synthetic_history(row, days)
    return hist.tail(days)


def forecast_history(row, hist, forecast_days, scenario):
    current = number(row.get("目前價")) or (hist["收盤價"].iloc[-1] if not hist.empty else 100.0)
    target = number(row.get("目標價"))
    rate = scenario_rate(scenario)
    if target is None:
        target = current * (1 + max(rating_score(row.get("建議/推薦")), 0) / 100)
    scenario_target = current + ((target - current) * rate)
    start_date = hist.index[-1] if not hist.empty else pd.Timestamp.today().normalize()
    dates = pd.date_range(start=start_date + pd.Timedelta(days=1), periods=max(1, int(forecast_days)), freq="B")
    values = []
    for index, _ in enumerate(dates, start=1):
        progress = index / len(dates)
        values.append(current + (scenario_target - current) * progress)
    return pd.DataFrame({f"預測（{scenario}）": values}, index=dates)


def daily_returns(hist):
    if hist.empty:
        return pd.DataFrame(columns=["日報酬率 (%)"])
    returns = hist["收盤價"].pct_change().dropna() * 100
    return pd.DataFrame({"日報酬率 (%)": returns})


def return_matrix(rows, days):
    series = {}
    names = {}
    for _, row in rows.iterrows():
        stock = str(row.get("股票"))
        hist = analysis_history(row, days)
        returns = hist["收盤價"].pct_change().dropna()
        if not returns.empty:
            series[stock] = returns.reset_index(drop=True)
            names[stock] = row.get("公司", stock)
    if not series:
        return pd.DataFrame(), names
    df = pd.DataFrame(series).dropna()
    return df, names


def portfolio_stats(returns, weights):
    if returns.empty or len(weights) == 0:
        return {"年化報酬": 0.0, "年化波動": 0.0, "夏普比率": 0.0}
    weights = pd.Series(weights, index=returns.columns).astype(float)
    weights = weights / weights.sum() if weights.sum() else pd.Series(1 / len(weights), index=returns.columns)
    daily = returns.dot(weights)
    annual_return = daily.mean() * 252 * 100
    annual_volatility = daily.std() * (252 ** 0.5) * 100
    sharpe = annual_return / annual_volatility if annual_volatility else 0.0
    return {"年化報酬": annual_return, "年化波動": annual_volatility, "夏普比率": sharpe}


def simulate_frontier(selected, history_days, count=3000):
    returns, names = return_matrix(selected, history_days)
    if returns.empty:
        return pd.DataFrame(), names
    rng = random.Random(42)
    rows = []
    stocks = list(returns.columns)
    for _ in range(count):
        raw = [rng.random() for _ in stocks]
        total = sum(raw) or 1
        weights = [value / total for value in raw]
        stats = portfolio_stats(returns, weights)
        item = {
            "年化報酬": stats["年化報酬"],
            "年化波動": stats["年化波動"],
            "夏普比率": stats["夏普比率"],
        }
        item.update({f"{stock} 權重": weight * 100 for stock, weight in zip(stocks, weights)})
        rows.append(item)
    return pd.DataFrame(rows), names


def efficient_frontier_curve(frontier):
    if frontier.empty:
        return pd.DataFrame()
    clean = frontier.dropna(subset=["年化波動", "年化報酬"]).sort_values("年化波動")
    rows = []
    best_return = -float("inf")
    for _, row in clean.iterrows():
        annual_return = float(row["年化報酬"])
        if annual_return >= best_return:
            rows.append(row)
            best_return = annual_return
    return pd.DataFrame(rows)


def build_frontier_chart(frontier, current_stats):
    curve = efficient_frontier_curve(frontier)
    best_sharpe = frontier.loc[frontier["夏普比率"].idxmax()]
    min_vol = frontier.loc[frontier["年化波動"].idxmin()]

    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=frontier["年化波動"],
            y=frontier["年化報酬"],
            mode="markers",
            name="隨機組合",
            marker=dict(
                size=5,
                opacity=0.72,
                color=frontier["夏普比率"],
                colorscale=[[0, "#ef4444"], [0.5, "#fff7a8"], [1, "#22c55e"]],
                colorbar=dict(title="夏普比率", tickfont=dict(color="#e5eefb"), titlefont=dict(color="#ffffff")),
                line=dict(width=0),
            ),
            hovertemplate="年化波動 %{x:.1f}%<br>年化報酬 %{y:.1f}%<br>夏普比率 %{marker.color:.2f}<extra></extra>",
        )
    )
    if not curve.empty:
        fig.add_trace(
            go.Scatter(
                x=curve["年化波動"],
                y=curve["年化報酬"],
                mode="lines",
                name="效率前緣",
                line=dict(color="#ffffff", width=3),
                hovertemplate="效率前緣<br>年化波動 %{x:.1f}%<br>年化報酬 %{y:.1f}%<extra></extra>",
            )
        )

    special_points = [
        ("最佳夏普", best_sharpe, "star", "#f59e0b", 22),
        ("最小波動", min_vol, "diamond", "#60a5fa", 20),
        ("目前配置", current_stats, "circle", "#f472b6", 18),
    ]
    for label, point, symbol, color, size in special_points:
        fig.add_trace(
            go.Scatter(
                x=[point["年化波動"]],
                y=[point["年化報酬"]],
                mode="markers+text",
                name=f"{label} (SR={point['夏普比率']:.2f})",
                text=[label],
                textposition="top center",
                textfont=dict(color="#ffffff", size=14),
                marker=dict(symbol=symbol, size=size, color=color, line=dict(color="#ffffff", width=2)),
                hovertemplate=f"{label}<br>年化波動 %{{x:.1f}}%<br>年化報酬 %{{y:.1f}}%<br>夏普比率 {point['夏普比率']:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=dict(text="Markowitz 效率前緣", x=0.01, y=0.93, font=dict(size=18, color="#ffffff")),
        height=690,
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        margin=dict(l=64, r=28, t=74, b=64),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color="#dbe7ff")),
        xaxis=dict(title="年化波動度 (%)", gridcolor="#263449", zeroline=False, color="#b9c7dd"),
        yaxis=dict(title="年化預期報酬 (%)", gridcolor="#263449", zeroline=False, color="#b9c7dd"),
        font=dict(family="Arial, sans-serif", color="#dbe7ff"),
    )
    return fig


def selected_weight_map(selected):
    if selected.empty:
        return {}
    weights = selected.set_index("股票")["權重"].fillna(0) / 100
    if weights.sum() == 0:
        return {stock: 1 / len(weights) for stock in weights.index}
    return (weights / weights.sum()).to_dict()


def current_portfolio_returns(selected, history_days):
    returns, names = return_matrix(selected, history_days)
    if returns.empty:
        return pd.Series(dtype=float), returns, names
    weights = selected_weight_map(selected)
    aligned = pd.Series(weights).reindex(returns.columns).fillna(0)
    aligned = aligned / aligned.sum() if aligned.sum() else pd.Series(1 / len(aligned), index=aligned.index)
    return returns.dot(aligned), returns, names


def key_portfolio_table(frontier, selected):
    if frontier.empty:
        return pd.DataFrame()
    current = {f"{row['股票']} 權重": row.get("權重", 0.0) for _, row in selected.iterrows()}
    current_stats = {
        "組合": "目前配置",
        "年化報酬": (selected["情境報酬"].fillna(0) * selected["權重"].fillna(0) / 100).sum(),
        "波動度": (selected["波動"].fillna(0) * selected["權重"].fillna(0) / 100).sum(),
        "夏普": 0.0,
    }
    current_stats.update(current)

    min_vol = frontier.loc[frontier["年化波動"].idxmin()].to_dict()
    best_sharpe = frontier.loc[frontier["夏普比率"].idxmax()].to_dict()
    rows = [
        {"組合": "最小波動", "年化報酬": min_vol.pop("年化報酬"), "波動度": min_vol.pop("年化波動"), "夏普": min_vol.pop("夏普比率"), **min_vol},
        {"組合": "最佳夏普", "年化報酬": best_sharpe.pop("年化報酬"), "波動度": best_sharpe.pop("年化波動"), "夏普": best_sharpe.pop("夏普比率"), **best_sharpe},
        current_stats,
    ]
    return pd.DataFrame(rows)


def cumulative_return_table(selected, history_days):
    portfolio_returns, returns, names = current_portfolio_returns(selected, history_days)
    if returns.empty:
        return pd.DataFrame()
    cumulative = (1 + returns).cumprod().subtract(1).multiply(100)
    cumulative["投資組合"] = (1 + portfolio_returns).cumprod().subtract(1).multiply(100)
    return cumulative


def best_weight_map(frontier, selected):
    if frontier.empty:
        return selected_weight_map(selected)
    best = frontier.loc[frontier["夏普比率"].idxmax()]
    weights = {}
    for stock in selected["股票"].astype(str):
        weights[stock] = float(best.get(f"{stock} 權重", 0.0)) / 100
    total = sum(weights.values())
    return {stock: weight / total for stock, weight in weights.items()} if total else selected_weight_map(selected)


def rebalance_table(selected, best_weights):
    rows = []
    for _, row in selected.iterrows():
        stock = str(row["股票"])
        current_weight = (number(row.get("權重")) or 0) / 100
        best_weight = best_weights.get(stock, 0)
        diff = (best_weight - current_weight) * 100
        if diff > 5:
            action = "增持"
        elif diff < -5:
            action = "減持"
        else:
            action = "維持"
        rows.append({
            "股票代碼": stock,
            "公司名稱": row.get("公司", "-"),
            "目前權重": current_weight * 100,
            "最佳權重": best_weight * 100,
            "差異 (pp)": diff,
            "建議操作": action,
            "個股年化報酬": row.get("歷史報酬"),
            "個股年化波動": row.get("波動"),
        })
    return pd.DataFrame(rows)


def report_overview_df(universe):
    if universe.empty:
        return pd.DataFrame()
    df = universe.copy()
    df["股票代碼"] = df["股票"].map(tw_symbol)
    df["檔名"] = df.get("檔名", "")
    df["公司名稱"] = df["公司"]
    df["報告發行日期"] = df["資料日期"]
    df["券商"] = df["券商"]
    df["評等"] = df["建議/推薦"]
    df["目前股價"] = df["目前價"]
    df["目標股價"] = df["目標價"]
    df["潛在漲幅"] = df["漲幅"]
    df["備註"] = df.apply(
        lambda row: row.get("備註") or ("目標價低於現價，暗示下行風險" if pd.notna(row.get("潛在漲幅")) and row.get("潛在漲幅") < 0 else ""),
        axis=1,
    )
    today = pd.Timestamp.today().normalize()
    df["近期報告"] = df["資料日期_dt"].map(lambda value: "✅" if pd.notna(value) and value >= today - pd.Timedelta(days=30) else "—")
    return df[["檔名", "股票代碼", "公司名稱", "報告發行日期", "券商", "評等", "目前股價", "目標股價", "潛在漲幅", "狀態", "備註", "近期報告"]]


def display_percent_df(df, columns):
    result = df.copy()
    for column in columns:
        if column in result:
            result[column] = result[column].map(lambda value: "" if pd.isna(value) else f"{value:.1f}%")
    return result


def render_pdf_report_page():
    st.title("股票報表系統")
    st.caption("上傳 PDF 後會自動判斷檔案是單一個股或多檔個股；多檔會自動拆成多筆資料。")

    uploads = st.file_uploader(
        "上傳一個或多個 PDF",
        type=["pdf"],
        accept_multiple_files=True,
        key="auto_uploads",
    )

    col_a, col_b = st.columns([1, 1])
    if col_a.button("處理上傳檔案", type="primary", key="auto_process"):
        if uploads:
            added, pending, skipped = process_tab_uploads(
                uploads,
                "auto_rows",
                "auto_pending",
                "auto_processed_files",
                parse_reports,
            )
            st.success(f"已加入 {added} 筆，待確認 {pending} 筆，重複略過 {skipped} 筆")
        else:
            st.warning("請先選擇 PDF")

    if col_b.button("清除全部資料", key="auto_clear"):
        st.session_state.auto_rows = []
        st.session_state.auto_pending = []
        st.session_state.auto_processed_files = set()
        st.rerun()

    render_manual_add("auto_rows", "auto")
    render_pending("auto_pending", "auto_rows", "auto")
    render_table_and_chart("auto_rows", chart_title="正漲幅彙整圖表", positive_only=True)


def render_stock_picker_page():
    st.title("📈 券商研究報告分析工具")
    init_stock_database()

    base_rows = st.session_state.get("auto_rows", [])
    brokers = sorted({row.get("券商", "-") for row in base_rows + SAMPLE_ROWS if row.get("券商")})

    with st.sidebar:
        st.header("⚙️ 參數設定")
        st.header("📁 上傳報告")
        picker_uploads = st.file_uploader(
            "上傳 PDF / Word / Excel / CSV / Markdown",
            type=["pdf"],
            accept_multiple_files=True,
            key="picker_uploads",
        )
        if st.button("處理上傳報告", key="picker_process_uploads"):
            if picker_uploads:
                st.session_state.auto_rows = []
                st.session_state.auto_pending = []
                st.session_state.auto_processed_files = set()
                added, pending, skipped = process_tab_uploads(
                    picker_uploads,
                    "auto_rows",
                    "auto_pending",
                    "auto_processed_files",
                    parse_reports,
                )
                st.success(f"已加入 {added} 筆，待確認 {pending} 筆，重複略過 {skipped} 筆")
            else:
                st.warning("請先選擇檔案")

        st.divider()
        st.header("📊 分析設定")
        scenario = st.selectbox("情境選擇", ["中性", "樂觀", "悲觀"], index=0, help="樂觀：目標價完全實現；中性：85%；悲觀：65%")
        history_days = st.slider("歷史資料天數", min_value=20, max_value=1200, value=365, step=5)
        forecast_days = st.slider("預測天數", min_value=1, max_value=365, value=90, step=5)
        recent_only = st.checkbox("顯示近期報告", value=False)
        recent_days = st.number_input("近期報告天數", min_value=1, max_value=365, value=90, step=5, disabled=not recent_only)
        use_sample = st.checkbox("使用範例資料", value=not bool(base_rows))

        st.header("🗄️ 本機資料庫")
        revenue_count, institutional_count = database_counts()
        st.caption(f"月營收 {revenue_count:,} 筆；法人買賣 {institutional_count:,} 筆")
        revenue_csv = st.file_uploader("匯入月營收 CSV", type=["csv"], key="monthly_revenue_csv")
        institutional_csv = st.file_uploader("匯入法人買賣 CSV", type=["csv"], key="institutional_csv")
        if st.button("匯入資料庫", key="import_stock_database", use_container_width=True):
            imported_revenue = 0
            imported_institutional = 0
            if revenue_csv:
                imported_revenue = save_monthly_revenue_to_db(read_uploaded_csv(revenue_csv), source="csv")
            if institutional_csv:
                imported_institutional = save_institutional_to_db(read_uploaded_csv(institutional_csv), source="csv")
            st.cache_data.clear()
        st.success(f"已匯入月營收 {imported_revenue:,} 筆、法人買賣 {imported_institutional:,} 筆")

        st.header("🔎 智慧選股")
        request_finmind_update = st.checkbox("缺資料時用 FinMind 更新資料庫", value=False)
        finmind_password = ""
        finmind_password_ok = False
        configured_password = configured_finmind_password()
        if request_finmind_update:
            finmind_password = st.text_input("FinMind 使用密碼", type="password", help="需符合 Streamlit secrets 裡的 FINMIND_UPDATE_PASSWORD。")
            if not configured_password:
                st.warning("尚未設定 FINMIND_UPDATE_PASSWORD，FinMind 更新功能已停用。")
            elif finmind_password == configured_password:
                finmind_password_ok = True
                st.success("FinMind 更新已解鎖。")
            elif finmind_password:
                st.warning("FinMind 使用密碼不正確，將只讀本機資料庫。")
        allow_finmind_update = request_finmind_update and finmind_password_ok
        finmind_token = st.text_input("FinMind Token（可留空）", type="password", disabled=not allow_finmind_update, help="只有勾選並輸入正確使用密碼後才會使用 FinMind；留空會嘗試公開額度。")
        apply_strategy = st.checkbox("套用策略交集", value=True)
        low_base_limit = st.slider("低基期位置上限 (%)", min_value=0.0, max_value=100.0, value=35.0, step=5.0, disabled=not apply_strategy)
        min_volume_lots = st.number_input("每日成交張數下限", min_value=0, max_value=100000, value=200, step=50, disabled=not apply_strategy)
        min_market_cap_million = st.number_input("市值下限（百萬元）", min_value=0, max_value=10000000, value=200000, step=10000, disabled=not apply_strategy)
        max_volatility = st.slider("波動上限 (%)", min_value=1.0, max_value=120.0, value=55.0, step=1.0)
        min_return = st.slider("情境報酬下限 (%)", min_value=-50.0, max_value=200.0, value=0.0, step=1.0)
        max_drawdown_limit = st.slider("最大回撤下限 (%)", min_value=-100.0, max_value=0.0, value=-35.0, step=1.0)
        max_stocks = st.number_input("最多選入股票數量", min_value=1, max_value=30, value=8, step=1)
        weight_mode = st.selectbox("投資組合權重模式", ["等權重", "依智慧分數", "依情境報酬"])
        stock_filter = st.text_input("篩選股票代碼", placeholder="例如 2308, 6805")
        broker_filter = st.multiselect("篩選券商", brokers)

    overview_rows = base_rows + pending_report_rows()
    all_report_universe = build_selection_universe(
        overview_rows,
        use_sample,
        False,
        recent_days,
        stock_filter,
        broker_filter,
        history_days,
        scenario,
    )
    report_universe = build_selection_universe(
        base_rows,
        use_sample,
        recent_only,
        recent_days,
        stock_filter,
        broker_filter,
        history_days,
        scenario,
    )
    stock_universe = aggregate_stock_universe(
        report_universe,
        history_days,
        scenario,
        low_base_limit,
        min_volume_lots,
        min_market_cap_million,
        finmind_token,
        allow_finmind_update,
    )
    selected_raw = filter_selection(
        stock_universe,
        min_return,
        max_volatility,
        max_drawdown_limit,
        max_stocks,
        apply_strategy,
        min_volume_lots,
        min_market_cap_million,
        low_base_limit,
    )
    selected = add_weights(selected_raw, weight_mode)

    overview_tab, stock_tab, portfolio_tab, smart_tab = st.tabs(["📋 報告總覽", "🔍 個股深入分析", "📦 投資組合分析", "🔬 智慧選股"])

    with overview_tab:
        st.subheader(f"報告彙整表（{scenario}情境）")
        overview = report_overview_df(all_report_universe)
        if overview.empty:
            st.info("尚無報告資料，請上傳檔案或勾選使用範例資料")
        else:
            display = overview.copy()
            display["目前股價"] = display["目前股價"].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
            display["目標股價"] = display["目標股價"].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
            display["潛在漲幅"] = display["潛在漲幅"].map(lambda value: "" if pd.isna(value) else f"{value:.1f}%")
            st.dataframe(display, use_container_width=True, hide_index=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("平均潛在漲幅", f"{overview['潛在漲幅'].dropna().mean():.1f}%" if overview["潛在漲幅"].notna().any() else "—")
            m2.metric("正報酬筆數", int((overview["潛在漲幅"].fillna(0) > 0).sum()))
            m3.metric("近期報告數", int((overview["近期報告"] == "✅").sum()))
            m4.metric("報告總數", len(overview))

            st.subheader("各股潛在漲幅比較")
            chart = overview.dropna(subset=["潛在漲幅"]).set_index("股票代碼")["潛在漲幅"]
            if chart.empty:
                st.info("沒有可繪製的潛在漲幅資料")
            else:
                st.bar_chart(chart)

    with stock_tab:
        st.subheader("個股深入分析")
        if stock_universe.empty:
            st.info("尚無可分析股票")
        else:
            choices = [f"{tw_symbol(row['股票'])} / {row.get('公司', '-')}" for _, row in stock_universe.iterrows()]
            selected_label = st.selectbox("選擇個股", choices, key="deep_stock_choice")
            stock_code = selected_label.split("/")[0].replace(".TW", "").strip()
            row = stock_universe[stock_universe["股票"].astype(str) == stock_code].iloc[0]
            related_reports = report_universe[report_universe["股票"].astype(str) == stock_code]
            hist = analysis_history(row, history_days)
            returns = daily_returns(hist)
            stats = history_metrics(row["股票"], history_days)
            annual_return = (returns["日報酬率 (%)"].mean() * 252) if not returns.empty else stats["歷史報酬"]
            annual_volatility = (returns["日報酬率 (%)"].std() * (252 ** 0.5)) if not returns.empty else stats["波動"]
            sharpe = annual_return / annual_volatility if annual_volatility else 0

            st.markdown(f"### 分析：{tw_symbol(row['股票'])}")
            left, right = st.columns([1, 1.35])
            with left:
                upside_text = "" if pd.isna(row.get("漲幅")) else f"{row.get('漲幅'):.1f}%"
                st.write(f"**公司名稱：** {row.get('公司', '-')}")
                st.write(f"**目前股價：** {format_num(row.get('目前價'))}")
                st.write(f"**平均目標價（{scenario}）：** {format_num(row.get('情境目標價')) or format_num(row.get('目標價'))}")
                st.write(f"**潛在漲幅：** {upside_text}")
                st.write(f"**評等分佈：** {row.get('建議/推薦') or '-'}")
            with right:
                detail = related_reports[["資料日期", "券商", "建議/推薦", "目標價", "情境報酬"]].copy()
                detail = detail.rename(columns={"資料日期": "報告發行日期", "建議/推薦": "評等", "目標價": "目標股價", "情境報酬": "預期報酬"})
                st.dataframe(format_analysis_df(detail), use_container_width=True, hide_index=True)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("年化報酬率", "" if annual_return is None or pd.isna(annual_return) else f"{annual_return:.1f}%")
            k2.metric("年化波動度", "" if annual_volatility is None or pd.isna(annual_volatility) else f"{annual_volatility:.1f}%")
            k3.metric("夏普比率", f"{sharpe:.2f}")
            k4.metric("最大回撤", "" if pd.isna(row.get("最大回撤")) else f"{row.get('最大回撤'):.1f}%")

            st.subheader("預測走勢")
            forecast = forecast_history(row, hist, forecast_days, scenario)
            trend = pd.concat([
                hist.rename(columns={"收盤價": "歷史股價"}),
                forecast,
            ], axis=1)
            st.line_chart(trend)

            st.subheader("日報酬")
            if returns.empty:
                st.info("沒有日報酬資料")
            else:
                st.bar_chart(returns.tail(90))

    with portfolio_tab:
        st.subheader("投資組合分析")
        if selected.empty:
            st.info("尚無投資組合資料")
        else:
            default_codes = selected["股票"].astype(str).tolist()
            chosen_codes = st.multiselect("選擇納入投資組合的股票", stock_universe["股票"].astype(str).tolist(), default=default_codes)
            portfolio_rows = stock_universe[stock_universe["股票"].astype(str).isin(chosen_codes)]
            if portfolio_rows.empty:
                st.info("請至少選擇一檔股票")
            else:
                portfolio_rows = add_weights(portfolio_rows.copy(), "等權重")
                left_weight, right_weight = st.columns([1, 2])
                raw_weights = {}
                with left_weight:
                    st.subheader("手動設定權重")
                    equal_weight = int(round(100 / len(portfolio_rows))) if len(portfolio_rows) else 0
                    for _, item in portfolio_rows.iterrows():
                        stock = str(item["股票"])
                        label = f"{tw_symbol(stock)} ({item.get('公司', '-')})"
                        raw_weights[stock] = st.slider(
                            label,
                            min_value=0,
                            max_value=100,
                            value=equal_weight,
                            step=1,
                            key=f"portfolio_weight_{stock}",
                        )

                weight_total = sum(raw_weights.values())
                if weight_total <= 0:
                    normalized_weights = {str(row["股票"]): 100 / len(portfolio_rows) for _, row in portfolio_rows.iterrows()}
                else:
                    normalized_weights = {stock: value / weight_total * 100 for stock, value in raw_weights.items()}
                portfolio_rows["權重"] = portfolio_rows["股票"].astype(str).map(normalized_weights).fillna(0)

                current_returns, returns, names = current_portfolio_returns(portfolio_rows, history_days)
                frontier, _ = simulate_frontier(portfolio_rows, history_days)
                current_stats = portfolio_stats(returns, selected_weight_map(portfolio_rows))

                with right_weight:
                    st.subheader("目前投資組合指標")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("年化預期報酬", f"{current_stats['年化報酬']:.1f}%")
                    c2.metric("年化波動度", f"{current_stats['年化波動']:.1f}%")
                    c3.metric("夏普比率", f"{current_stats['夏普比率']:.2f}")

                    st.subheader("持股權重")
                    labels = [f"{tw_symbol(row['股票'])} {row.get('公司', '-')}" for _, row in portfolio_rows.iterrows()]
                    values = portfolio_rows["權重"].astype(float).tolist()
                    fig = go.Figure(
                        data=[
                            go.Pie(
                                labels=labels,
                                values=values,
                                hole=0.42,
                                textinfo="label+percent",
                                sort=False,
                            )
                        ]
                    )
                    fig.update_layout(
                        height=430,
                        margin=dict(l=8, r=8, t=12, b=12),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    if abs(weight_total - 100) > 0.01:
                        st.caption(f"滑桿合計 {weight_total:.0f}%，圖表與後續分析已自動換算為 100%。")

                st.subheader("效率前緣")
                if frontier.empty:
                    st.info("歷史資料不足，無法建立效率前緣")
                else:
                    st.markdown("### 效率前緣（Monte Carlo 3,000 組合）")
                    st.plotly_chart(build_frontier_chart(frontier, current_stats), use_container_width=True)
                    st.caption(
                        "每個點是一組隨機權重投資組合；白線是在相同或更低波動下能取得最高報酬的組合，也就是效率前緣。"
                    )
                    with st.expander("這張圖怎麼算？", expanded=True):
                        st.markdown(
                            """
                            1. 先用每檔股票的歷史收盤價計算每日報酬率：`今日收盤價 / 昨日收盤價 - 1`。
                            2. Monte Carlo 會隨機產生 3,000 組權重，且每組權重都會正規化成合計 100%。
                            3. 每組投資組合的每日報酬 = 各股票每日報酬 × 對應權重後加總。
                            4. 年化報酬 = 投資組合每日平均報酬 × 252 × 100。
                            5. 年化波動度 = 投資組合每日報酬標準差 × √252 × 100。
                            6. 夏普比率 = 年化報酬 ÷ 年化波動度；目前未扣無風險利率。

                            圖上的 **最佳夏普** 是夏普比率最高的隨機組合，**最小波動** 是年化波動度最低的組合，**目前配置** 是你在左側權重滑桿設定後換算出的組合。
                            """
                        )

                st.subheader("關鍵組合比較")
                comparison = key_portfolio_table(frontier, portfolio_rows)
                if comparison.empty:
                    st.info("沒有關鍵組合資料")
                else:
                    st.dataframe(display_percent_df(comparison, ["年化報酬", "波動度"] + [col for col in comparison.columns if col.endswith("權重")]), use_container_width=True, hide_index=True)

                st.subheader("累積報酬走勢")
                cumulative = cumulative_return_table(portfolio_rows, history_days)
                if cumulative.empty:
                    st.info("沒有累積報酬資料")
                else:
                    st.line_chart(cumulative)

                st.subheader("再平衡建議")
                best_weights = best_weight_map(frontier, portfolio_rows)
                rebalance = rebalance_table(portfolio_rows, best_weights)
                st.dataframe(display_percent_df(rebalance, ["目前權重", "最佳權重", "差異 (pp)", "個股年化報酬", "個股年化波動"]), use_container_width=True, hide_index=True)
                if not rebalance.empty:
                    st.bar_chart(rebalance.set_index("股票代碼")["差異 (pp)"])

                st.subheader("投資金額模擬")
                total_amount = st.number_input("總投資金額（NT$）", min_value=10000, max_value=100000000, value=1000000, step=10000)
                use_best = st.radio("使用哪組權重？", ["目前配置", "最佳夏普配置"], horizontal=True)
                weights = best_weights if use_best == "最佳夏普配置" else selected_weight_map(portfolio_rows)
                simulator_rows = []
                buy_fee = 0.001425
                sell_tax = 0.003
                for _, item in portfolio_rows.iterrows():
                    stock = str(item["股票"])
                    price = number(item.get("目前價")) or 0
                    weight = weights.get(stock, 0)
                    target_amount = total_amount * weight
                    shares = int(target_amount // price // 1000 * 1000) if price else 0
                    invested = shares * price
                    simulator_rows.append({
                        "股票代碼": tw_symbol(stock),
                        "公司名稱": item.get("公司", "-"),
                        "權重": weight * 100,
                        "目標金額": target_amount,
                        "目前股價": price,
                        "應買張數(整張)": shares // 1000,
                        "實際股數": shares,
                        "實際投入金額": invested,
                        "未用餘額": max(0, target_amount - invested),
                        "買進手續費": invested * buy_fee,
                    })
                simulator = pd.DataFrame(simulator_rows)
                actual_invested = simulator["實際投入金額"].sum() if not simulator.empty else 0
                fees = simulator["買進手續費"].sum() if not simulator.empty else 0
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("總投資金額", f"NT${total_amount:,.0f}")
                s2.metric("實際投入", f"NT${actual_invested:,.0f}")
                s3.metric("買進手續費", f"NT${fees:,.0f}")
                s4.metric("賣出費用（假設）", f"NT${actual_invested * (buy_fee + sell_tax):,.0f}")
                st.dataframe(format_analysis_df(simulator), use_container_width=True, hide_index=True)
                if not simulator.empty:
                    allocation = simulator.set_index("股票代碼")["實際投入金額"]
                    allocation["未使用餘額"] = max(0, total_amount - actual_invested)
                    st.bar_chart(allocation)

    with smart_tab:
        st.subheader("智慧選股")
        if stock_universe.empty:
            st.info("尚無候選股票")
        else:
            st.markdown(
                """
                **策略邏輯：** 先以上傳報告形成股票池；三率用 yfinance 季財報，月營收與外資+投信買超優先讀 SQLite 本機資料庫，成交量與市值用 yfinance，最後取策略條件交集。
                """
            )
            with st.expander("策略條件怎麼判斷？", expanded=True):
                st.markdown(
                    """
                    1. **低基期**：用歷史區間內的收盤價位置計算，`(目前價 - 區間最低價) / (區間最高價 - 區間最低價) × 100`，低於左側設定門檻就通過。
                    2. **三率三升**：用 yfinance 季財報計算毛利率、營益率、淨利率，三者都比前一季上升就通過。
                    3. **營收條件三選一**：用本機資料庫的月營收判斷 `月營收創高`、`月營收 MoM +10%`、`累積 YoY +10%` 任一項；資料可由 CSV 匯入，或勾選並輸入正確密碼後用 FinMind 補缺漏。
                    4. **法人買入**：用本機資料庫的法人買賣表計算最近可得交易日的 `外資 + 投信` 買超張數，大於 0 就通過；資料可由 CSV 匯入，或勾選並輸入正確密碼後用 FinMind 補缺漏。
                    5. **成交量**：用最近 20 個交易日平均成交股數換算成張數，門檻預設 200 張。
                    6. **市值**：用 yfinance 的 marketCap 換算成百萬元，門檻預設 200,000 百萬元。
                    """
                )

            feature_cols = [
                "股票", "公司", "券商", "報告筆數", "目前價", "情境報酬", "建議/推薦", "目標價",
                "低基期位置", "低基期", "三率三升", "營收條件", "營收特徵", "法人買入",
                "營收MoM", "累積YoY", "外資投信買超張數", "平均成交張數", "市值百萬元",
                "策略通過", "三率原因", "營收原因", "法人原因", "策略資料來源", "智慧分數",
            ]
            existing_feature_cols = [col for col in feature_cols if col in stock_universe.columns]
            with st.expander("各股策略檢核表（展開查看）", expanded=True):
                st.dataframe(format_analysis_df(stock_universe[existing_feature_cols]), use_container_width=True, hide_index=True)

            with st.expander("各股完整分析資料"):
                full_cols = ["股票", "公司", "券商", "報告筆數", "目前價", "情境報酬", "建議/推薦", "目標價", "最高目標價", "歷史報酬", "波動", "最大回撤", "智慧分數"]
                full_cols = [col for col in full_cols if col in stock_universe.columns]
                st.dataframe(format_analysis_df(stock_universe[full_cols]), use_container_width=True, hide_index=True)

            st.subheader(f"篩選結果：{len(selected)} 檔股票入選（上限 {int(max_stocks)} 檔）")
            if selected.empty:
                st.warning("目前沒有股票同時符合報告與策略交集。可以先查看上方檢核表，確認是三率/營收/法人文字沒抓到，或是成交量、市值、低基期門檻太嚴。")
            else:
                cols = [
                    "股票", "公司", "券商", "資料日期", "建議/推薦", "目前價", "目標價", "情境報酬",
                    "低基期位置", "營收特徵", "營收MoM", "累積YoY", "外資投信買超張數",
                    "平均成交張數", "市值百萬元", "智慧分數", "權重",
                ]
                st.dataframe(format_analysis_df(selected[cols]), use_container_width=True, hide_index=True)
                st.bar_chart(selected.set_index("股票")["智慧分數"])


if __name__ == "__main__":
    init_tab_state()
    st.session_state.setdefault("auto_rows", [])
    st.session_state.setdefault("auto_pending", [])
    st.session_state.setdefault("auto_processed_files", set())

    render_stock_picker_page()
