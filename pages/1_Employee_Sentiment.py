import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import (C_APR, C_MID, C_NEG, C_OCT, C_POS, COMPA_ORDER, GRADE_ORDER, MIN_N, Q_LABELS, TENURE_ORDER, WAVES,
                 WAVE_COLORS, apply_filters, enps, enps_table, hbar, hero, load_enps, multiselect_filter, page_style,
                 label_positions, plotly_layout, section, sort_segments, stat, summary, tone, topbar)

st.set_page_config(page_title="Employee Sentiment", layout="wide")
page_style()
r_all, e_all = load_enps()

# Sidebar filters
sb = st.sidebar
sb.markdown('<div class="sb-label">Filters</div>', unsafe_allow_html=True)
sb.caption("Empty = all.")
HR_DIMS = {
    "Company": None, "Thread": None, "Function": None, "Job Family": None, "Grade": GRADE_ORDER,
    "Location": None, "Location Type": None, "Performance Rating FY25-26": None, "Compa Band": COMPA_ORDER,
    "Intercity Jun-26 reorg": None,
}
RESP_ONLY = {"Tenure Band": TENURE_ORDER, "Mgr Changed <6m": None}
sel = {}
for col, order in HR_DIMS.items():
    sel[col] = multiselect_filter(sb, col, r_all[col], f"enps_{col}", order)
with sb.expander("Respondent-level filters"):
    for col, order in RESP_ONLY.items():
        label = {"Tenure Band": "Tenure at survey", "Mgr Changed <6m": "Manager changed in last 6 months"}[col]
        sel[col] = multiselect_filter(st, label, r_all[col], f"enps_{col}", order)
show_small = sb.toggle(f"Show segments with n < {MIN_N}", value=False)

r = apply_filters(r_all, sel)
e = apply_filters(e_all, {k: v for k, v in sel.items() if k in HR_DIMS})

active = {k: v for k, v in sel.items() if v}
ftxt = "; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in active.items()) if active else "All employees"
topbar("Employee sentiment", "eNPS pulse · April vs October 2026 · " + ftxt,
       [])

if r.empty:
    st.warning("No responses match these filters.")
    st.stop()

ra, ro = r[r["Survey Wave"] == "Apr-2026"], r[r["Survey Wave"] == "Oct-2026"]
ea, eo = enps(ra["Q1"]), enps(ro["Q1"])
inv_a, inv_o = e["Eligible Apr-2026"].sum(), e["Eligible Oct-2026"].sum()
rr_a = ra["Employee ID"].nunique() / inv_a * 100 if inv_a else np.nan
rr_o = ro["Employee ID"].nunique() / inv_o * 100 if inv_o else np.nan
na_, no_ = int(ra["Q1"].notna().sum()), int(ro["Q1"].notna().sum())
f1 = lambda x, suf="": "–" if pd.isna(x) else f"{x:.1f}{suf}"
d_enps = eo - ea if not (pd.isna(ea) or pd.isna(eo)) else np.nan
d_rr = rr_o - rr_a if not (pd.isna(rr_a) or pd.isna(rr_o)) else np.nan
det = (ro["Q1"].dropna() <= 6).mean() * 100 if ro["Q1"].notna().any() else np.nan
pro = (ro["Q1"].dropna() >= 9).mean() * 100 if ro["Q1"].notna().any() else np.nan
hero("Porter · Pulse survey · Wave 2 vs Wave 1", "Employee Net Promoter Score",
     "eNPS = % promoters (9–10) minus % detractors (0–6) on “How likely are you to recommend Porter as a place to work?”. "
     "All figures recalculate on the filters in the sidebar.",
     [(f1(eo), "eNPS · Oct-26", None if pd.isna(d_enps) else f"{d_enps:+.1f} vs Apr", tone(d_enps)),
      (f1(ea), "eNPS · Apr-26"),
      (f"{no_}", f"Responses Oct (Apr {na_})"),
      ("–" if pd.isna(rr_o) else f"{rr_o:.0f}%", "Response rate Oct",
       None if pd.isna(d_rr) else f"{d_rr:+.0f} pts", tone(d_rr)),
      ("–" if pd.isna(pro) else f"{pro:.0f}%", "Promoters Oct"),
      ("–" if pd.isna(det) else f"{det:.0f}%", "Detractors Oct")])
if any(sel[c] for c in RESP_ONLY):
    st.caption("Response rate ignores respondent-level filters (tenure, manager change), which are not defined for non-respondents.")

