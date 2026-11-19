"""지점 실적 탐색 대시보드 (확장판).

기존 12주차 배포 예제 앱(app.py)의 구조와 배포 안전장치(HERE, @st.cache_data,
Matplotlib 한글 글꼴 폴백)를 유지하면서, 수익성·성장성·누적 실적·지점 간 격차 분석
차트와 파생 지표를 추가한 버전입니다.

GitHub 저장소에 app.py, requirements.txt, sales.csv를 같은 폴더로 올리고
Streamlit Community Cloud에 배포합니다.
로컬 실행: python -m streamlit run app.py
"""
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).parent
COLORS = {"A": "#0072B2", "B": "#D55E00"}

st.set_page_config(page_title="지점 실적 탐색 (확장판)", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    """CSV를 읽고 분석용 파생 변수를 미리 계산합니다."""
    df = pd.read_csv(HERE / "sales.csv").sort_values(["branch", "month"]).reset_index(drop=True)
    # 추정 비용 = 매출 - 영업이익
    df["cost"] = df["sales"] - df["profit"]
    # 월별 영업이익률 (%)
    df["margin"] = df["profit"] / df["sales"] * 100
    # 분기 (Q1 ~ Q4)
    df["quarter"] = ((df["month"] - 1) // 3 + 1).map(lambda q: f"Q{q}")
    # 지점별 전월 대비 증감률 (MoM %)
    df["sales_mom"] = df.groupby("branch")["sales"].pct_change() * 100
    df["profit_mom"] = df.groupby("branch")["profit"].pct_change() * 100
    return df


def korean_font():
    """Matplotlib가 쓸 수 있는 한글 글꼴 이름. 없으면 None을 반환합니다."""
    names = {f.name for f in fm.fontManager.ttflist}
    return next(
        (f for f in ["Pretendard", "Malgun Gothic", "AppleGothic", "NanumGothic"] if f in names),
        None,
    )


def calc_period_growth(df: pd.DataFrame, col: str) -> float | None:
    """선택한 기간의 첫 월 합계 대비 마지막 월 합계 성장률(%)을 계산합니다."""
    monthly = df.groupby("month")[col].sum().sort_index()
    if len(monthly) < 2 or monthly.iloc[0] == 0:
        return None
    return (monthly.iloc[-1] - monthly.iloc[0]) / monthly.iloc[0] * 100


# ---------------------------------------------------------------------------
# 1. 헤더 및 데이터 로드
# ---------------------------------------------------------------------------
st.title("어느 지점의 실적이 더 좋은가")
st.caption("출처: 수업용 가상 데이터(sales.csv) · 2026년 1~12월 지점별 월 실적 · 금액 단위: 백만원")

try:
    data = load_data()
except FileNotFoundError:
    st.error("app.py와 같은 폴더에 sales.csv를 올려 주세요.")
    st.stop()

# ---------------------------------------------------------------------------
# 2. 사이드바 조회 조건
# ---------------------------------------------------------------------------
st.sidebar.header("조회 조건")
all_branches = sorted(data["branch"].unique().tolist())
branches = st.sidebar.multiselect("지점", all_branches, default=all_branches)
months = st.sidebar.slider("월 범위", 1, 12, (1, 12))
metric_label = st.sidebar.selectbox("표시 지표", ["매출", "영업이익"])
metric = {"매출": "sales", "영업이익": "profit"}[metric_label]
mom_col = {"매출": "sales_mom", "영업이익": "profit_mom"}[metric_label]

view = data.loc[
    data["branch"].isin(branches) & data["month"].between(months[0], months[1])
].copy()

if view.empty:
    st.warning("표시할 데이터가 없습니다. 지점을 하나 이상 선택하세요.")
    st.stop()

# 선택된 구간 내 누적 실적 계산 (월 범위 변경 시 선택 구간 기준 누적)
view = view.sort_values(["branch", "month"])
view["cum_sales"] = view.groupby("branch")["sales"].cumsum()
view["cum_profit"] = view.groupby("branch")["profit"].cumsum()
cum_col = {"매출": "cum_sales", "영업이익": "cum_profit"}[metric_label]

# ---------------------------------------------------------------------------
# 3. 핵심 KPI 카드 (기존 3개 → 5개로 확장)
# ---------------------------------------------------------------------------
st.subheader(f"{months[0]}~{months[1]}월 {metric_label} · {', '.join(branches)}지점")

total_sales = view["sales"].sum()
total_profit = view["profit"].sum()
total_cost = view["cost"].sum()
period_margin = (total_profit / total_sales * 100) if total_sales else 0.0
period_growth = calc_period_growth(view, metric)
avg_mom = view[mom_col].dropna().mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(f"기간 {metric_label} 합계", f"{view[metric].sum():,.0f} 백만원")
c2.metric("기간 추정 비용", f"{total_cost:,.0f} 백만원", f"매출 대비 {total_cost / total_sales * 100:.1f}%", delta_color="off")
c3.metric("기간 영업이익률", f"{period_margin:.1f} %")
c4.metric(
    f"구간 성장률 ({months[0]}→{months[1]}월)",
    f"{period_growth:+.1f} %" if period_growth is not None else "N/A",
)
c5.metric(
    "평균 전월 대비(MoM)",
    f"{avg_mom:+.1f} %" if pd.notna(avg_mom) else "N/A",
)
st.caption(
    "추정 비용 = 매출 - 영업이익 · 기간 영업이익률 = 기간 이익 합계 ÷ 기간 매출 합계 · "
    "구간 성장률은 선택 기간 첫 월 대비 마지막 월 변화율입니다."
)

# ---------------------------------------------------------------------------
# 4. 탭 기반 시각화 구성
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 기본 현황 (기존 3종)", "💰 수익성·비용 분석", "📈 성장성·누적 실적", "⚖️ 지점 간 격차 (A vs B)"]
)

# === Tab 1: 기존 3종 차트 ===
with tab1:
    # 차트 1: 월별 추이 (Plotly)
    trend = px.line(
        view,
        x="month",
        y=metric,
        color="branch",
        markers=True,
        color_discrete_map=COLORS,
        title=f"월별 {metric_label} 추이",
        labels={"month": "월", metric: f"{metric_label} (백만원)", "branch": "지점"},
    )
    trend.update_xaxes(dtick=1)
    trend.update_yaxes(rangemode="tozero")

    # 차트 2: 기간 합계 (Matplotlib - 한글 글꼴 폴백 유지)
    kfont = korean_font()
    totals = view.groupby("branch", as_index=False)[metric].sum()
    with plt.rc_context({"font.family": kfont or "DejaVu Sans", "axes.unicode_minus": False}):
        static_fig, ax = plt.subplots(figsize=(6, 3.6))
        bars = ax.bar(
            totals["branch"],
            totals[metric],
            color=[COLORS.get(b, "#666666") for b in totals["branch"]],
        )
        ax.bar_label(bars, fmt="%.0f", padding=3)
        if kfont:
            ax.set(title=f"기간 {metric_label} 합계", xlabel="지점", ylabel=f"{metric_label} (백만원)")
        else:
            ax.set(title="Period total", xlabel="Branch", ylabel=f"{metric} (million KRW)")
        ax.set_ylim(0, max(totals[metric].max() * 1.2, 1))
        ax.spines[["top", "right"]].set_visible(False)
        static_fig.tight_layout()

    # 차트 3: 기간 영업이익률 (Plotly)
    period = view.groupby("branch", as_index=False)[["sales", "profit"]].sum()
    period["margin"] = period["profit"] / period["sales"] * 100
    margin_fig = px.bar(
        period,
        x="branch",
        y="margin",
        color="branch",
        color_discrete_map=COLORS,
        text=period["margin"].map(lambda v: f"{v:.1f}%"),
        title="기간 영업이익률",
        labels={"branch": "지점", "margin": "영업이익률 (%)"},
    )
    margin_fig.update_traces(textposition="outside")
    margin_fig.update_layout(showlegend=False)
    margin_fig.update_yaxes(rangemode="tozero", range=[0, max(period["margin"].max() * 1.25, 1)])

    left, middle, right = st.columns(3)
    with left:
        st.plotly_chart(trend, width="stretch")
    with middle:
        st.pyplot(static_fig, width="stretch")
    with right:
        st.plotly_chart(margin_fig, width="stretch")
    plt.close(static_fig)

    if not kfont:
        st.caption("이 서버에는 한글 글꼴이 없어 가운데 그림(Matplotlib)의 글자를 영어로 표시합니다.")

# === Tab 2: 수익성·비용 구조 심층 분석 (신규) ===
with tab2:
    col_a, col_b = st.columns(2)

    # 차트 4: 월별 영업이익률 추이
    with col_a:
        margin_trend = px.line(
            view,
            x="month",
            y="margin",
            color="branch",
            markers=True,
            color_discrete_map=COLORS,
            title="월별 영업이익률 추이 (수익성 개선 확인)",
            labels={"month": "월", "margin": "영업이익률 (%)", "branch": "지점"},
            hover_data={"sales": True, "profit": True, "margin": ":.1f"},
        )
        margin_trend.update_xaxes(dtick=1)
        margin_trend.update_yaxes(rangemode="tozero")
        st.plotly_chart(margin_trend, width="stretch")

    # 차트 5: 매출 vs 영업이익 산점도 (영업 레버리지 분석)
    with col_b:
        scatter_fig = px.scatter(
            view,
            x="sales",
            y="profit",
            color="branch",
            size="margin",
            text="month",
            color_discrete_map=COLORS,
            title="매출 대비 영업이익 분포 (점 크기: 이익률, 숫자: 월)",
            labels={"sales": "매출 (백만원)", "profit": "영업이익 (백만원)", "branch": "지점", "margin": "이익률(%)"},
            hover_data={"month": True, "margin": ":.1f"},
        )
        scatter_fig.update_traces(textposition="top center")
        # 15% 기준선 추가
        max_s = view["sales"].max() * 1.05
        scatter_fig.add_trace(
            go.Scatter(
                x=[0, max_s],
                y=[0, max_s * 0.15],
                mode="lines",
                name="이익률 15% 기준선",
                line=dict(dash="dash", color="gray"),
            )
        )
        scatter_fig.update_xaxes(rangemode="tozero")
        scatter_fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(scatter_fig, width="stretch")

    # 차트 6: 지점별 매출 구조 (추정 비용 vs 영업이익 누적 막대)
    struct_df = (
        view.groupby("branch", as_index=False)[["cost", "profit"]]
        .sum()
        .melt(id_vars="branch", var_name="항목", value_name="금액")
    )
    struct_df["항목"] = struct_df["항목"].map({"cost": "추정 비용", "profit": "영업이익"})
    cost_fig = px.bar(
        struct_df,
        x="branch",
        y="금액",
        color="항목",
        barmode="stack",
        text_auto=".0f",
        color_discrete_map={"추정 비용": "#B0BEC5", "영업이익": "#2E7D32"},
        title="지점별 매출 구성 (추정 비용 vs 영업이익)",
        labels={"branch": "지점", "금액": "금액 (백만원)"},
    )
    st.plotly_chart(cost_fig, width="stretch")

# === Tab 3: 성장성·누적 실적 (신규) ===
with tab3:
    col_c, col_d = st.columns(2)

    # 차트 7: 전월 대비 성장률 (MoM %)
    with col_c:
        mom_view = view.dropna(subset=[mom_col])
        if mom_view.empty:
            st.info("전월 대비 증감률을 계산하려면 2월 이후 데이터가 포함되어야 합니다.")
        else:
            mom_fig = px.bar(
                mom_view,
                x="month",
                y=mom_col,
                color="branch",
                barmode="group",
                color_discrete_map=COLORS,
                title=f"월별 {metric_label} 전월 대비 증감률 (MoM %)",
                labels={"month": "월", mom_col: "전월 대비 증감률 (%)", "branch": "지점"},
            )
            mom_fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1)
            mom_fig.update_xaxes(dtick=1)
            st.plotly_chart(mom_fig, width="stretch")

    # 차트 8: 구간 누적 실적 추이
    with col_d:
        cum_fig = px.area(
            view,
            x="month",
            y=cum_col,
            color="branch",
            markers=True,
            color_discrete_map=COLORS,
            title=f"선택 구간 누적 {metric_label} 추이",
            labels={"month": "월", cum_col: f"누적 {metric_label} (백만원)", "branch": "지점"},
        )
        cum_fig.update_layout(hovermode="x unified")
        cum_fig.update_xaxes(dtick=1)
        st.plotly_chart(cum_fig, width="stretch")

    # 차트 9: 분기별 실적 비교
    q_df = view.groupby(["quarter", "branch"], as_index=False)[["sales", "profit"]].sum()
    q_df["margin"] = q_df["profit"] / q_df["sales"] * 100
    quarter_fig = px.bar(
        q_df,
        x="quarter",
        y=metric,
        color="branch",
        barmode="group",
        text_auto=".0f",
        color_discrete_map=COLORS,
        category_orders={"quarter": ["Q1", "Q2", "Q3", "Q4"]},
        title=f"분기별 {metric_label} 비교",
        labels={"quarter": "분기", metric: f"{metric_label} (백만원)", "branch": "지점"},
        hover_data={"margin": ":.1f"},
    )
    st.plotly_chart(quarter_fig, width="stretch")

