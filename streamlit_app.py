import re
from io import BytesIO

import fitz
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="股票報表系統", layout="wide")

BROKERS = [
    "元大投顧", "元大證券", "凱基投顧", "凱基證券", "富邦投顧", "富邦證券",
    "永豐投顧", "永豐金證券", "國泰證券", "國泰投顧", "群益投顧", "群益證券",
    "統一投顧", "統一證券", "兆豐投顧", "兆豐證券", "第一金投顧", "第一金證券",
    "玉山投顧", "玉山證券", "台新投顧", "台新證券", "中信投顧", "中國信託證券",
    "華南永昌", "華南永昌證券", "元富投顧", "元富證券", "日盛投顧", "日盛證券",
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
    "華南永昌": "華南永昌",
    "元富": "元富",
    "國票": "國票",
    "宏遠": "宏遠",
    "新光": "新光",
    "合庫": "合庫",
    "康和": "康和",
    "日盛": "日盛",
}


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
        if 1900 <= value <= 2100:
            continue
        if any(key in before for key in ["目標", "target", "price", "tp"]):
            continue
        return match.group(0)
    return ""


def segments_after_pattern(text, label_pattern, length=100):
    pattern = rf"{label_pattern}\s*(?:至|為|到|:|：|=)?\s*(?:NT\$|TWD|新台幣|台幣|\$)?\s*"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        yield text[match.end():match.end() + length]


def price_candidates(segment, min_value=50):
    values = []
    for match in re.finditer(r"\d+(?:\.\d+)?", segment):
        before = segment[max(0, match.start() - 8):match.start()]
        after = segment[match.end():match.end() + 8]
        context = before + match.group(0) + after

        if re.search(r"\d{2,4}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{1,4}", context):
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
        for segment in segments_after_pattern(text, label, 120):
            stop = re.search(
                r"EPS|收盤|大盤|市值|股本|日期|評等|QoQ|YoY|毛利|營收|電話|地址|傳真|"
                r"Email|E-mail|電子信箱|免責|聲明|服務據點|研究員|分析師",
                segment,
                re.I,
            )
            scoped = segment[:stop.start()] if stop else segment
            candidates.extend(price_candidates(scoped, 50))

    return max(candidates) if candidates else None


def clean_broker(value):
    text = re.sub(r"\s+", " ", value or "").strip()
    return re.split(r"[，,。；;:/：｜|]", text)[0].strip()[:30]


def extract_broker(text, filename=""):
    combined = f"{filename}\n{text}"[:12000]
    compact = re.sub(r"\s+", "", combined).lower()
    for broker in BROKERS:
        if broker.lower() in combined.lower() or re.sub(r"\s+", "", broker).lower() in compact:
            return broker

    broker_context = compact[:5000] + compact[-4000:]
    for alias, display_name in BROKER_ALIASES.items():
        compact_alias = re.sub(r"\s+", "", alias).lower()
        if compact_alias not in broker_context:
            continue
        alias_index = broker_context.find(compact_alias)
        nearby = broker_context[max(0, alias_index - 80):alias_index + 120]
        if any(keyword in nearby for keyword in ["投顧", "證券", "研究", "報告", "電話", "地址", "analyst", "research"]):
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
    return {
        "file_name": uploaded_file.name,
        "stock": extract_stock_code(text),
        "target": extract_target_price(text),
        "broker": extract_broker(text, uploaded_file.name),
        "date": extract_report_date(text),
        "raw_text": text,
    }


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
    return (
        row.get("股票", ""),
        row.get("券商", "-"),
        row.get("資料日期", "-"),
        float(row.get("目標價", 0)),
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
        parsed = parse_report(uploaded_file)
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


init_state()

st.title("股票報表系統")

with st.sidebar:
    st.subheader("上傳 PDF")
    uploads = st.file_uploader("選擇一個或多個 PDF", type=["pdf"], accept_multiple_files=True)
    if st.button("處理上傳檔案", type="primary", use_container_width=True):
        if uploads:
            added, pending, skipped = process_uploads(uploads)
            st.success(f"已加入 {added} 筆，待確認 {pending} 筆，重複略過 {skipped} 筆")
        else:
            st.warning("請先選擇 PDF")

    if st.button("清除全部資料", use_container_width=True):
        st.session_state.rows = []
        st.session_state.pending = []
        st.session_state.processed_files = set()
        st.cache_data.clear()
        st.rerun()

st.subheader("手動新增")
col1, col2, col3, col4, col5, col6 = st.columns(6)
manual_stock = col1.text_input("股票", key="manual_stock")
manual_company = col2.text_input("公司", key="manual_company")
manual_broker = col3.text_input("券商", key="manual_broker")
manual_date = col4.text_input("資料日期", key="manual_date")
manual_current = col5.text_input("目前價", key="manual_current")
manual_target = col6.text_input("目標價", key="manual_target")

if st.button("新增", type="primary"):
    current = number(manual_current)
    if current is None and manual_stock:
        quote = fetch_quote(manual_stock)
        current = quote["price"]
        if quote["name"] and not manual_company:
            manual_company = quote["name"]
    target = number(manual_target)
    if add_row(manual_stock, manual_company, manual_broker, manual_date, current, target):
        st.success("已新增")
    else:
        st.warning("資料不足或重複")

if st.session_state.pending:
    st.subheader("待確認資料")
    for index, item in enumerate(st.session_state.pending):
        with st.expander(f"{item.get('stock') or '-'} / {item.get('broker') or '-'} / {item.get('date') or '-'} / 目 {format_num(item.get('target'))}"):
            st.caption(item.get("reason", ""))
            quote = fetch_quote(item["stock"]) if item.get("stock") else {"price": None, "name": "", "symbol": ""}
            st.write(f"Yahoo 現價：{format_num(quote['price']) or '抓不到'}")
            c1, c2 = st.columns([1, 1])
            manual_price = c1.text_input("手動目前價", key=f"pending_price_{index}")
            if c2.button("加入表格", key=f"add_pending_{index}"):
                price = quote["price"] or number(manual_price)
                if add_row(item["stock"], quote["name"], item["broker"], item["date"], price, item["target"]):
                    st.session_state.pending.pop(index)
                    st.rerun()
                else:
                    st.warning("資料不足或重複")
            with st.expander("PDF 文字"):
                st.text_area("內容", item.get("raw_text", ""), height=180, key=f"raw_{index}")

left, right = st.columns([3, 1])

with left:
    st.subheader("資料表")
    if st.session_state.rows:
        df = pd.DataFrame(st.session_state.rows)
        df = df.sort_values("漲幅", ascending=not st.session_state.sort_desc)
        display_df = df.copy()
        display_df["目前價"] = display_df["目前價"].map(lambda value: f"{value:.2f}")
        display_df["目標價"] = display_df["目標價"].map(lambda value: f"{value:.2f}")
        display_df["漲幅"] = display_df["漲幅"].map(lambda value: f"{value:.1f}%")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("尚無資料")

with right:
    st.subheader("漲幅圖表")
    if st.session_state.rows:
        chart_df = pd.DataFrame(st.session_state.rows)[["股票", "漲幅"]]
        st.bar_chart(chart_df.set_index("股票"))
    else:
        st.info("尚無資料")
