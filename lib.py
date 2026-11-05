"""Shared loaders, metric functions and UI helpers for the Porter People Analytics app."""
import re
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

# Palette
NAVY = "#030C25"      # midnight
INK_SOFT = "#6B7585"  # neutral-500
C_APR = "#8EC9F5"     # blue-light
C_OCT = "#0D558B"     # blue-deep
C_POS = "#1F8A5B"     # success
C_NEG = "#D23B3B"     # danger
C_MID = "#D98A00"     # warning
C_TEAL = "#01B8FB"    # blue-bright
WAVE_COLORS = {"Apr-2026": C_APR, "Oct-2026": C_OCT}
MIN_N = 5  # segments below this are suppressed (confidentiality + noise)


# Loading
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


# Metrics
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


# UI helpers
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


FONTS = "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&display=swap"

CSS = """
<style>
@import url('__FONTS__');
:root{--blue-bright:#01b8fb;--blue-deep:#0d558b;--midnight:#030c25;--ink:#333333;--blue-pale:#ecf6fd;--blue-light:#8ec9f5;
--blue-600:#009bd9;--blue-700:#066db8;--blue-900:#0a4672;--n0:#ffffff;--n50:#f6f8fb;--n100:#eef1f6;--n200:#dfe4ec;--n300:#c4ccd8;
--n400:#97a1b2;--n500:#6b7585;--success:#1f8a5b;--warning:#d98a00;--danger:#d23b3b;
--shadow-xs:0 1px 2px rgba(3,12,37,.06);--shadow-sm:0 1px 3px rgba(3,12,37,.08),0 1px 2px rgba(3,12,37,.04);
--shadow-md:0 4px 12px rgba(13,85,139,.10),0 2px 4px rgba(3,12,37,.05);--r-sm:6px;--r-md:10px;--r-lg:16px;
--ease:cubic-bezier(0.16,1,0.3,1);--font:'DM Sans',system-ui,-apple-system,'Segoe UI',sans-serif;}
html,body,[class*="css"],.stApp,.stApp p,.stApp label,.stApp li,.stApp span:not([data-testid="stIconMaterial"]),.stApp div{font-family:var(--font);}
[data-testid="stIconMaterial"]{font-family:"Material Symbols Rounded"!important;}
.stApp{background:var(--n50);color:var(--ink);}
h1,h2,h3,h4,h5{font-family:var(--font)!important;color:var(--midnight)!important;letter-spacing:-.02em;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1rem!important;padding-bottom:3rem;max-width:1320px;}
@keyframes rdfade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.rd-fade{animation:rdfade .35s var(--ease) both;}

/* sidebar: light filter rail */
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--n200);}
[data-testid="stSidebarHeader"] img{height:40px!important;max-width:220px;}
[data-testid="stSidebarNav"] a{border-radius:var(--r-md);margin:1px 8px;padding:6px 10px;}
[data-testid="stSidebarNav"] a span{color:var(--n500)!important;font-weight:600;font-size:14px;}
[data-testid="stSidebarNav"] a:hover{background:var(--blue-pale);}
[data-testid="stSidebarNav"] a[aria-current="page"]{background:var(--blue-pale);box-shadow:inset 3px 0 0 var(--blue-bright);}
[data-testid="stSidebarNav"] a[aria-current="page"] span{color:var(--blue-deep)!important;}
[data-testid="stSidebarNavSeparator"]{border-color:var(--n200);}
section[data-testid="stSidebar"] label p{font-size:10px!important;text-transform:uppercase;letter-spacing:.05em;font-weight:700!important;color:var(--n400)!important;}
section[data-testid="stSidebar"] .react-aria-ComboBox [role="group"],[data-testid="stMain"] .react-aria-ComboBox [role="group"],
[data-baseweb="select"]>div{background:#fff!important;border:1px solid var(--n200)!important;border-radius:var(--r-sm)!important;}
[data-testid="stMultiSelectTagsContainer"]>div:not(:has(input)){background:var(--blue-pale)!important;border:1px solid var(--blue-light);border-radius:var(--r-sm);}
[data-testid="stMultiSelectTagsContainer"]>div:not(:has(input)) span{color:var(--blue-deep)!important;font-weight:600;}
.sb-label{font-size:11px;text-transform:uppercase;letter-spacing:.14em;font-weight:700;color:var(--blue-deep);margin:4px 0 2px;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:var(--n500)!important;}
[data-testid="stExpander"]{border-radius:var(--r-md);border:1px solid var(--n200);background:#fff;}

/* header bar */
.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;background:#fff;border:1px solid var(--n200);
 border-radius:var(--r-md);padding:12px 20px;margin-bottom:16px;box-shadow:var(--shadow-xs);}
.topbar h1{font-size:16px!important;font-weight:700!important;margin:0!important;padding:0!important;line-height:1.1!important;}
.topbar .sub{font-size:12px;color:var(--n500);margin-top:2px;}
.topbar .right{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:7px 12px;border-radius:var(--r-md);
 background:#fff;border:1px solid var(--n200);color:var(--blue-deep);white-space:nowrap;}
.pill .d{width:7px;height:7px;border-radius:50%;background:var(--n400);}
.pill.green .d{background:var(--success);} .pill.blue{background:var(--blue-deep);color:#fff;border-color:var(--blue-deep);} .pill.blue .d{background:var(--blue-bright);}

/* page heading + KPI grid */
.pagehead .over{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--blue-deep);}
.pagehead .title{font-size:28px;font-weight:700;letter-spacing:-.02em;color:var(--midnight);margin-top:4px;
 background:linear-gradient(90deg,#0092ff 0%,#0a4672 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;width:fit-content;}
.pagehead .desc{font-size:13.5px;color:var(--n500);margin-top:4px;max-width:880px;line-height:1.5;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:12px;margin:16px 0 14px;}
.kpi{position:relative;background:#fff;border:1px solid var(--n200);border-radius:var(--r-md);padding:15px 16px;box-shadow:var(--shadow-sm);
 transition:box-shadow .2s var(--ease),transform .2s var(--ease);}
.kpi:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);}
.kpi .l{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--n500);}
.kpi .v{font-size:27px;font-weight:800;line-height:1.05;margin-top:7px;white-space:nowrap;color:var(--blue-deep);font-variant-numeric:tabular-nums;}
.kpi .s{font-size:11px;color:var(--n400);margin-top:5px;}
.delta{display:inline-flex;align-items:center;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-top:6px;}
.delta.up{background:#e8f6ef;color:var(--success);} .delta.down{background:#fdecec;color:var(--danger);} .delta.flat{background:var(--n100);color:var(--n500);}

/* key insight strip (one-line live summary) */
.insight{display:flex;gap:10px;align-items:flex-start;background:var(--blue-pale);border:1px solid var(--blue-light);border-radius:var(--r-md);
 padding:13px 16px;margin:0 0 16px;font-size:13.5px;line-height:1.5;color:var(--ink);}
.insight .tag{flex-shrink:0;display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.06em;
 text-transform:uppercase;color:var(--blue-deep);padding-top:2px;}
.insight b{color:var(--midnight);}

/* cards  */
[data-testid="stPlotlyChart"],[data-testid="stDataFrame"],[class*="st-key-card"]{background:#fff;border:1px solid var(--n200);
 border-radius:var(--r-md);box-shadow:var(--shadow-sm);padding:14px 16px;transition:box-shadow .2s var(--ease);}
[data-testid="stPlotlyChart"]:hover,[class*="st-key-card"]:hover{box-shadow:var(--shadow-md);}
[data-testid="stDataFrame"]{padding:6px;}
[data-testid="stPlotlyChart"]{padding:0!important;border:none!important;overflow:hidden;
 box-shadow:0 0 0 1px var(--n200),var(--shadow-sm);}
[data-testid="stPlotlyChart"]:hover{box-shadow:0 0 0 1px var(--n200),var(--shadow-md);}
[class*="st-key-card"] [data-testid="stPlotlyChart"],[class*="st-key-card"] [data-testid="stDataFrame"]{border:none;box-shadow:none;padding:0;}
.card-title{font-size:13px;font-weight:700;color:var(--midnight);display:flex;justify-content:space-between;align-items:center;margin:2px 0 8px;}
.card-title .hint{font-size:11.5px;font-weight:600;color:var(--n500);}
.section-h{display:flex;align-items:baseline;gap:12px;margin:24px 0 12px;padding-bottom:10px;border-bottom:1px solid var(--n200);}
.section-h .t{font-size:18px;font-weight:700;color:var(--midnight);} .section-h .s{font-size:12px;color:var(--n500);}
.note{font-size:12px;color:var(--n500);}
.stat{background:#fff;border:1px solid var(--n200);border-radius:var(--r-md);box-shadow:var(--shadow-sm);padding:15px 16px;height:100%;}
.stat .l{font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:700;color:var(--n500);}
.stat .v{font-size:28px;font-weight:800;color:var(--blue-deep);margin-top:6px;font-variant-numeric:tabular-nums;}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-top:6px;}
.chip .d{width:6px;height:6px;border-radius:50%;}
.chip.green{background:#e8f6ef;color:var(--success);} .chip.green .d{background:var(--success);}
.chip.red{background:#fdecec;color:var(--danger);} .chip.red .d{background:var(--danger);}
.chip.amber{background:#fdf3e0;color:var(--warning);} .chip.amber .d{background:var(--warning);}
.chip.gray{background:var(--n100);color:var(--n500);} .chip.gray .d{background:var(--n400);}

/* tabs: underline style */
[data-testid="stTabs"] [role="tablist"]{gap:28px;border-bottom:1px solid var(--n200);background:transparent;}
[data-testid="stTab"]{padding:10px 2px!important;background:transparent!important;position:relative;}
[data-testid="stTab"] p{font-weight:600!important;font-size:14px!important;color:var(--n500)!important;}
[data-testid="stTab"][aria-selected="true"] p{color:var(--blue-deep)!important;}
[data-testid="stTab"][aria-selected="true"]::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:3px;
 background:var(--blue-bright);border-radius:3px 3px 0 0;}
[data-testid="stTabs"] .react-aria-SelectionIndicator{display:none!important;}
[data-testid="stTabs"] [role="tabpanel"]{padding-top:16px;}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--n200);border-radius:var(--r-md);padding:12px 16px;box-shadow:var(--shadow-sm);}
.stButton>button,.stDownloadButton>button{border-radius:var(--r-md);font-weight:600;color:var(--blue-deep);border:1px solid var(--n200);}
.stDownloadButton>button:hover{background:var(--blue-pale);border-color:var(--blue-light);}
</style>
""".replace("__FONTS__", FONTS)


