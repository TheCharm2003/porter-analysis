"""Shared loaders, metric functions and UI helpers for the Porter People Analytics app."""
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "clean"
WAVES = ["Apr-2026", "Oct-2026"]
GRADE_ORDER = ["TBA"] + [f"G{i}" for i in range(1, 11)]
TENURE_ORDER = ["0-3m", "3-6m", "6-12m", "1-2y", "2y+"]
COMPA_ORDER = ["<0.85", "0.85-0.95", "0.95-1.05", ">1.05"]
Q_LABELS = {
    "Q2": "Manager feedback",
    "Q3": "Fair pay",
    "Q4": "Manageable workload",
    "Q5": "Onboarding & tools",
    "Q6": "Growth path",
}
# palette: one accent per wave, muted neutrals
C_APR = "#9AA5B1"
C_OCT = "#1F6FEB"
C_POS = "#2DA44E"
C_NEG = "#CF222E"
C_MID = "#BF8700"
WAVE_COLORS = {"Apr-2026": C_APR, "Oct-2026": C_OCT}
MIN_N = 5  # segments below this are suppressed (confidentiality + noise)


# ------------------------------------------------------------------ loading
@st.cache_data
def load_enps():
    r = pd.read_csv(DATA / "enps_responses.csv", parse_dates=["Submitted On", "Date of Joining", "Manager Effective From",
                                                              "Date of Exit"])
    e = pd.read_csv(DATA / "employees.csv", parse_dates=["Date of Joining", "Date of Exit", "Manager Effective From"])
    e["Compa Band"] = pd.cut(e["Compa Ratio"], [0, .85, .95, 1.05, 10], labels=COMPA_ORDER).astype("string")
    r["Mgr Changed <6m"] = r["Mgr Changed <6m"].map({True: "Yes", False: "No"})
    reorg = e[(e["Manager Effective From"] >= "2026-06-01") & (e["Manager Effective From"] < "2026-07-01") &
              (e["Manager Effective From"] > e["Date of Joining"])]["Employee ID"]
    r["Intercity Jun-26 reorg"] = np.where(r["Employee ID"].isin(reorg), "Yes", "No")
    e["Intercity Jun-26 reorg"] = np.where(e["Employee ID"].isin(reorg), "Yes", "No")
    return r, e


@st.cache_data
def load_recruitment():
    dcols = ["Req Raised On", "Hire Accept Date", "Hire DOJ", "Hire Offer Date"]
    q = pd.read_csv(DATA / "requisitions.csv", parse_dates=dcols)
    ccols = ["Applied On", "Shortlisted On", "Screening Done On", "R1 Interview Date", "R1 Feedback Submitted On",
             "R2 Interview Date", "Offer Released On", "Offer Response On", "Expected DOJ", "Actual DOJ", "Req Raised On"]
    c = pd.read_csv(DATA / "candidates.csv", parse_dates=ccols)
    rec = pd.read_csv(DATA / "recruiters.csv")
    q["Hire Source"] = q["Hire Source"].fillna("Not filled")
    return q, c, rec


@st.cache_data
def load_dq():
    return pd.read_csv(DATA / "dq_log.csv")


# ------------------------------------------------------------------ metrics
def enps(scores):
    s = pd.Series(scores).dropna()
    if len(s) == 0:
        return np.nan
    return 100 * ((s >= 9).mean() - (s <= 6).mean())


def enps_table(df, by):
    """eNPS, n, promoter/detractor %, item means by `by` (list) - recalculated on whatever df is passed."""
    g = df.groupby(by, dropna=False)
    out = g.agg(
        n=("Q1", lambda s: s.notna().sum()),
        eNPS=("Q1", enps),
        Promoters=("Q1", lambda s: (s.dropna() >= 9).mean() * 100 if s.notna().any() else np.nan),
        Detractors=("Q1", lambda s: (s.dropna() <= 6).mean() * 100 if s.notna().any() else np.nan),
        **{v: (k, "mean") for k, v in Q_LABELS.items()},
    )
    return out.reset_index()


def fmt_delta(x, suffix=""):
    if pd.isna(x):
        return "–"
    return f"{x:+.1f}{suffix}"


# ------------------------------------------------------------------ UI helpers
def multiselect_filter(container, label, series, key, order=None):
    opts = [v for v in (order or sorted(series.dropna().unique().tolist())) if v in set(series.dropna())]
    sel = container.multiselect(label, opts, default=[], key=key, placeholder="All")
    return sel


def apply_filters(df, selections):
    m = pd.Series(True, index=df.index)
    for col, vals in selections.items():
        if vals and col in df.columns:
            m &= df[col].isin(vals)
    return df[m]


def sort_segments(df, col):
    if col == "Grade":
        return df.assign(_o=df[col].map({g: i for i, g in enumerate(GRADE_ORDER)})).sort_values("_o").drop(columns="_o")
    if col == "Tenure Band":
        return df.assign(_o=df[col].map({g: i for i, g in enumerate(TENURE_ORDER)})).sort_values("_o").drop(columns="_o")
    if col == "Compa Band":
        return df.assign(_o=df[col].map({g: i for i, g in enumerate(COMPA_ORDER)})).sort_values("_o").drop(columns="_o")
    return df


def page_style():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1400px;}
        div[data-testid="stMetric"] {background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.18);
             border-radius: 10px; padding: 10px 14px;}
        div[data-testid="stMetricLabel"] p {font-size: 0.82rem; opacity: 0.8;}
        h1 {font-size: 1.9rem !important;} h3 {margin-top: 0.6rem;}
        .note {font-size: 0.82rem; opacity: 0.75;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout(fig, height=360, legend=True):
    fig.update_layout(
        height=height, margin=dict(l=10, r=30, t=78, b=10), font=dict(size=12),
        title=dict(y=0.985, yanchor="top", x=0.01, xanchor="left", font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text="") if legend else None,
        showlegend=legend, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(127,127,127,0.18)", zerolinecolor="rgba(127,127,127,0.4)")
    return fig


def hbar(labels, values, ns, title, xtitle, colors, height=None):
    """Horizontal bar with n in the axis label and padded range so labels never collide."""
    import plotly.graph_objects as go
    vals = pd.Series(values, dtype=float)
    ylab = [f"{l}  (n={n:.0f})" for l, n in zip(labels, ns)]
    lo, hi = min(0, vals.min(skipna=True) if vals.notna().any() else 0), max(0, vals.max(skipna=True) if vals.notna().any() else 0)
    pad = max((hi - lo) * 0.18, 4)
    fig = go.Figure(go.Bar(x=vals, y=ylab, orientation="h", marker_color=colors,
                           text=["–" if pd.isna(v) else f"{v:.0f}" for v in vals], textposition="outside",
                           cliponaxis=False))
    fig.update_layout(title=title, xaxis_title=xtitle, bargap=0.35)
    fig.update_xaxes(range=[lo - (pad if lo < 0 else 0), hi + pad])
    fig.update_yaxes(autorange="reversed")
    return plotly_layout(fig, height or max(240, 34 * len(vals) + 110), legend=False)
