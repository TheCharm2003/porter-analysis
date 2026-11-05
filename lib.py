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
# palette (navy / corporate-blue system with RAG status colours)
NAVY = "#14172A"
INK_SOFT = "#5A6275"
C_APR = "#B7BFCC"
C_OCT = "#1370BB"
C_POS = "#1E8E5A"
C_NEG = "#C33F37"
C_MID = "#B8730F"
C_TEAL = "#2CA6A4"
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


FONTS = "https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap"

CSS = """
<style>
@import url('__FONTS__');
:root{--navy-900:#14172a;--navy-800:#1b2039;--blue-600:#1370bb;--blue-700:#27508e;--blue-50:#eaf3fb;
--ink:#1c2130;--ink-soft:#5a6275;--line:#e2e6ef;--line-soft:#edf0f6;--canvas:#f5f7fb;
--green:#1e8e5a;--green-bg:#e6f4ec;--amber:#b8730f;--amber-bg:#fbf1de;--red:#c33f37;--red-bg:#fbeae9;
--gray:#8a92a3;--gray-bg:#eef0f4;--shadow:0 1px 2px rgba(20,23,42,.04),0 8px 24px -12px rgba(20,23,42,.14);}
html,body,[class*="css"],.stApp{font-family:'Inter','Segoe UI',sans-serif;}
.stApp{background:var(--canvas);color:var(--ink);}
h1,h2,h3,h4,h5{font-family:'Manrope','Segoe UI',sans-serif!important;color:var(--navy-900)!important;letter-spacing:-.2px;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1.2rem!important;padding-bottom:3rem;max-width:1400px;}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#14172a 0%,#1b2039 100%);border-right:none;}
section[data-testid="stSidebar"] *{color:#c3cbe4;}
section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3{color:#fff!important;}
[data-testid="stSidebarHeader"] img{height:44px!important;max-width:220px;}
[data-testid="stSidebarNav"] a{border-radius:10px;margin:2px 8px;padding:6px 10px;}
[data-testid="stSidebarNav"] a span{color:#c3cbe4!important;font-weight:600;font-size:14px;}
[data-testid="stSidebarNav"] a:hover{background:rgba(255,255,255,.06);}
[data-testid="stSidebarNav"] a[aria-current="page"]{background:var(--blue-600);}
[data-testid="stSidebarNav"] a[aria-current="page"] span{color:#fff!important;}
[data-testid="stSidebarNavSeparator"]{border-color:rgba(255,255,255,.08);}
section[data-testid="stSidebar"] label p{font-size:11px!important;text-transform:uppercase;letter-spacing:.8px;font-weight:700!important;color:#8f9ac2!important;}
section[data-testid="stSidebar"] .react-aria-ComboBox [role="group"],section[data-testid="stSidebar"] [data-baseweb="select"]>div{
 background:rgba(255,255,255,.06)!important;border:1px solid rgba(255,255,255,.14)!important;border-radius:10px!important;}
section[data-testid="stSidebar"] input{color:#fff!important;background:transparent!important;}
section[data-testid="stSidebar"] input::placeholder{color:#8f9ac2!important;}
section[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] span,section[data-testid="stSidebar"] [data-baseweb="tag"]{
 color:#fff!important;}
section[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"]>div:not(:has(input)){background:var(--blue-600)!important;border-radius:6px;}
section[data-testid="stSidebar"] [data-testid="stExpander"]{border:1px solid rgba(255,255,255,.12);border-radius:12px;background:transparent;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover{background:rgba(255,255,255,.04);}
section[data-testid="stSidebar"] .stCaption p,section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#6b76a0!important;}
.sb-brand{display:flex;align-items:center;gap:12px;padding:4px 2px 16px;border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:10px;}
.sb-brand .chip{width:42px;height:42px;border-radius:10px;background:#fff;display:flex;align-items:center;justify-content:center;
 font-family:'Manrope','Segoe UI',Arial,sans-serif;font-weight:800;font-size:20px;color:#1370bb!important;box-shadow:0 2px 8px rgba(0,0,0,.25);}
.sb-brand strong{display:block;font-family:'Manrope','Segoe UI',Arial,sans-serif;font-size:15.5px;font-weight:800;color:#fff!important;}
.sb-brand span{display:block;font-size:11.5px;color:#8f9ac2!important;font-weight:500;}
.sb-label{font-size:10.5px;text-transform:uppercase;letter-spacing:1px;font-weight:700;color:#6b76a0!important;margin:6px 0 2px;}

/* ---------- top bar ---------- */
.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;background:#fff;border:1px solid var(--line);
 border-radius:16px;padding:14px 22px;margin-bottom:18px;box-shadow:var(--shadow);}
.topbar h1{font-size:20px!important;font-weight:800!important;margin:0!important;padding:0!important;}
.topbar .sub{font-size:12.5px;color:var(--ink-soft);font-weight:500;margin-top:2px;}
.topbar .right{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;}
.pill{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:600;padding:6px 12px;border-radius:20px;
 background:var(--gray-bg);color:var(--ink-soft);white-space:nowrap;}
.pill .d{width:7px;height:7px;border-radius:50%;background:var(--gray);}
.pill.green{background:var(--green-bg);color:var(--green);} .pill.green .d{background:var(--green);}
.pill.blue{background:var(--blue-50);color:var(--blue-700);} .pill.blue .d{background:var(--blue-600);}

/* ---------- hero ---------- */
.hero{background:linear-gradient(135deg,#14172a 0%,#27508e 130%);border-radius:20px;padding:26px 30px;color:#fff;
 position:relative;overflow:hidden;margin-bottom:18px;}
.hero:after{content:'';position:absolute;right:-60px;top:-60px;width:280px;height:280px;border-radius:50%;
 background:radial-gradient(circle,rgba(19,112,187,.4),transparent 70%);}
.hero .eyebrow{font-size:11.5px;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;color:#9fb7e8;}
.hero .title{font-family:'Manrope','Segoe UI',Arial,sans-serif;font-size:26px;font-weight:800;margin-top:6px;color:#fff;}
.hero .desc{font-size:13.5px;color:#c3cfe8;margin-top:8px;max-width:760px;line-height:1.5;}
.hero .metrics{display:flex;gap:30px;margin-top:22px;flex-wrap:wrap;position:relative;z-index:1;}
.hero .num{font-family:'Manrope','Segoe UI',Arial,sans-serif;font-size:27px;font-weight:800;font-variant-numeric:tabular-nums;color:#fff;line-height:1.1;}
.hero .lbl{font-size:11.5px;color:#a9b7d8;font-weight:600;margin-top:3px;}
.hero .delta{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:8px;vertical-align:middle;}
.hero .delta.up{background:rgba(30,142,90,.25);color:#7fe0b0;} .hero .delta.down{background:rgba(195,63,55,.28);color:#ffb2ab;}
.hero .delta.flat{background:rgba(255,255,255,.12);color:#cfd6ea;}

/* ---------- cards ---------- */
[data-testid="stPlotlyChart"],[data-testid="stDataFrame"],[class*="st-key-card"]{background:#fff;border:1px solid var(--line);
 border-radius:20px;box-shadow:var(--shadow);padding:14px 16px;}
[data-testid="stDataFrame"]{padding:8px;}
[class*="st-key-card"] [data-testid="stPlotlyChart"],[class*="st-key-card"] [data-testid="stDataFrame"]{border:none;box-shadow:none;padding:0;}
.card-title{font-family:'Manrope','Segoe UI',Arial,sans-serif;font-size:14.5px;font-weight:800;color:var(--navy-900);display:flex;justify-content:space-between;
 align-items:center;margin:2px 0 6px;}
.card-title .hint{font-size:11.5px;font-weight:600;color:var(--ink-soft);}
.section-h{font-family:'Manrope','Segoe UI',Arial,sans-serif;font-size:16px;font-weight:800;color:var(--navy-900);margin:18px 0 8px;}
.note{font-size:12px;color:var(--ink-soft);}

/* stat cards */
.stat{background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:16px 18px;height:100%;}
.stat .l{font-size:11px;text-transform:uppercase;letter-spacing:.6px;font-weight:700;color:var(--ink-soft);}
.stat .v{font-family:'Manrope','Segoe UI',Arial,sans-serif;font-size:26px;font-weight:800;color:var(--navy-900);margin-top:4px;font-variant-numeric:tabular-nums;}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:20px;margin-top:6px;}
.chip .d{width:7px;height:7px;border-radius:50%;}
.chip.green{background:var(--green-bg);color:var(--green);} .chip.green .d{background:var(--green);}
.chip.red{background:var(--red-bg);color:var(--red);} .chip.red .d{background:var(--red);}
.chip.amber{background:var(--amber-bg);color:var(--amber);} .chip.amber .d{background:var(--amber);}
.chip.gray{background:var(--gray-bg);color:var(--gray);} .chip.gray .d{background:var(--gray);}

/* ---------- tabs as segmented switch ---------- */
[data-testid="stTabs"] [role="tablist"]{gap:4px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:4px;
 width:fit-content;box-shadow:var(--shadow);margin-bottom:6px;}
[data-testid="stTab"]{border-radius:9px;padding:8px 16px!important;background:transparent;}
[data-testid="stTab"] p{font-weight:700!important;font-size:13px!important;color:var(--ink-soft);}
[data-testid="stTab"]:hover{background:var(--canvas);}
[data-testid="stTab"][aria-selected="true"]{background:var(--navy-900)!important;}
[data-testid="stTab"][aria-selected="true"] p{color:#fff!important;}
[data-testid="stTabs"] .react-aria-SelectionIndicator{display:none!important;}

/* inputs in main area */
.main [data-baseweb="select"]>div,[data-testid="stMain"] [data-baseweb="select"]>div{border-radius:10px;border-color:var(--line);background:#fff;}
[data-testid="stExpander"]{border-radius:14px;border-color:var(--line);background:#fff;}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px 16px;box-shadow:var(--shadow);}
</style>
""".replace("__FONTS__", FONTS)


