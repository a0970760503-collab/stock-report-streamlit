import pandas as pd
import streamlit as st

import streamlit_app as core


def init_smart_state():
    core.init_tab_state()
    st.session_state.setdefault("auto_rows", [])
    st.session_state.setdefault("auto_pending", [])
    st.session_state.setdefault("auto_processed_files", set())


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
    password_ok = False
    configured_password = core.configured_finmind_password()

    if request_update:
        password = st.text_input("FinMind 使用密碼", type="password")
        if not configured_password:
            st.warning("尚未設定 FINMIND_UPDATE_PASSWORD，FinMind 更新功能已停用。")
        elif password == configured_password:
            password_ok = True
            st.success("FinMind 更新已解鎖。")
        elif password:
            st.warning("FinMind 使用密碼不正確，將只讀本機資料庫。")

    allow_update = request_update and password_ok
    token = st.text_input(
        "FinMind Token（可留空）",
        type="password",
        disabled=not allow_update,
        help="只有勾選並輸入正確使用密碼後才會使用 FinMind；留空會嘗試公開額度。",
    )
    return token, allow_update


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


def render_smart_picker():
    core.apply_app_style()
    core.init_stock_database()
    init_smart_state()

    st.title("智慧選股")
    st.caption("上傳券商報告建立股票池，再用低基期、三率三升、營收、法人、成交量與市值條件做交集篩選。")

    base_rows = st.session_state.get("auto_rows", [])
    brokers = sorted({row.get("券商", "-") for row in base_rows + core.SAMPLE_ROWS if row.get("券商")})

    with st.sidebar:
        st.header("上傳報告")
        uploads = st.file_uploader(
            "上傳 PDF",
            type=["pdf"],
            accept_multiple_files=True,
            key="smart_picker_uploads",
        )
        if st.button("處理上傳報告", key="smart_picker_process_uploads", use_container_width=True):
            if uploads:
                st.session_state.auto_rows = []
                st.session_state.auto_pending = []
                st.session_state.auto_processed_files = set()
                added, pending, skipped = core.process_tab_uploads(
                    uploads,
                    "auto_rows",
                    "auto_pending",
                    "auto_processed_files",
                    core.parse_reports,
                )
                st.success(f"已加入 {added} 筆，待確認 {pending} 筆，重複略過 {skipped} 筆")
            else:
                st.warning("請先選擇檔案")

        if st.button("清除上傳資料", key="smart_picker_clear_uploads", use_container_width=True):
            st.session_state.auto_rows = []
            st.session_state.auto_pending = []
            st.session_state.auto_processed_files = set()
            st.rerun()

        st.divider()
        render_database_controls()

        st.divider()
        st.header("分析設定")
        scenario = st.selectbox("情境選擇", ["中性", "樂觀", "悲觀"], index=0)
        history_days = st.slider("歷史資料天數", min_value=20, max_value=1200, value=365, step=5)
        recent_only = st.checkbox("只看近期報告", value=False)
        recent_days = st.number_input("近期報告天數", min_value=1, max_value=365, value=90, step=5, disabled=not recent_only)
        use_sample = st.checkbox("使用範例資料", value=not bool(base_rows))

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
        st.info("尚無候選股票。請先上傳報告，或勾選使用範例資料。")
        return

    render_strategy_explanation()

    feature_cols = [
        "股票", "公司", "券商", "報告筆數", "目前價", "情境報酬", "建議/推薦", "目標價",
        "低基期位置", "低基期", "三率三升", "營收條件", "營收特徵", "法人買入",
        "營收MoM", "累積YoY", "外資投信買超張數", "平均成交張數", "市值百萬元",
        "策略通過", "三率原因", "營收原因", "法人原因", "策略資料來源", "智慧分數",
    ]
    feature_cols = [col for col in feature_cols if col in stock_universe.columns]

    with st.expander("各股策略檢核表", expanded=True):
        st.dataframe(core.format_analysis_df(stock_universe[feature_cols]), use_container_width=True, hide_index=True)

    st.subheader(f"篩選結果：{len(selected)} 檔股票入選（上限 {int(max_stocks)} 檔）")
    if selected.empty:
        st.warning("目前沒有股票同時符合報告與策略交集。可查看上方檢核表，或放寬左側條件。")
        return

    result_cols = [
        "股票", "公司", "券商", "資料日期", "建議/推薦", "目前價", "目標價", "情境報酬",
        "低基期位置", "營收特徵", "營收MoM", "累積YoY", "外資投信買超張數",
        "平均成交張數", "市值百萬元", "智慧分數", "權重",
    ]
    result_cols = [col for col in result_cols if col in selected.columns]
    st.dataframe(core.format_analysis_df(selected[result_cols]), use_container_width=True, hide_index=True)
    st.bar_chart(selected.set_index("股票")["智慧分數"])


if __name__ == "__main__":
    render_smart_picker()
