import html

import pandas as pd
import streamlit as st

import streamlit_app as core


SMART_PICKER_DB_IMPORT_PASSWORD = "330215dlEEVB"


def init_smart_state():
    core.init_tab_state()
    st.session_state.setdefault("auto_rows", [])
    st.session_state.setdefault("auto_pending", [])
    st.session_state.setdefault("auto_processed_files", set())
    st.session_state.setdefault("smart_picker_db_import_requested", False)


def render_database_controls():
    st.header("本機資料庫")
    revenue_count, institutional_count = core.database_counts()
    st.caption(f"月營收 {revenue_count:,} 筆；法人買賣 {institutional_count:,} 筆")

    revenue_csv = st.file_uploader("匯入月營收 CSV", type=["csv"], key="smart_monthly_revenue_csv")
    institutional_csv = st.file_uploader("匯入法人買賣 CSV", type=["csv"], key="smart_institutional_csv")

    if st.button("匯入資料庫", key="smart_import_stock_database", use_container_width=True):
        imported_revenue = 0
        imported_institutional = 0
        if revenue_csv:
            imported_revenue = core.save_monthly_revenue_to_db(core.read_uploaded_csv(revenue_csv), source="csv")
        if institutional_csv:
            imported_institutional = core.save_institutional_to_db(core.read_uploaded_csv(institutional_csv), source="csv")
        st.cache_data.clear()
        st.success(f"已匯入月營收 {imported_revenue:,} 筆、法人買賣 {imported_institutional:,} 筆")


def finmind_update_controls():
    request_update = st.checkbox("缺資料時用 FinMind 更新資料庫", value=False)
    if not request_update:
        return "", False

    configured_password = core.configured_finmind_password()
    password = st.text_input(
        "FinMind 使用密碼",
        type="password",
        help="輸入正確使用密碼後，才會允許用 FinMind 補齊缺漏資料。",
    )

    if not configured_password:
        st.warning("尚未設定 FINMIND_UPDATE_PASSWORD，FinMind 更新功能已停用。")
        return "", False
    if not password:
        st.info("請先輸入 FinMind 使用密碼，才會啟用更新。")
        return "", False
    if password != configured_password:
        st.warning("FinMind 使用密碼不正確，將只讀本機資料庫。")
        return "", False

    st.success("FinMind 更新已解鎖。")
    token = st.text_input(
        "FinMind API Token（可留空）",
        type="password",
        help="可填 FinMind API token；留空會嘗試使用公開額度。",
    )
    return token, True


def render_strategy_explanation():
    st.markdown(
        """
        **策略邏輯：** 先以上傳報告形成股票池；三率用 yfinance 季財報，月營收與外資+投信買超優先讀 SQLite 本機資料庫，成交量與市值用 yfinance，最後取策略條件交集。
        """
    )
    with st.expander("策略條件怎麼判斷？", expanded=True):
        st.markdown(
            """
            1. **低基期**：`(目前價 - 區間最低價) / (區間最高價 - 區間最低價) x 100`，低於左側門檻就通過。
            2. **三率三升**：用 yfinance 季財報計算毛利率、營益率、淨利率，三者都比前一季上升就通過。
            3. **營收條件三選一**：用本機資料庫月營收判斷 `月營收創高`、`月營收 MoM +10%`、`累積 YoY +10%` 任一項。
            4. **法人買入**：用本機資料庫法人買賣表計算最近可得交易日的 `外資 + 投信` 買超張數，大於 0 就通過。
            5. **成交量**：用最近 20 個交易日平均成交股數換算成張數。
            6. **市值**：用 yfinance 的 marketCap 換算成百萬元。
            """
        )


def smart_num(value, default=0.0):
    parsed = core.number(value)
    if parsed is None or pd.isna(parsed):
        return default
    return float(parsed)


def smart_text(value, default="-"):
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def smart_pct_text(value, digits=1):
    parsed = core.number(value)
    if parsed is None or pd.isna(parsed):
        return "-"
    return f"{parsed:.{digits}f}%"


