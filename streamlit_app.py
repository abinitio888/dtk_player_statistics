"""DTK Tennis Tracker — coach dashboard for tennis player performance analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DTK Tennis Tracker",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── constants ────────────────────────────────────────────────────────────────

_GREEN = "#1a6b3c"
_WIN_COLOR = "#2ecc71"
_LOSS_COLOR = "#e74c3c"
_NEUTRAL = "#95a5a6"
_RESULT_COLORS = {"W": _WIN_COLOR, "L": _LOSS_COLOR}
_WR_SCALE = ["#e74c3c", "#f39c12", "#2ecc71"]

# Round priority for sorting (higher = deeper round)
_ROUND_RANK = {
    "qualifying": 1, "qualifying round": 1,
    "1st round qualifying": 2, "2nd round qualifying": 3,
    "round of 128": 4, "r128": 4,
    "1st round": 5, "round of 64": 5, "r64": 5,
    "2nd round": 6, "round of 32": 6, "r32": 6,
    "3rd round": 7, "round of 16": 7, "r16": 7,
    "quarter-final": 8, "quarterfinal": 8, "qf": 8,
    "semi-final": 9, "semifinal": 9, "sf": 9,
    "final": 10, "f": 10,
}


def _round_rank(r: str) -> int:
    return _ROUND_RANK.get(r.strip().lower(), 5)


# ─── data loading ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading match data…")
def load_csv(data) -> pd.DataFrame:
    df = pd.read_csv(data)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["year"] = df["date"].dt.year.astype(str)
    df["win"] = (df["result"] == "W").astype(int)
    df["loss"] = (df["result"] == "L").astype(int)
    for col in ["player", "tournament", "round", "match_type",
                "partner", "opponent", "result", "source"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


_DEFAULT_CSV = Path("output") / "player_data.csv"


def find_default_csv() -> Path | None:
    return _DEFAULT_CSV if _DEFAULT_CSV.exists() else None


# ─── metric helpers ───────────────────────────────────────────────────────────

def win_rate(df: pd.DataFrame) -> float:
    return df["win"].sum() / len(df) if len(df) else 0.0


def record_str(df: pd.DataFrame) -> str:
    return f"{int(df['win'].sum())}W – {int(df['loss'].sum())}L"


def player_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("player", sort=False)
        .agg(
            Matches=("result", "count"),
            Wins=("win", "sum"),
            Losses=("loss", "sum"),
            Singles=("match_type", lambda x: (x == "Singles").sum()),
            Doubles=("match_type", lambda x: (x == "Doubles").sum()),
        )
        .assign(**{"Win Rate": lambda d: d["Wins"] / d["Matches"]})
        .sort_values("Win Rate", ascending=False)
        .reset_index()
        .rename(columns={"player": "Player"})
    )


# ─── sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎾 DTK Tennis Tracker")
    st.caption("Coach Performance Dashboard")
    st.divider()

    df_raw: pd.DataFrame | None = None

    default = find_default_csv()
    if default:
        df_raw = load_csv(default)
    else:
        st.error("Data file not found: output/player_data.csv")

    if df_raw is None:
        st.stop()

    st.divider()

    # ── filters ───────────────────────────────────────────────────────────────
    st.markdown("**Filters**")

    min_d = df_raw["date"].min().date()
    max_d = df_raw["date"].max().date()
    date_range = st.date_input(
        "Period",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        date_from, date_to = date_range
    else:
        date_from = date_to = date_range[0] if isinstance(date_range, (list, tuple)) else date_range

    mt_opts = sorted(df_raw["match_type"].unique().tolist())
    sel_types = st.multiselect("Match Type", mt_opts, default=mt_opts)

    st.divider()

    # ── view selector ─────────────────────────────────────────────────────────
    st.markdown("**View**")
    player_names = sorted(df_raw["player"].unique().tolist())
    view_options = ["🏠  Club Overview"] + [f"👤  {p}" for p in player_names]
    sel_view = st.radio("View", view_options, label_visibility="collapsed")

# ─── apply filters ────────────────────────────────────────────────────────────

df = df_raw.copy()
df = df[(df["date"].dt.date >= date_from) & (df["date"].dt.date <= date_to)]
if sel_types:
    df = df[df["match_type"].isin(sel_types)]

if df.empty:
    st.warning("No matches match the current filters.")
    st.stop()

# ─── club overview ────────────────────────────────────────────────────────────

def show_club_overview(df: pd.DataFrame) -> None:
    st.title("🎾 DTK Tennis Tracker")
    st.caption(f"Club performance overview · {date_from} → {date_to}")
    st.divider()

    # ── KPI cards ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Players", df["player"].nunique())
    c2.metric("Total Matches", f"{len(df):,}")
    c3.metric("Club Win Rate", f"{win_rate(df):.1%}")
    active_months = df["month"].nunique()
    c4.metric("Active Months", active_months)

    st.divider()

    # ── win rate + volume charts ───────────────────────────────────────────────
    ps = player_summary_table(df)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Win Rate by Player")
        ps_sorted = ps.sort_values("Win Rate")
        fig = px.bar(
            ps_sorted,
            x="Win Rate", y="Player",
            orientation="h",
            text=ps_sorted["Win Rate"].map("{:.0%}".format),
            color="Win Rate",
            color_continuous_scale=_WR_SCALE,
            range_color=[0, 1],
        )
        fig.add_vline(x=0.5, line_dash="dot", line_color=_NEUTRAL, annotation_text="50%")
        fig.update_layout(
            xaxis_tickformat=".0%", xaxis_range=[0, 1.1],
            coloraxis_showscale=False, height=40 * len(ps) + 60,
            margin=dict(l=0, r=60, t=10, b=10),
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Match Volume by Player")
        ps_vol = ps.sort_values("Matches")
        fig2 = px.bar(
            ps_vol,
            x="Matches", y="Player",
            orientation="h",
            text="Matches",
            color_discrete_sequence=[_GREEN],
        )
        fig2.update_layout(
            height=40 * len(ps) + 60,
            margin=dict(l=0, r=40, t=10, b=10),
        )
        fig2.update_traces(textposition="outside")
        st.plotly_chart(fig2, use_container_width=True)

    # ── monthly activity ──────────────────────────────────────────────────────
    st.markdown("#### Monthly Match Activity")
    monthly = (
        df.groupby(["month", "player"])
        .agg(matches=("result", "count"), wins=("win", "sum"))
        .reset_index()
    )
    fig3 = px.line(
        monthly, x="month", y="matches", color="player",
        markers=True, line_shape="spline",
    )
    fig3.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=10),
        xaxis_title="", yaxis_title="Matches",
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── player summary table ──────────────────────────────────────────────────
    st.markdown("#### Player Summary")
    display = ps.copy()
    display["Win Rate"] = display["Win Rate"].map("{:.1%}".format)
    st.dataframe(display, use_container_width=True, hide_index=True)

    # ── recent matches ────────────────────────────────────────────────────────
    st.markdown("#### Recent Matches (all players)")
    recent = (
        df.sort_values("date", ascending=False)
        .head(20)
        [["date", "player", "tournament", "round", "match_type", "opponent", "score", "result"]]
        .copy()
    )
    recent["date"] = recent["date"].dt.date
    st.dataframe(recent, use_container_width=True, hide_index=True)


# ─── player detail ────────────────────────────────────────────────────────────

def show_player_detail(df: pd.DataFrame, player: str) -> None:
    pdf = df[df["player"] == player].copy()

    if pdf.empty:
        st.warning(f"No matches for {player} in the selected period/filters.")
        return

    singles = pdf[pdf["match_type"] == "Singles"]
    doubles = pdf[pdf["match_type"] == "Doubles"]

    st.title(f"👤 {player}")
    st.caption(f"DTK Tennis Tracker · {date_from} → {date_to}")
    st.divider()

    # ── KPI cards ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Record", record_str(pdf))
    c2.metric("Win Rate", f"{win_rate(pdf):.1%}")
    c3.metric("Matches", len(pdf))
    c4.metric(
        "Singles",
        f"{len(singles)}  ({win_rate(singles):.0%})" if singles.empty is False else "–",
    )
    c5.metric(
        "Doubles",
        f"{len(doubles)}  ({win_rate(doubles):.0%})" if doubles.empty is False else "–",
    )

    st.divider()

    tab_overview, tab_history, tab_opponents = st.tabs(
        ["📊 Overview", "📋 Match History", "🆚 Opponents"]
    )

    # ── overview ──────────────────────────────────────────────────────────────
    with tab_overview:

        # Win rate over time (monthly)
        monthly = (
            pdf.groupby("month")
            .agg(matches=("result", "count"), wins=("win", "sum"))
            .assign(win_rate=lambda d: d["wins"] / d["matches"])
            .reset_index()
        )

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### Win Rate Over Time")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly["month"],
                y=monthly["matches"],
                name="Matches",
                marker_color="#d5e8d4",
                yaxis="y2",
                hovertemplate="%{y} matches<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=monthly["month"],
                y=monthly["win_rate"],
                name="Win Rate",
                line=dict(color=_GREEN, width=2.5),
                mode="lines+markers",
                marker=dict(size=7),
                hovertemplate="%{y:.0%}<extra></extra>",
            ))
            fig.add_hline(y=0.5, line_dash="dot", line_color=_NEUTRAL)
            fig.update_layout(
                yaxis=dict(tickformat=".0%", title="Win Rate", range=[0, 1.05]),
                yaxis2=dict(title="Matches", overlaying="y", side="right"),
                height=300, margin=dict(l=0, r=0, t=10, b=10),
                legend=dict(orientation="h", y=1.15),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.markdown("#### Singles vs Doubles")
            type_df = (
                pdf.groupby(["match_type", "result"])
                .size()
                .reset_index(name="count")
            )
            fig2 = px.bar(
                type_df, x="match_type", y="count", color="result",
                color_discrete_map=_RESULT_COLORS,
                text="count", barmode="group",
            )
            fig2.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=10),
                xaxis_title="", yaxis_title="Matches",
                legend_title="Result",
            )
            fig2.update_traces(textposition="outside")
            st.plotly_chart(fig2, use_container_width=True)

        # Tournament performance
        st.markdown("#### Tournament Performance")
        tourn = (
            pdf.groupby("tournament")
            .agg(matches=("result", "count"), wins=("win", "sum"))
            .assign(win_rate=lambda d: d["wins"] / d["matches"])
            .sort_values("matches", ascending=False)
            .head(20)
            .reset_index()
        )
        tourn["record"] = tourn.apply(
            lambda r: f"{int(r.wins)}W–{int(r.matches - r.wins)}L", axis=1
        )
        fig3 = px.scatter(
            tourn,
            x="win_rate", y="tournament",
            size="matches",
            color="win_rate",
            color_continuous_scale=_WR_SCALE,
            range_color=[0, 1],
            custom_data=["record", "matches"],
        )
        fig3.update_traces(
            hovertemplate="<b>%{y}</b><br>%{customdata[0]}"
                          " (%{customdata[1]} matches)<extra></extra>"
        )
        fig3.add_vline(x=0.5, line_dash="dot", line_color=_NEUTRAL)
        fig3.update_layout(
            height=max(260, len(tourn) * 30 + 60),
            xaxis_tickformat=".0%", xaxis_range=[-0.05, 1.1],
            xaxis_title="Win Rate", yaxis_title="",
            coloraxis_showscale=False,
            margin=dict(l=0, r=20, t=10, b=10),
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Round + source breakdown
        col_c, col_d = st.columns(2)

        with col_c:
            st.markdown("#### Round Distribution")
            round_df = (
                pdf.groupby(["round", "result"])
                .size()
                .reset_index(name="count")
            )
            # Sort by round depth
            round_order = (
                round_df["round"]
                .drop_duplicates()
                .sort_values(key=lambda s: s.map(_round_rank))
                .tolist()
            )
            fig4 = px.bar(
                round_df, x="round", y="count", color="result",
                color_discrete_map=_RESULT_COLORS,
                barmode="stack",
                category_orders={"round": round_order},
            )
            fig4.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=10),
                xaxis_title="", yaxis_title="Matches",
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig4, use_container_width=True)

        with col_d:
            st.markdown("#### Source Breakdown")
            src_df = (
                pdf.groupby(["source", "result"])
                .size()
                .reset_index(name="count")
            )
            fig5 = px.bar(
                src_df, x="source", y="count", color="result",
                color_discrete_map=_RESULT_COLORS,
                barmode="stack", text="count",
            )
            fig5.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=10),
                xaxis_title="Source", yaxis_title="Matches",
            )
            fig5.update_traces(textposition="inside")
            st.plotly_chart(fig5, use_container_width=True)

    # ── match history ─────────────────────────────────────────────────────────
    with tab_history:
        st.markdown("#### Match History")

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            res_filter = st.multiselect(
                "Result", ["W", "L"], default=["W", "L"], key="hist_res"
            )
        with fc2:
            type_filter = st.multiselect(
                "Type",
                sorted(pdf["match_type"].unique().tolist()),
                default=sorted(pdf["match_type"].unique().tolist()),
                key="hist_type",
            )
        with fc3:
            tourn_filter = st.multiselect(
                "Tournament",
                sorted(pdf["tournament"].unique().tolist()),
                key="hist_tourn",
            )

        hist = pdf.copy()
        if res_filter:
            hist = hist[hist["result"].isin(res_filter)]
        if type_filter:
            hist = hist[hist["match_type"].isin(type_filter)]
        if tourn_filter:
            hist = hist[hist["tournament"].isin(tourn_filter)]

        hist = hist.sort_values("date", ascending=False)
        hist["date"] = hist["date"].dt.date

        st.dataframe(
            hist[["date", "tournament", "round", "match_type", "partner",
                  "opponent", "score", "result", "source"]].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "result": st.column_config.TextColumn("Result"),
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            },
        )
        st.caption(f"{len(hist):,} matches shown")

    # ── opponents ─────────────────────────────────────────────────────────────
    with tab_opponents:
        st.markdown("#### Head-to-Head Records")

        opp = (
            pdf[pdf["opponent"].str.len() > 0]
            .groupby("opponent")
            .agg(matches=("result", "count"), wins=("win", "sum"))
            .assign(
                losses=lambda d: d["matches"] - d["wins"],
                win_rate=lambda d: d["wins"] / d["matches"],
            )
            .sort_values("matches", ascending=False)
            .reset_index()
        )
        opp["record"] = opp.apply(
            lambda r: f"{int(r.wins)}W–{int(r.losses)}L", axis=1
        )

        top_opp = opp.head(20).sort_values("win_rate")

        col_e, col_f = st.columns([3, 2])

        with col_e:
            fig6 = px.bar(
                top_opp,
                x="win_rate", y="opponent",
                orientation="h",
                color="win_rate",
                color_continuous_scale=_WR_SCALE,
                range_color=[0, 1],
                text="record",
                custom_data=["matches"],
            )
            fig6.update_traces(
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{text} (%{customdata[0]} matches)<extra></extra>",
            )
            fig6.add_vline(x=0.5, line_dash="dot", line_color=_NEUTRAL)
            fig6.update_layout(
                xaxis_tickformat=".0%", xaxis_range=[0, 1.25],
                coloraxis_showscale=False,
                height=max(300, len(top_opp) * 30 + 60),
                margin=dict(l=0, r=100, t=10, b=10),
            )
            st.plotly_chart(fig6, use_container_width=True)

        with col_f:
            st.markdown("**Most Played Opponents**")
            opp_table = opp[["opponent", "matches", "record", "win_rate"]].copy()
            opp_table["win_rate"] = opp_table["win_rate"].map("{:.0%}".format)
            opp_table.columns = ["Opponent", "Matches", "Record", "Win%"]
            st.dataframe(opp_table, use_container_width=True, hide_index=True)


# ─── routing ──────────────────────────────────────────────────────────────────

if sel_view == "🏠  Club Overview":
    show_club_overview(df)
else:
    player = sel_view.replace("👤  ", "")
    show_player_detail(df, player)