# === Tab 4: 지점 간 격차 분석 (A vs B) (신규) ===
with tab4:
    if set(branches) >= {"A", "B"}:
        piv = view.pivot(index="month", columns="branch", values=metric).dropna()
        gap_df = pd.DataFrame(
            {
                "month": piv.index,
                "A": piv["A"],
                "B": piv["B"],
                "gap": piv["A"] - piv["B"],
            }
        )
        gap_df["우세 지점"] = gap_df["gap"].apply(
            lambda g: "A 우세" if g > 0 else ("B 우세" if g < 0 else "동일")
        )

        gap_fig = px.bar(
            gap_df,
            x="month",
            y="gap",
            color="우세 지점",
            text=gap_df["gap"].map(lambda v: f"{v:+.0f}"),
            color_discrete_map={"A 우세": COLORS["A"], "B 우세": COLORS["B"], "동일": "#999999"},
            title=f"월별 지점 간 {metric_label} 격차 (A지점 − B지점)",
            labels={"month": "월", "gap": f"{metric_label} 격차 (백만원)"},
            hover_data={"A": True, "B": True},
        )
        gap_fig.add_hline(y=0, line_color="black", line_width=1)
        gap_fig.update_traces(textposition="outside")
        gap_fig.update_xaxes(dtick=1)
        st.plotly_chart(gap_fig, width="stretch")

        # 요약 코멘트
        a_wins = int((gap_df["gap"] > 0).sum())
        b_wins = int((gap_df["gap"] < 0).sum())
        st.info(
            f"선택한 기간({len(gap_df)}개월) 중 **A지점 우세 {a_wins}개월**, **B지점 우세 {b_wins}개월**이며, "
            f"누적 격차(A−B)는 **{gap_df['gap'].sum():+,.0f} 백만원**입니다."
        )
    else:
        st.info("지점 간 격차(A − B)를 비교하려면 사이드바에서 A지점과 B지점을 모두 선택하세요.")