def smart_stage(row):
    score = smart_num(row.get("智慧分數"))
    strategy_pass = bool(row.get("策略通過"))
    low_base = bool(row.get("低基期"))
    revenue = bool(row.get("營收條件"))
    institutional = bool(row.get("法人買入"))
    if strategy_pass or (score >= 90 and revenue and institutional):
        return "Stage 2 — 主升段", "stage-hot"
    if score >= 60 or low_base:
        return "Stage 1 — 潛伏段", "stage-base"
    if smart_num(row.get("情境報酬")) < 0 or score < 20:
        return "Watch — 風險觀察", "stage-risk"
    return "Stage 0 — 觀察池", "stage-watch"


def smart_badge(text, kind="neutral"):
    return f'<span class="smart-badge {kind}">{html.escape(str(text))}</span>'


def smart_signal_badges(row):
    badges = []
    if bool(row.get("低基期")):
        badges.append(smart_badge(f"低基期 {smart_pct_text(row.get('低基期位置'), 0)}", "gold"))
    if bool(row.get("三率三升")):
        badges.append(smart_badge("三率三升", "blue"))
    if bool(row.get("營收條件")):
        badges.append(smart_badge(smart_text(row.get("營收特徵"), "營收條件"), "green"))
    if bool(row.get("法人買入")):
        lots = smart_num(row.get("外資投信買超張數"))
        badges.append(smart_badge(f"法人買超 {lots:,.0f} 張", "cyan"))
    upside = smart_num(row.get("情境報酬"), None)
    if upside is not None:
        badges.append(smart_badge(f"情境報酬 {upside:+.1f}%", "purple" if upside >= 0 else "red"))
    if not badges:
        badges.append(smart_badge("資料待補", "neutral"))
    return "".join(badges)


def smart_rating_stars(row):
    score = core.rating_score(row.get("建議/推薦"))
    stars = max(1, min(3, int(round(max(score, 0) / 7)) or 1))
    return "★" * stars + "☆" * (3 - stars)


def smart_table_html(df):
    if df.empty:
        return ""
    max_score = max(100.0, float(df["智慧分數"].fillna(0).max()) if "智慧分數" in df else 100.0)
    rows = []
    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        stage_label, stage_class = smart_stage(row)
        score = smart_num(row.get("智慧分數"))
        score_width = max(4, min(100, score / max_score * 100))
        code = html.escape(smart_text(row.get("股票")))
        company = html.escape(smart_text(row.get("公司")))
        broker = html.escape(smart_text(row.get("券商")))
        price = smart_num(row.get("目前價"), None)
        price_text = "-" if price is None else f"{price:,.2f}"
        score_delta = smart_pct_text(row.get("情境報酬"))
        target = smart_num(row.get("目標價"), None)
        target_text = "-" if target is None else f"{target:,.2f}"
        low_base = smart_pct_text(row.get("低基期位置"), 0)
        volume = smart_num(row.get("平均成交張數"), None)
        volume_text = "-" if volume is None else f"{volume:,.0f}"
        rows.append(
            f"""
            <tr>
                <td class="rank">{rank}</td>
                <td>
                    <div class="stock-code">{code}</div>
                    <div class="stock-name">{company}</div>
                </td>
                <td class="price">{price_text}</td>
                <td><span class="stage-pill {stage_class}">{html.escape(stage_label)}</span></td>
                <td class="signals">{smart_signal_badges(row)}</td>
                <td>
                    <div class="score-wrap">
                        <strong>{score:.0f}</strong>
                        <span>{score_delta}</span>
                    </div>
                    <div class="score-bar"><i style="width:{score_width:.0f}%"></i></div>
                </td>
                <td>
                    <div class="stars">{smart_rating_stars(row)}</div>
                    <div class="rating-text">{html.escape(smart_text(row.get("建議/推薦"), "未評"))}</div>
                </td>
                <td>{target_text}</td>
                <td>{low_base}</td>
                <td>{volume_text}</td>
                <td class="broker">{broker}</td>
            </tr>
            """
        )
    return f"""
    <div class="smart-table-shell">
        <table class="smart-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>股票</th>
                    <th>現價</th>
                    <th>Weinstein 階段</th>
                    <th>觸發訊號</th>
                    <th>評分</th>
                    <th>評級</th>
                    <th>目標價</th>
                    <th>低基期</th>
                    <th>量能</th>
                    <th>券商</th>
                </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
    """