def page_style():
    st.markdown(CSS, unsafe_allow_html=True)
    st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")


def topbar(title, sub, pills=()):
    ph = "".join(f'<span class="pill {c}"><span class="d"></span>{t}</span>' for t, c in pills)
    st.markdown(f'<div class="topbar"><div><h1>{title}</h1><div class="sub">{sub}</div></div>'
                f'<div class="right">{ph}</div></div>', unsafe_allow_html=True)


def hero(eyebrow, title, desc, metrics):
    """metrics: list of (value, label, delta_text or None, 'up'|'down'|'flat')."""
    items = []
    for m in metrics:
        v, lbl = m[0], m[1]
        d = f'<span class="delta {m[3]}">{m[2]}</span>' if len(m) > 2 and m[2] else ""
        items.append(f'<div><div class="num">{v}{d}</div><div class="lbl">{lbl}</div></div>')
    st.markdown(f'<div class="hero"><div class="eyebrow">{eyebrow}</div><div class="title">{title}</div>'
                f'<div class="desc">{desc}</div><div class="metrics">{"".join(items)}</div></div>',
                unsafe_allow_html=True)


def stat(container, label, value, chip=None, tone="gray"):
    c = f'<div class="chip {tone}"><span class="d"></span>{chip}</div>' if chip else ""
    container.markdown(f'<div class="stat"><div class="l">{label}</div><div class="v">{value}</div>{c}</div>',
                       unsafe_allow_html=True)