def page_style():
    st.markdown(CSS, unsafe_allow_html=True)
    st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")


def topbar(title, sub, pills=()):
    ph = "".join(f'<span class="pill {c}"><span class="d"></span>{t}</span>' for t, c in pills)
    st.markdown(f'<div><h1>{title}</h1><div class="sub">{sub}</div></div></div>'
                f'<div class="right">{ph}</div></div>', unsafe_allow_html=True)


def hero(eyebrow, title, desc, metrics):
    """Page heading + KPI card grid. metrics: (value, label[, delta_text, 'up'|'down'|'flat'])."""
    cards = []
    for m in metrics:
        v, lbl = m[0], m[1]
        d = f'<div class="delta {m[3]}">{m[2]}</div>' if len(m) > 2 and m[2] else ""
        cards.append(f'<div class="kpi"><div class="l">{lbl}</div><div class="v">{v}</div>{d}</div>')
    st.markdown(f'<div class="pagehead rd-fade"><div class="over">{eyebrow}</div><div class="title">{title}</div>'
                f'<div class="desc">{desc}</div></div><div class="kpis rd-fade">{"".join(cards)}</div>',
                unsafe_allow_html=True)


def summary(text):
    """One-line key insight that recalculates with the current filters."""
    st.markdown('<div class="insight rd-fade"><span class="tag"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 22h4M12 2a7 7 '
                '0 0 0-4 12.7c.5.4.8 1 .9 1.6h6.2c.1-.6.4-1.2.9-1.6A7 7 0 0 0 12 2z"/></svg></span>'
                f'<span>{text}</span></div>', unsafe_allow_html=True)