# Summary (recalculates with filters)
def _enps_summary():
    if pd.isna(eo):
        return "Not enough October responses in this selection to summarise."
    parts = [f"eNPS is <b>{eo:.1f}</b> in Oct" + ("" if pd.isna(ea) else f" vs {ea:.1f} in Apr (<b>{eo - ea:+.1f} pts</b>)")
             + f", n = {no_}."]
    worst = None
    for dim in ["Thread", "Function", "Location", "Tenure Band", "Compa Band"]:
        if sel.get(dim) and len(sel[dim]) == 1:
            continue
        t = enps_table(ro, [dim])
        t = t[t["n"] >= max(MIN_N, 10)]
        if len(t) > 1:
            row = t.loc[t["eNPS"].idxmin()]
            if worst is None or row["eNPS"] < worst[2]:
                worst = (dim, row[dim], row["eNPS"], int(row["n"]))
    if worst:
        parts.append(f"Weakest pocket: <b>{worst[0]} = {worst[1]}</b> at <b>{worst[2]:.0f}</b> (n {worst[3]}).")
    if len(ra) and len(ro):
        chg = (ro[list(Q_LABELS)].mean() - ra[list(Q_LABELS)].mean()).rename(index=Q_LABELS)
        k = chg.idxmin()
        if chg[k] < 0:
            parts.append(f"Biggest item drop: <b>{k}</b> ({chg[k]:+.2f}).")
    return " ".join(parts)


summary(_enps_summary())

tab1, tab2, tab3, tab4 = st.tabs(["Wave comparison", "Drill-down", "Drivers", "Attrition link"])