def section(title, hint=""):
    st.markdown(f'<div class="section-h">{title} <span class="note" style="font-weight:600">{hint}</span></div>',
                unsafe_allow_html=True)


def tone(delta, good_up=True):
    if delta is None or pd.isna(delta) or abs(delta) < 0.05:
        return "flat"
    return "up" if (delta > 0) == good_up else "down"


def plotly_layout(fig, height=360, legend=True):
    fig.update_layout(
        height=height, margin=dict(l=8, r=24, t=64, b=28),
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#1c2130"),
        title=dict(y=0.98, yanchor="top", x=0.0, xanchor="left",
                   font=dict(family="Manrope, Segoe UI, sans-serif", size=15, color=NAVY)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text="",
                    font=dict(size=11.5, color=INK_SOFT)) if legend else None,
        showlegend=legend, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=NAVY, font=dict(color="#fff", family="Inter")), barcornerradius=5,
    )
    fig.update_xaxes(showgrid=False, linecolor="#e2e6ef", tickfont=dict(color=INK_SOFT))
    fig.update_yaxes(gridcolor="#edf0f6", zerolinecolor="#c9cfdb", tickfont=dict(color=INK_SOFT))
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
    fig.update_layout(title=title, xaxis_title=xtitle, bargap=0.38)
    fig.update_traces(marker_line_width=0, textfont=dict(color=NAVY, size=12))
    fig.update_xaxes(range=[lo - (pad if lo < 0 else 0), hi + pad])
    fig.update_yaxes(autorange="reversed")
    return plotly_layout(fig, height or max(240, 34 * len(vals) + 110), legend=False)