def stat(container, label, value, chip=None, tone="gray"):
    c = f'<div class="chip {tone}"><span class="d"></span>{chip}</div>' if chip else ""
    container.markdown(f'<div class="stat"><div class="l">{label}</div><div class="v">{value}</div>{c}</div>',
                       unsafe_allow_html=True)


def section(title, hint=""):
    st.markdown(f'<div class="section-h"><span class="t">{title}</span><span class="s">{hint}</span></div>',
                unsafe_allow_html=True)


def tone(delta, good_up=True):
    if delta is None or pd.isna(delta) or abs(delta) < 0.05:
        return "flat"
    return "up" if (delta > 0) == good_up else "down"


_MONTH = re.compile(r"^\d{4}-\d{2}$")


def _month_axis(fig):
    """'2026-04' strings render as a date axis, which clips the first and last bars. Use 'Apr-26' categories."""
    seen = set()
    for tr in fig.data:
        x = getattr(tr, "x", None)
        if x is None or len(x) == 0 or getattr(tr, "orientation", None) == "h":
            return
        xs = [str(v) for v in x]
        if not all(_MONTH.match(v) for v in xs):
            return
        seen.update(xs)
    if not seen:
        return
    lab = lambda v: pd.Timestamp(v + "-01").strftime("%b-%y")
    for tr in fig.data:
        tr.x = [lab(str(v)) for v in tr.x]
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=[lab(v) for v in sorted(seen)],
                     tickangle=0, title_text=None)