# Wave comparison
with tab1:
    c1, c2 = st.columns([1, 1.4])
    with c1:
        t = enps_table(r, ["Survey Wave"])
        mix = r.groupby("Survey Wave")["eNPS Group"].value_counts(normalize=True).mul(100).rename("pct").reset_index()
        fig = px.bar(mix, x="Survey Wave", y="pct", color="eNPS Group", text_auto=".0f",
                     category_orders={"eNPS Group": ["Detractor", "Passive", "Promoter"], "Survey Wave": WAVES},
                     color_discrete_map={"Detractor": C_NEG, "Passive": C_APR, "Promoter": C_POS},
                     title="Promoter / passive / detractor mix (%)")
        for _, row in t.iterrows():
            fig.add_annotation(x=row["Survey Wave"], y=104, text=f"eNPS {row['eNPS']:.1f} · n={row['n']}",
                               showarrow=False, font=dict(size=12))
        fig.update_yaxes(range=[0, 110], title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(plotly_layout(fig, 380), width="stretch")
    with c2:
        items = r.groupby("Survey Wave")[list(Q_LABELS)].mean().rename(columns=Q_LABELS).T.reset_index()
        items = items.melt(id_vars="index", var_name="Wave", value_name="Mean (1-5)")
        fig = px.bar(items, x="index", y="Mean (1-5)", color="Wave", barmode="group", text_auto=".2f",
                     color_discrete_map=WAVE_COLORS, title="Driver items, mean score (1–5)")
        fig.update_xaxes(title=None)
        fig.update_yaxes(range=[1, 5])
        st.plotly_chart(plotly_layout(fig, 380), width="stretch")

    section("Change by segment", "pick any dimension")
    dim = st.selectbox("Compare waves by", ["Thread", "Function", "Grade", "Location", "Location Type", "Tenure Band",
                                            "Compa Band", "Company", "Job Family", "Performance Rating FY25-26",
                                            "Mgr Changed <6m", "Intercity Jun-26 reorg"], key="wave_dim")
    t = enps_table(r, [dim, "Survey Wave"])
    if not show_small:
        t = t[t["n"] >= MIN_N]
    piv = t.pivot(index=dim, columns="Survey Wave", values=["eNPS", "n"])
    piv.columns = [f"{a} {b}" for a, b in piv.columns]
    piv = piv.reset_index()
    for w in WAVES:
        for m in ("eNPS", "n"):
            if f"{m} {w}" not in piv:
                piv[f"{m} {w}"] = np.nan
    piv["Δ eNPS"] = piv["eNPS Oct-2026"] - piv["eNPS Apr-2026"]
    piv = sort_segments(piv, dim)
    fig = go.Figure()
    for w in WAVES:
        fig.add_bar(x=piv[dim], y=piv[f"eNPS {w}"], name=w, marker_color=WAVE_COLORS[w],
                    customdata=piv[f"n {w}"], hovertemplate="%{x}<br>eNPS %{y:.1f}<br>n=%{customdata}<extra>" + w + "</extra>")
    fig.update_layout(barmode="group", title=f"eNPS by {dim}, Apr vs Oct")
    st.plotly_chart(plotly_layout(fig, 380), width="stretch")
    st.dataframe(piv.style.format({c: "{:.1f}" for c in piv.columns if "eNPS" in c} |
                                  {c: "{:.0f}" for c in piv.columns if c.startswith("n ")}, na_rep="–")
                 .background_gradient(subset=["Δ eNPS"], cmap="RdYlGn", vmin=-30, vmax=30),
                 width="stretch", hide_index=True)

# ------------------------------------------------------------------ drill-down
with tab2:
    st.markdown("Start from the overall score, pick a dimension, then select one segment to break it down again.")
    dims = ["Thread", "Function", "Location", "Grade", "Tenure Band", "Compa Band", "Location Type",
            "Performance Rating FY25-26", "Mgr Changed <6m", "Reporting Manager ID", "Company"]
    wave = st.radio("Wave", WAVES + ["Both (Oct − Apr change)"], index=1, horizontal=True)
    c1, c2 = st.columns(2)
    d1 = c1.selectbox("Level 1 dimension", dims, index=0)

    def level_table(df, dim):
        if wave.startswith("Both"):
            t = enps_table(df, [dim, "Survey Wave"]).pivot(index=dim, columns="Survey Wave", values=["eNPS", "n"])
            t.columns = [f"{a} {b}" for a, b in t.columns]
            for w in WAVES:
                for m in ("eNPS", "n"):
                    if f"{m} {w}" not in t:
                        t[f"{m} {w}"] = np.nan
            t = t.reset_index()
            t["metric"] = t["eNPS Oct-2026"] - t["eNPS Apr-2026"]
            t["n"] = t[["n Apr-2026", "n Oct-2026"]].min(axis=1)
        else:
            t = enps_table(df[df["Survey Wave"] == wave], [dim])
            t["metric"] = t["eNPS"]
        if not show_small:
            t = t[t["n"] >= MIN_N]
        return sort_segments(t, dim)

    def drill_chart(t, dim, title):
        mlabel = "Δ eNPS (Oct − Apr)" if wave.startswith("Both") else f"eNPS {wave}"
        colors = [C_NEG if v < 0 else C_POS for v in t["metric"].fillna(0)]
        return hbar(t[dim].astype(str), t["metric"], t["n"], title, mlabel, colors)

    t1 = level_table(r, d1)
    overall = enps(r[r["Survey Wave"] == wave]["Q1"]) if not wave.startswith("Both") else eo - ea
    c1.plotly_chart(drill_chart(t1, d1, f"Overall {overall:.1f} → by {d1}"), width="stretch")
    seg = c2.selectbox(f"Drill into {d1}", t1[d1].astype(str).tolist(), key="seg1")
    d2 = c2.selectbox("Level 2 dimension", [d for d in dims if d != d1], index=1)
    sub = r[r[d1].astype(str) == seg]
    t2 = level_table(sub, d2)
    c2.plotly_chart(drill_chart(t2, d2, f"{d1} = {seg} → by {d2}"), width="stretch")

    with st.expander(f"Item heatmap for {d1} = {seg}, split by {d2}"):
        w = sub if wave.startswith("Both") else sub[sub["Survey Wave"] == wave]
        h = enps_table(w, [d2])
        if not show_small:
            h = h[h["n"] >= MIN_N]
        h = sort_segments(h, d2).set_index(d2)
        st.dataframe(h.style.format("{:.1f}", na_rep="–").format({"n": "{:.0f}"})
                     .background_gradient(subset=list(Q_LABELS.values()), cmap="RdYlGn", vmin=1.5, vmax=4)
                     .background_gradient(subset=["eNPS"], cmap="RdYlGn", vmin=-50, vmax=50),
                     width="stretch")

# Drivers
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        corr = r[["Q1"] + list(Q_LABELS)].corr()["Q1"].drop("Q1").rename(index=Q_LABELS)
        chg = (r[r["Survey Wave"] == "Oct-2026"][list(Q_LABELS)].mean() -
               r[r["Survey Wave"] == "Apr-2026"][list(Q_LABELS)].mean()).rename(index=Q_LABELS)
        d = pd.DataFrame({"Correlation with Q1": corr, "Change Apr→Oct": chg}).reset_index(names="Item")
        fig = px.scatter(d, x="Change Apr→Oct", y="Correlation with Q1", text="Item",
                         title="Key-driver map: importance vs movement")
        fig.update_traces(marker=dict(size=14, color=C_OCT), cliponaxis=False,
                          textposition=label_positions(d["Change Apr→Oct"], d["Correlation with Q1"]))
        xr = d["Change Apr→Oct"]
        fig.update_xaxes(range=[min(xr.min(), 0) - 0.08, max(xr.max(), 0) + 0.08])
        yr = d["Correlation with Q1"]
        fig.update_yaxes(range=[yr.min() - 0.02, yr.max() + 0.03])
        fig.add_vline(x=0, line_dash="dot", line_color="gray")
        st.plotly_chart(plotly_layout(fig, 380, legend=False), width="stretch")
        st.caption("Items further left fell most; higher = more tightly linked to recommending Porter.")
    with c2:
        th = r.dropna(subset=["Comment Theme"]).groupby(["Survey Wave", "Comment Theme"]).size().rename("n").reset_index()
        fig = px.bar(th, x="n", y="Comment Theme", color="Survey Wave", barmode="group", orientation="h",
                     color_discrete_map=WAVE_COLORS, title="Comment themes (keyword-coded)")
        fig.update_yaxes(title=None)
        fig.update_xaxes(title="Comments")
        st.plotly_chart(plotly_layout(fig, 380), width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        t = enps_table(r, ["Compa Band", "Survey Wave"])
        t = t[t["n"] >= MIN_N] if not show_small else t
        fig = px.bar(t, x="Compa Band", y="eNPS", color="Survey Wave", barmode="group", text_auto=".0f",
                     category_orders={"Compa Band": COMPA_ORDER}, color_discrete_map=WAVE_COLORS,
                     hover_data=["n", "Fair pay"], title="eNPS by compa-ratio band (CTC ÷ FY26 band mid)")
        st.plotly_chart(plotly_layout(fig, 340), width="stretch")
    with c2:
        t = enps_table(r, ["Tenure Band", "Survey Wave"])
        t = t[t["n"] >= MIN_N] if not show_small else t
        fig = px.bar(t, x="Tenure Band", y="eNPS", color="Survey Wave", barmode="group", text_auto=".0f",
                     category_orders={"Tenure Band": TENURE_ORDER}, color_discrete_map=WAVE_COLORS,
                     hover_data=["n", "Onboarding & tools"], title="eNPS by tenure at survey")
        st.plotly_chart(plotly_layout(fig, 340), width="stretch")
    with st.expander("Comment browser"):
        cm = r.dropna(subset=["Comment"])[["Survey Wave", "Thread", "Location", "Grade", "Q1", "Comment Theme", "Comment"]]
        th_sel = st.multiselect("Theme", sorted(cm["Comment Theme"].dropna().unique()), placeholder="All")
        if th_sel:
            cm = cm[cm["Comment Theme"].isin(th_sel)]
        st.dataframe(cm, width="stretch", hide_index=True, height=300)

# Attrition
with tab4:
    st.markdown("Exits use the HR filters above (Thread, Function, Grade, …). FY26 = exits on/after 01-Apr-2026.")
    ex = e[e["Date of Exit"] >= "2026-04-01"]
    k = st.columns(4)
    nreg = int((ex["Exit Classification"] == "Regrettable").sum())
    hc = e[(e["Date of Joining"] <= "2026-04-01")].shape[0]
    stat(k[0], "FY26 exits", len(ex))
    stat(k[1], "Voluntary", int((ex["Exit Type"] == "Voluntary").sum()))
    stat(k[2], "Regrettable", nreg, f"{nreg / len(ex) * 100:.0f}% of exits" if len(ex) else None, "red")
    stat(k[3], "Exits ÷ Apr headcount", f"{len(ex) / hc * 100:.1f}%" if hc else "–")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        m = ex.groupby(["Exit Month", "Exit Classification"]).size().rename("Exits").reset_index()
        fig = px.bar(m, x="Exit Month", y="Exits", color="Exit Classification",
                     color_discrete_map={"Regrettable": C_NEG, "Non-Regrettable": C_APR}, title="Exits by month")
        fig.update_xaxes(title=None)
        st.plotly_chart(plotly_layout(fig, 340), width="stretch")
    with c2:
        a = r[r["Survey Wave"] == "Apr-2026"].copy()
        a["Left voluntarily after Apr survey"] = (a["Exit Type"] == "Voluntary") & (a["Date of Exit"] > "2026-04-17")
        t = a.groupby("eNPS Group").agg(n=("Employee ID", "size"),
                                        rate=("Left voluntarily after Apr survey", "mean")).reset_index()
        t["rate"] *= 100
        fig = px.bar(t, x="eNPS Group", y="rate", text_auto=".1f",
                     category_orders={"eNPS Group": ["Detractor", "Passive", "Promoter"]},
                     color="eNPS Group", color_discrete_map={"Detractor": C_NEG, "Passive": C_APR, "Promoter": C_POS},
                     hover_data=["n"], title="% of April respondents who later left voluntarily")
        fig.update_yaxes(title="% left")
        fig.update_xaxes(title=None)
        st.plotly_chart(plotly_layout(fig, 340, legend=False), width="stretch")