def render_smart_dashboard(stock_universe, selected, max_stocks):
    st.markdown(
        """
        <style>
        .smart-lab {
            padding: 18px 20px;
            border: 1px solid rgba(0, 209, 255, .28);
            border-radius: 10px;
            background:
                radial-gradient(circle at 50% -30%, rgba(0, 209, 255, .18), transparent 34%),
                linear-gradient(135deg, #061426 0%, #020810 62%, #030f14 100%);
            color: #dff8ff;
            box-shadow: inset 0 0 0 1px rgba(0, 255, 195, .08);
        }
        .smart-lab-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 18px;
            font-weight: 700;
        }
        .market-dot {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            background: #18ffc2;
            box-shadow: 0 0 16px #18ffc2;
        }
        .market-note {
            color: #00ffc8;
            background: rgba(0, 255, 153, .10);
            border: 1px solid rgba(0, 255, 153, .18);
            border-radius: 6px;
            padding: 7px 12px;
        }
        .smart-stat-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
        }
        .smart-stat {
            padding: 17px 20px;
            border: 1px solid rgba(0, 178, 255, .28);
            border-radius: 10px;
            background: rgba(8, 26, 58, .92);
        }
        .smart-stat strong {
            display: block;
            color: #00d9ff;
            font-size: 2rem;
            line-height: 1;
        }
        .smart-stat span {
            display: block;
            margin-top: 8px;
            color: #67a6c7;
            font-size: .9rem;
        }
        .smart-table-shell {
            overflow-x: auto;
            border: 1px solid rgba(0, 185, 255, .28);
            border-radius: 8px;
            background:
                radial-gradient(circle at 88% 12%, rgba(0, 209, 255, .12), transparent 22%),
                #020a12;
        }
        .smart-table {
            width: 100%;
            min-width: 1120px;
            border-collapse: collapse;
            color: #d9f7ff;
            font-size: .94rem;
        }
        .smart-table th {
            text-align: left;
            color: #79c7ec;
            padding: 13px 16px;
            border-bottom: 1px solid rgba(0, 209, 255, .45);
            background: rgba(8, 31, 66, .94);
            font-size: .78rem;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .smart-table td {
            padding: 14px 16px;
            border-bottom: 1px solid rgba(85, 166, 211, .12);
            vertical-align: middle;
        }
        .smart-table tr:hover td {
            background: rgba(0, 209, 255, .045);
        }
        .rank, .broker, .rating-text { color: #6fa8c7; }
        .stock-code {
            color: #dff8ff;
            font-weight: 800;
            font-size: 1.02rem;
        }
        .stock-name {
            color: #7db6d5;
            margin-top: 3px;
            white-space: nowrap;
        }
        .price {
            color: #dff8ff;
            font-weight: 800;
        }
        .stage-pill, .smart-badge {
            display: inline-flex;
            align-items: center;
            min-height: 24px;
            padding: 3px 9px;
            margin: 2px 4px 2px 0;
            border-radius: 999px;
            font-weight: 800;
            font-size: .78rem;
            white-space: nowrap;
        }
        .stage-hot, .gold {
            color: #ffd84a;
            border: 1px solid rgba(255, 216, 74, .58);
            background: rgba(255, 216, 74, .12);
        }
        .stage-base, .green {
            color: #16ffc4;
            border: 1px solid rgba(22, 255, 196, .34);
            background: rgba(22, 255, 196, .10);
        }
        .stage-watch, .blue, .cyan {
            color: #7bdcff;
            border: 1px solid rgba(123, 220, 255, .30);
            background: rgba(0, 145, 255, .12);
        }
        .stage-risk, .red {
            color: #ff6b8a;
            border: 1px solid rgba(255, 107, 138, .32);
            background: rgba(255, 107, 138, .12);
        }
        .purple {
            color: #d5a6ff;
            border: 1px solid rgba(213, 166, 255, .30);
            background: rgba(151, 88, 255, .15);
        }
        .neutral {
            color: #9bb9ca;
            border: 1px solid rgba(155, 185, 202, .25);
            background: rgba(155, 185, 202, .10);
        }
        .score-wrap {
            display: flex;
            gap: 10px;
            align-items: baseline;
            color: #ffd84a;
        }
        .score-wrap strong { font-size: 1.25rem; }
        .score-wrap span {
            color: #ff5c93;
            font-size: .82rem;
        }
        .score-bar {
            width: 112px;
            height: 5px;
            margin-top: 8px;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(76, 129, 172, .28);
        }
        .score-bar i {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #ffe45e, #00e5ff);
        }
        .stars {
            color: #ffd84a;
            letter-spacing: 0;
            white-space: nowrap;
        }
        @media (max-width: 900px) {
            .smart-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .smart-lab-top { align-items: flex-start; flex-direction: column; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    universe = stock_universe.copy()
    universe["_stage"] = universe.apply(lambda row: smart_stage(row)[0], axis=1)
    universe["_score"] = universe["智慧分數"].fillna(0) if "智慧分數" in universe else 0
    stage2_count = int((universe["_stage"] == "Stage 2 — 主升段").sum())
    strategy_count = int(universe["策略通過"].fillna(False).sum()) if "策略通過" in universe else 0
    highest_score = smart_num(universe["智慧分數"].max()) if "智慧分數" in universe else 0
    avg_return = universe["情境報酬"].dropna().mean() if "情境報酬" in universe else None
    avg_return_text = "-" if avg_return is None or pd.isna(avg_return) else f"{avg_return:.1f}%"

    st.markdown(
        f"""
        <div class="smart-lab">
            <div class="smart-lab-top">
                <div><span class="market-dot"></span>智慧選股作戰台&nbsp;&nbsp; <strong>Stage 2 — 主升段</strong>&nbsp;&nbsp; 報告池 {len(universe):,} | 平均情境報酬 {avg_return_text}</div>
                <div class="market-note">策略交集越完整，訊號可信度越高</div>
            </div>
            <div class="smart-stat-grid">
                <div class="smart-stat"><strong>{len(universe):,}</strong><span>股票池</span></div>
                <div class="smart-stat"><strong>{strategy_count:,}</strong><span>策略通過</span></div>
                <div class="smart-stat"><strong>{highest_score:.0f}</strong><span>最高評分</span></div>
                <div class="smart-stat"><strong>{stage2_count:,}</strong><span>Stage 2 主升段</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    pool = st.radio("股票池", ["精選池", "全市場", "預警池"], horizontal=True, label_visibility="collapsed")
    display_cap = min(50, len(universe))
    min_display = 5
    default_display = min(display_cap, max(10, int(max_stocks)))
    c1, c2, c3 = st.columns([1, 1.25, 1.25])
    with c1:
        if display_cap > min_display:
            default_display = max(min_display, min(default_display, display_cap))
            show_count = st.slider(
                "顯示前",
                min_value=min_display,
                max_value=display_cap,
                value=default_display,
                step=1,
            )
        else:
            show_count = display_cap
            st.metric("顯示前", f"{show_count} 檔")
    with c2:
        stage_filter = st.selectbox("篩選", ["全部階段"] + sorted(universe["_stage"].dropna().unique().tolist()))
    with c3:
        sort_mode = st.selectbox("排序", ["依評分排序", "依情境報酬排序", "依低基期排序", "依報告數排序"])

    if pool == "精選池":
        frame = selected.copy()
    elif pool == "預警池":
        strategy_mask = universe["策略通過"].fillna(False) if "策略通過" in universe else pd.Series(False, index=universe.index)
        frame = universe[(~strategy_mask) | (universe["_score"] < 40)].copy()
    else:
        frame = universe.copy()

    if not frame.empty:
        frame["_stage"] = frame.apply(lambda row: smart_stage(row)[0], axis=1)
        if stage_filter != "全部階段":
            frame = frame[frame["_stage"] == stage_filter]

    sort_columns = {
        "依評分排序": ("智慧分數", False),
        "依情境報酬排序": ("情境報酬", False),
        "依低基期排序": ("低基期位置", True),
        "依報告數排序": ("報告筆數", False),
    }
    sort_col, ascending = sort_columns[sort_mode]
    if sort_col in frame:
        frame = frame.sort_values(sort_col, ascending=ascending, na_position="last")
    frame = frame.head(show_count)

    if frame.empty:
        if pool == "精選池":
            st.warning("目前沒有股票同時符合報告與策略交集。可以切到「全市場」看候選池，或放寬左側低基期、成交量、市值與策略交集條件。")
        else:
            st.info("目前這個池別沒有符合條件的股票。")
    else:
        st.markdown(smart_table_html(frame), unsafe_allow_html=True)

    with st.expander("策略檢核明細", expanded=False):
        feature_cols = [
            "股票", "公司", "券商", "報告筆數", "目前價", "情境報酬", "建議/推薦", "目標價",
            "低基期位置", "低基期", "三率三升", "營收條件", "營收特徵", "法人買入",
            "營收MoM", "累積YoY", "外資投信買超張數", "平均成交張數", "市值百萬元",
            "策略通過", "三率原因", "營收原因", "法人原因", "策略資料來源", "智慧分數",
        ]
        feature_cols = [col for col in feature_cols if col in stock_universe.columns]
        st.dataframe(core.format_analysis_df(stock_universe[feature_cols]), use_container_width=True, hide_index=True)

    with st.expander("策略條件說明", expanded=False):
        render_strategy_explanation()


def render_smart_picker():
    core.apply_app_style()
    core.init_stock_database()
    init_smart_state()

    st.title("智慧選股")
    st.caption("上傳券商報告建立股票池，再用低基期、三率三升、營收、法人、成交量與市值條件做交集篩選。")

    uploaded_rows = st.session_state.get("auto_rows", [])
    database_rows = core.load_broker_database_rows()
    brokers = sorted({row.get("券商", "-") for row in uploaded_rows + database_rows + core.SAMPLE_ROWS if row.get("券商")})

    with st.sidebar:
        st.header("券商資料庫")
        db_files, db_reports = core.broker_database_counts()
        st.caption(f"檔案 {db_files:,} 個；報告 {db_reports:,} 筆")
        use_broker_database = st.checkbox("載入券商資料庫", value=db_reports > 0, disabled=db_reports == 0)
        st.caption("勾選後會把 broker_reports.db 內的券商報告加入智慧選股股票池。")
        active_report_rows = (database_rows if use_broker_database else []) + uploaded_rows

        st.divider()
        st.header("上傳報告")
        uploads = st.file_uploader(
            "上傳券商研究報告 PDF",
            type=["pdf"],
            accept_multiple_files=True,
            key="smart_picker_uploads",
            help="請上傳券商或投顧發布的股票研究報告 PDF，內容需可擷取文字，系統會讀取股票代碼、券商、日期、評等與目標價。",
        )
        st.caption("可上傳單一個股或多檔個股的券商研究報告 PDF；掃描圖片式 PDF 可能無法正確解析。")
        if st.button("匯入資料庫", key="smart_picker_request_db_import", use_container_width=True):
            if uploads:
                st.session_state.smart_picker_db_import_requested = True
            else:
                st.warning("請先選擇檔案")

        if st.session_state.get("smart_picker_db_import_requested"):
            import_password = st.text_input("匯入資料庫密碼", type="password", key="smart_picker_db_import_password")
            if st.button("確認匯入資料庫", key="smart_picker_confirm_db_import", use_container_width=True):
                if not uploads:
                    st.warning("請先選擇檔案")
                elif import_password != SMART_PICKER_DB_IMPORT_PASSWORD:
                    st.warning("匯入資料庫密碼不正確，檔案尚未入庫。")
                else:
                    st.session_state.auto_rows = []
                    st.session_state.auto_pending = []
                    st.session_state.auto_processed_files = set()
                    imported, rows_added, pending, skipped = core.process_broker_uploads_to_database(uploads)
                    st.session_state.smart_picker_db_import_requested = False
                    st.success(f"已入庫 {imported} 個檔案，加入畫面 {rows_added} 筆，待確認 {pending} 筆，重複略過 {skipped} 個檔案")

        if st.button("清除上傳資料", key="smart_picker_clear_uploads", use_container_width=True):
            st.session_state.auto_rows = []
            st.session_state.auto_pending = []
            st.session_state.auto_processed_files = set()
            st.session_state.smart_picker_db_import_requested = False
            st.rerun()

        st.divider()
        render_database_controls()

        st.divider()
        st.header("分析設定")
        scenario = st.selectbox("情境選擇", ["中性", "樂觀", "悲觀"], index=0)
        history_days = st.slider("歷史資料天數", min_value=20, max_value=1200, value=365, step=5)
        recent_only = st.checkbox("只看近期報告", value=False)
        recent_days = st.number_input("近期報告天數", min_value=1, max_value=365, value=90, step=5, disabled=not recent_only)
        use_sample = st.checkbox("使用範例資料", value=not bool(active_report_rows))

        st.header("策略條件")
        finmind_token, allow_finmind_update = finmind_update_controls()
        apply_strategy = st.checkbox("套用策略交集", value=True)
        low_base_limit = st.slider("低基期位置上限 (%)", min_value=0.0, max_value=100.0, value=35.0, step=5.0, disabled=not apply_strategy)
        min_volume_lots = st.number_input("每日成交張數下限", min_value=0, max_value=100000, value=200, step=50, disabled=not apply_strategy)
        min_market_cap_million = st.number_input("市值下限（百萬元）", min_value=0, max_value=10000000, value=200000, step=10000, disabled=not apply_strategy)
        max_volatility = st.slider("波動上限 (%)", min_value=1.0, max_value=120.0, value=55.0, step=1.0)
        min_return = st.slider("情境報酬下限 (%)", min_value=-50.0, max_value=200.0, value=0.0, step=1.0)
        max_drawdown_limit = st.slider("最大回撤下限 (%)", min_value=-100.0, max_value=0.0, value=-35.0, step=1.0)
        max_stocks = st.number_input("最多選入股票數量", min_value=1, max_value=30, value=8, step=1)
        weight_mode = st.selectbox("權重模式", ["等權重", "依智慧分數", "依情境報酬"])
        stock_filter = st.text_input("篩選股票代碼", placeholder="例如 2308, 6805")
        broker_filter = st.multiselect("篩選券商", brokers)

    base_rows = (core.load_broker_database_rows() if use_broker_database else []) + st.session_state.get("auto_rows", [])

    if st.session_state.get("auto_pending"):
        with st.expander("待確認資料", expanded=False):
            core.render_pending("auto_pending", "auto_rows", "smart")

    report_universe = core.build_selection_universe(
        base_rows,
        use_sample,
        recent_only,
        recent_days,
        stock_filter,
        broker_filter,
        history_days,
        scenario,
    )
    stock_universe = core.aggregate_stock_universe(
        report_universe,
        history_days,
        scenario,
        low_base_limit,
        min_volume_lots,
        min_market_cap_million,
        finmind_token,
        allow_finmind_update,
    )
    selected_raw = core.filter_selection(
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
    selected = core.add_weights(selected_raw, weight_mode)

    if stock_universe.empty:
        st.info("尚無候選股票。請先載入券商資料庫、上傳報告，或勾選使用範例資料。")
        return

    render_smart_dashboard(stock_universe, selected, max_stocks)


if __name__ == "__main__":
    render_smart_picker()