# ---------------------------------------------------------------------------
# 5. 지점별 요약 표 & 상세 데이터 다운로드
# ---------------------------------------------------------------------------
st.divider()
st.subheader("지점별 기간 요약")
summary_df = (
    view.groupby("branch", as_index=False)
    .agg(
        관측월수=("month", "count"),
        총매출=("sales", "sum"),
        총영업이익=("profit", "sum"),
        총추정비용=("cost", "sum"),
        월평균매출=("sales", "mean"),
        월평균영업이익=("profit", "mean"),
    )
)
summary_df["기간영업이익률(%)"] = (summary_df["총영업이익"] / summary_df["총매출"] * 100).round(1)
summary_df["월평균매출"] = summary_df["월평균매출"].round(1)
summary_df["월평균영업이익"] = summary_df["월평균영업이익"].round(1)
st.dataframe(summary_df, hide_index=True, width="stretch")

st.subheader("현재 선택한 상세 데이터 (파생 지표 포함)")
display_cols = [
    "month", "quarter", "branch", "sales", "profit", "cost", "margin",
    "sales_mom", "profit_mom", "cum_sales", "cum_profit",
]
renamed = view[display_cols].rename(
    columns={
        "month": "월",
        "quarter": "분기",
        "branch": "지점",
        "sales": "매출",
        "profit": "영업이익",
        "cost": "추정비용",
        "margin": "영업이익률(%)",
        "sales_mom": "매출MoM(%)",
        "profit_mom": "이익MoM(%)",
        "cum_sales": "누적매출",
        "cum_profit": "누적이익",
    }
)
st.dataframe(
    renamed.style.format(
        {"영업이익률(%)": "{:.1f}", "매출MoM(%)": "{:+.1f}", "이익MoM(%)": "{:+.1f}"},
        na_rep="-",
    ),
    hide_index=True,
    width="stretch",
)

st.download_button(
    "현재 선택 CSV 저장 (파생 지표 포함)",
    data=renamed.to_csv(index=False).encode("utf-8-sig"),
    file_name="selected_sales_extended.csv",
    mime="text/csv",
)
st.caption("이 자료만으로 실적 변화의 원인을 단정하지 않습니다.")