def _wrap(s, width=16):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return "<br>".join(lines)


def _wrap_categories(fig):
    """Long categorical x labels get wrapped onto two lines instead of being rotated and clipped."""
    cats = []
    for tr in fig.data:
        x = getattr(tr, "x", None)
        if x is None or getattr(tr, "orientation", None) == "h" or getattr(tr, "type", "") not in ("bar", "box"):
            return
        for v in x:
            if not isinstance(v, str):
                return
            if v not in cats:
                cats.append(v)
    if cats and max(len(c) for c in cats) > 11:
        fig.update_xaxes(tickmode="array", tickvals=cats, ticktext=[_wrap(c) for c in cats], tickangle=0)


def _legend_rows(fig, width=440):
    names = [tr.name for tr in fig.data if tr.name and tr.showlegend is not False]
    names = list(dict.fromkeys(names))
    if not names:
        return 0
    rows, used = 1, 0
    for n in names:
        w = 7 * len(str(n)) + 44
        if used and used + w > width:
            rows += 1; used = 0
        used += w
    return rows


def label_positions(x, y):
    """Put a point's label below when another label already sits close above it, so text never overlaps."""
    x, y = list(map(float, x)), list(map(float, y))
    xr = (max(x) - min(x)) or 1
    yr = (max(y) - min(y)) or 1
    order = sorted(range(len(x)), key=lambda i: -y[i])
    pos = [None] * len(x)
    for i in order:
        clash = any(pos[j] == "top center" and abs(x[i] - x[j]) < 0.6 * xr and abs(y[i] - y[j]) < 0.22 * yr
                    for j in range(len(x)) if pos[j])
        pos[i] = "bottom center" if clash else "top center"
    return pos


def plotly_layout(fig, height=360, legend=True, legend_width=440):
    _month_axis(fig)
    _wrap_categories(fig)
    rows = _legend_rows(fig, legend_width) if legend else 0
    has_title = bool(fig.layout.title.text)
    top = (40 if has_title else 12) + (24 * rows + 6 if rows else 6)
    fig.update_layout(
        height=height + max(rows - 1, 0) * 24, margin=dict(l=16, r=24, t=top, b=14, autoexpand=True),
        barcornerradius=4, uniformtext=dict(minsize=10, mode="hide"),
        font=dict(family="DM Sans, system-ui, sans-serif", size=12, color="#333333"),
        title=dict(yref="container", y=1, yanchor="top", pad=dict(t=14, l=18), xref="container", x=0.0, xanchor="left",
                   font=dict(family="DM Sans, system-ui, sans-serif", size=13, color=NAVY, weight=700)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text="",
                    font=dict(size=11.5, color=INK_SOFT)) if legend else None,
        showlegend=legend, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        colorway=["#01b8fb", "#0d558b", "#8ec9f5", "#066db8", "#0a4672", "#f8bc3b"],
        hoverlabel=dict(bgcolor=NAVY, font=dict(color="#fff", family="DM Sans")),
    )
    fig.update_traces(textangle=0, selector=dict(type="bar"))
    fig.update_xaxes(showgrid=False, linecolor="#dfe4ec", tickfont=dict(color=INK_SOFT), automargin=True,
                     title_standoff=10, title_font=dict(size=12, color=INK_SOFT))
    fig.update_yaxes(gridcolor="#eef1f6", zerolinecolor="#c4ccd8", tickfont=dict(color=INK_SOFT), automargin=True,
                     title_standoff=8, title_font=dict(size=12, color=INK_SOFT))
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
    return plotly_layout(fig, height or max(190, 36 * len(vals) + 96), legend=False)
