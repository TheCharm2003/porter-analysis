import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import (C_APR, C_MID, C_NEG, C_OCT, C_POS, C_TEAL, GRADE_ORDER, NAVY, apply_filters, hbar, hero,
                 load_recruitment, multiselect_filter, page_style, label_positions, plotly_layout, section, sort_segments, stat, summary, topbar)

st.set_page_config(page_title="Recruitment · Porter", page_icon="🧲", layout="wide")
page_style()
q_all, c_all, rec = load_recruitment()

# Sidebar
sb = st.sidebar
sb.markdown('<div class="sb-label">Filters</div>', unsafe_allow_html=True)
sb.caption("Empty = all.")
months = sorted(q_all["Req Month"].dropna().unique())
m0, m1 = sb.select_slider("Req raised month", options=months, value=(months[0], months[-1]))
REQ_DIMS = {"Thread": None, "Function": None, "Grade": GRADE_ORDER, "Location": None, "Recruiter": None,
            "Criticality": None, "Position Type": None, "Job Family": None, "Req Status": None}
sel = {col: multiselect_filter(sb, col, q_all[col], f"rec_{col}", order) for col, order in REQ_DIMS.items()}
src_sel = multiselect_filter(sb, "Source", c_all["Source"], "rec_src")
sb.caption("**Source** filters candidate-level views (funnel, offers) to those channels, and requisition-level views "
           "(time to fill, SLA) to requisitions whose hire came from them.")

q = apply_filters(q_all, sel)
q = q[(q["Req Month"] >= m0) & (q["Req Month"] <= m1)]
c = c_all[c_all["Req ID"].isin(q["Req ID"])]
if src_sel:
    c = c[c["Source"].isin(src_sel)]
    q = q[q["Hire Source"].isin(src_sel)]
f = q[q["Filled"]]

active = {k: v for k, v in sel.items() if v}
if src_sel:
    active["Source"] = src_sel
txt = f"Reqs raised {m0} → {m1}"
txt += " · " + ("; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in active.items()) if active else "all requisitions")
topbar("Recruitment performance", txt,
       [(f"{len(active)} filter(s) active", "blue" if active else "")])
if q.empty:
    st.warning("No requisitions match these filters.")
    st.stop()

open_q = q[q["Req Status"] == "Open"]
offers = c[c["Reached Offer"]]
acc_rate = (offers["Offer Status"] == "Accepted").mean() * 100 if len(offers) else np.nan
sla = f["Within SLA (recalc)"].astype(float).mean() * 100 if len(f) else np.nan
ob = int((q["SLA Status (recalc)"] == "Open - Breached").sum())
hero("Porter · Talent Acquisition · FY26 requisitions", "Hiring scorecard",
     "Time to fill = days from Req Raised On to the hired candidate’s offer acceptance. SLA = 30 / 45 / 60 days for "
     "TBA–G2 / G3–G5 / G6+, recomputed from the README rule.",
     [(f"{len(f)} / {len(q)}", "Requisitions filled"),
      (f"{f['TTF (days)'].median():.0f} d" if len(f) else "–", "Median time to fill"),
      ("–" if pd.isna(sla) else f"{sla:.0f}%", "Filled within SLA",
       None if pd.isna(sla) else ("on track" if sla >= 85 else "below 85%"), "up" if not pd.isna(sla) and sla >= 85 else "down"),
      (f"{ob}", f"Open reqs past SLA (of {len(open_q)})"),
      ("–" if pd.isna(acc_rate) else f"{acc_rate:.0f}%", f"Offer acceptance ({len(offers)})"),
      (f"{int(c['Joined'].sum())}", "Joiners"),
      (f"₹{q['Agency Fee (INR)'].sum() / 1e5:.1f}L", "Agency fees")])

# Live one-line summary (recalculates with filters)
def _rec_summary():
    if not len(f):
        return f"No filled requisitions in this selection; {len(open_q)} still open, {ob} past SLA."
    parts = [f"<b>{len(f)}</b> of {len(q)} reqs filled in a median <b>{f['TTF (days)'].median():.0f} days</b>, "
             f"<b>{sla:.0f}%</b> within SLA."]
    br = f[f["Within SLA (recalc)"].astype(float) == 0]
    if len(br):
        applied = br["Hired Candidate"].map(c_all.set_index("Candidate ID")["Applied On"])
        restart = ((applied - br["Req Raised On"]).dt.days > 20).mean() * 100
        parts.append(f"<b>{restart:.0f}%</b> of the {len(br)} breaches came from a restarted search.")
    g = f.groupby("Grade")["TTF (days)"].agg(["median", "size"])
    g = g[g["size"] >= 3]
    if len(g) > 1:
        parts.append(f"Slowest grade: <b>{g['median'].idxmax()}</b> ({g['median'].max():.0f} d, n {int(g.loc[g['median'].idxmax(), 'size'])}).")
    if len(offers):
        dec = (offers["Offer Status"] == "Declined").mean() * 100
        parts.append(f"Offer decline rate <b>{dec:.0f}%</b>.")
    return " ".join(parts)


summary(_rec_summary())

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Monthly trends", "Drill-down", "Funnel & sources", "Where time goes",
                                         "Recruiters & interviewers"])

# Trends
with tab1:
    raised = q.groupby("Req Month").size().rename("Reqs raised")
    acc = c[c["Offer Accepted"]].assign(m=lambda d: d["Offer Response On"].dt.to_period("M").astype(str)) \
        .groupby("m").size().rename("Offers accepted")
    joins = c[c["Joined"] & c["Actual DOJ"].notna()].assign(m=lambda d: d["Actual DOJ"].dt.to_period("M").astype(str)) \
        .groupby("m").size().rename("Joiners")
    t = pd.concat([raised, acc, joins], axis=1).fillna(0).sort_index()
    t = t[t.index <= "2026-10"]
    fig = go.Figure()
    for col, colr in zip(t.columns, [C_APR, C_OCT, C_TEAL]):
        fig.add_bar(x=t.index, y=t[col], name=col, marker_color=colr)
    fig.update_layout(barmode="group", title="Hiring volume by month")
    st.plotly_chart(plotly_layout(fig, 340), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        m = f.groupby("Req Month").agg(TTF=("TTF (days)", "median"), SLA=("Within SLA (recalc)", "mean"),
                                       n=("Req ID", "size")).reset_index()
        fig = go.Figure()
        fig.add_bar(x=m["Req Month"], y=m["TTF"], name="Median TTF (days)", marker_color=C_OCT,
                    text=[f"n={n}" for n in m["n"]], textposition="inside", insidetextanchor="start")
        fig.add_scatter(x=m["Req Month"], y=m["SLA"] * 100, name="% within SLA", yaxis="y2", mode="lines+markers",
                        line=dict(color=C_MID, width=3))
        fig.update_layout(title="Time to fill by month raised (filled reqs)",
                          yaxis2=dict(overlaying="y", side="right", range=[0, 110], tickvals=[0, 25, 50, 75, 100],
                                      ticksuffix="%", title=None, showgrid=False, automargin=True,
                                      tickfont=dict(color="#6B7585")))
        fig.update_layout(yaxis_title="Median days")
        fig = plotly_layout(fig, 340)
        fig.update_layout(yaxis2=dict(ticksuffix="%"))
        st.plotly_chart(fig, width="stretch")
        st.caption("Recent months look faster because only quickly-filled reqs have closed yet (right-censoring).")
    with c2:
        s = q.groupby(["Req Month", "SLA Status (recalc)"]).size().rename("n").reset_index()
        fig = px.bar(s, x="Req Month", y="n", color="SLA Status (recalc)", title="SLA status by month raised",
                     color_discrete_map={"Within SLA": C_POS, "Breached": C_NEG, "Open - Breached": "#F08C8C",
                                         "Open - Within SLA": "#9CC7EA", "On Hold / Archived": C_APR})
        st.plotly_chart(plotly_layout(fig, 340), width="stretch")

# Drill-down
with tab2:
    dims = ["Thread", "Function", "Grade", "Location", "Recruiter", "Criticality", "Position Type", "Job Family",
            "Hire Source", "Hiring Manager"]
    metric = st.radio("Metric", ["Median TTF (days)", "% filled within SLA", "Open & past SLA (count)",
                                 "Requisitions (count)"], horizontal=True)

    def seg_table(df, dim):
        g = df.groupby(dim)
        t = pd.DataFrame({
            "Reqs": g.size(),
            "Filled": g["Filled"].sum(),
            "Median TTF (days)": g.apply(lambda d: d.loc[d["Filled"], "TTF (days)"].median(), include_groups=False),
            "% filled within SLA": g.apply(lambda d: d.loc[d["Filled"], "Within SLA (recalc)"].astype(float).mean() * 100,
                                           include_groups=False),
            "Open & past SLA (count)": g.apply(lambda d: (d["SLA Status (recalc)"] == "Open - Breached").sum(),
                                               include_groups=False),
            "Offer declines": g["Declines"].sum(),
        }).reset_index()
        t["Requisitions (count)"] = t["Reqs"]
        return sort_segments(t, dim)

    def chart(t, dim, title):
        col = metric
        vals = t[col]
        if col == "% filled within SLA":
            colors = [C_NEG if v < 70 else (C_MID if v < 85 else C_POS) for v in vals.fillna(100)]
        elif col == "Median TTF (days)":
            colors = [C_NEG if v > 45 else (C_MID if v > 30 else C_POS) for v in vals.fillna(0)]
        else:
            colors = C_OCT
        return hbar(t[dim].astype(str), vals, t["Reqs"], title, col, colors)

    c1, c2 = st.columns(2)
    d1 = c1.selectbox("Level 1 dimension", dims, index=2)
    t1 = seg_table(q, d1)
    c1.plotly_chart(chart(t1, d1, f"By {d1}"), width="stretch")
    seg = c2.selectbox(f"Drill into {d1}", t1[d1].astype(str).tolist())
    d2 = c2.selectbox("Level 2 dimension", [d for d in dims if d != d1], index=0)
    sub = q[q[d1].astype(str) == seg]
    t2 = seg_table(sub, d2)
    c2.plotly_chart(chart(t2, d2, f"{d1} = {seg} → by {d2}"), width="stretch")
    with st.expander(f"Requisitions in {d1} = {seg}"):
        cols = ["Req ID", "Req Raised On", "Thread", "Function", "Designation", "Grade", "Location", "Recruiter",
                "Hiring Manager", "Req Status", "SLA (Days)", "TTF (days)", "Age (days)", "SLA Status (recalc)",
                "SLA Status (System)", "Applicants", "Offers", "Declines", "Hire Source"]
        st.dataframe(sub[cols].sort_values("Age (days)", ascending=False), width="stretch", hide_index=True)
        st.download_button("Download CSV", sub[cols].to_csv(index=False), f"reqs_{d1}_{seg}.csv")

# Funnel & sources
with tab3:
    c1, c2 = st.columns([1, 1.2])
    with c1:
        stages = [("Applied", len(c)), ("Shortlisted", c["Reached Shortlist"].sum()),
                  ("Screened", c["Reached Screening"].sum()), ("R1 interview", c["Reached R1"].sum()),
                  ("R2 interview", c["Reached R2"].sum()), ("Offer", c["Reached Offer"].sum()),
                  ("Accepted", c["Offer Accepted"].sum()), ("Joined", c["Joined"].sum())]
        fig = go.Figure(go.Funnel(y=[s for s, _ in stages], x=[n for _, n in stages], textinfo="value+percent previous",
                                  marker_color=["#0a4672", "#0d558b", "#066db8", "#009bd9", "#01b8fb", "#4aa9ef", "#8ec9f5", "#1f8a5b"]))
        fig.update_layout(title="Candidate funnel (stage reached)")
        st.plotly_chart(plotly_layout(fig, 420, legend=False), width="stretch")
    with c2:
        s = c.groupby("Source").agg(Applicants=("Candidate ID", "size"),
                                    Shortlist_pct=("Reached Shortlist", "mean"),
                                    Offers=("Reached Offer", "sum"),
                                    Accepted=("Offer Accepted", "sum"),
                                    Joined=("Joined", "sum")).reset_index()
        s["Offer accept %"] = s["Accepted"] / s["Offers"].replace(0, np.nan) * 100
        s["Joins per 100 applicants"] = s["Joined"] / s["Applicants"] * 100
        s["Shortlist %"] = s["Shortlist_pct"] * 100
        fig = px.scatter(s, x="Applicants", y="Joins per 100 applicants", size="Joined", text="Source",
                         title="Source volume vs yield (bubble = joiners)", size_max=40)
        fig.update_traces(marker_color=C_OCT, cliponaxis=False,
                          textposition=label_positions(s["Applicants"], s["Joins per 100 applicants"]))
        st.plotly_chart(plotly_layout(fig, 420, legend=False), width="stretch")
    st.dataframe(s.drop(columns="Shortlist_pct").style.format({"Shortlist %": "{:.0f}", "Offer accept %": "{:.0f}",
                                                                "Joins per 100 applicants": "{:.1f}"}, na_rep="–"),
                 width="stretch", hide_index=True)
    if (c["Source"] == "Agency").any():
        ag = c[c["Source"] == "Agency"].groupby("Agency Name").agg(Applicants=("Candidate ID", "size"),
                                                                   Offers=("Reached Offer", "sum"),
                                                                   Declined=("Offer Status", lambda x: (x == "Declined").sum()),
                                                                   Joined=("Joined", "sum")).reset_index()
        fee = q[(q["Hire Source"] == "Agency")].groupby("Hire Agency")["Agency Fee (INR)"].sum()
        ag["Fees (₹L)"] = ag["Agency Name"].map(fee).fillna(0) / 1e5
        section("Agencies")
        st.dataframe(ag.style.format({"Fees (₹L)": "{:.1f}"}), width="stretch", hide_index=True)

    section("Offer outcomes vs pay gap to candidate expectation")
    o = c[c["Reached Offer"]].copy()
    o["Outcome"] = np.select([o["Candidate Status"] == "Not Joined - Backed Out", o["Offer Status"] == "Declined",
                              o["Offer Status"] == "Accepted"], ["Backed out", "Declined", "Accepted"], "Pending")
    o["Offer vs expected"] = pd.cut(o["Offer vs Expected %"], [-100, -10, -5, 0, 100],
                                    labels=["≥10% below", "5–10% below", "0–5% below", "At/above"]).astype(str)
    t = o.groupby(["Offer vs expected", "Outcome"]).size().rename("n").reset_index()
    fig = px.bar(t, x="Offer vs expected", y="n", color="Outcome", barmode="stack", text_auto=True,
                 category_orders={"Offer vs expected": ["≥10% below", "5–10% below", "0–5% below", "At/above"]},
                 color_discrete_map={"Accepted": C_POS, "Declined": C_NEG, "Backed out": C_MID, "Pending": C_APR})
    fig.update_traces(textposition="inside")
    fig.update_xaxes(title=None)
    st.plotly_chart(plotly_layout(fig, 320), width="stretch")

# Where time goes
with tab4:
    hired = c[c["Candidate ID"].isin(f["Hired Candidate"])]
    steps = [("Req raised → hire applied", "Req Raised On", "Applied On"),
             ("Applied → shortlisted", "Applied On", "Shortlisted On"),
             ("Shortlisted → screened", "Shortlisted On", "Screening Done On"),
             ("Screened → R1", "Screening Done On", "R1 Interview Date"),
             ("R1 → feedback", "R1 Interview Date", "R1 Feedback Submitted On"),
             ("Feedback → R2", "R1 Feedback Submitted On", "R2 Interview Date"),
             ("R2 → offer", "R2 Interview Date", "Offer Released On"),
             ("Offer → acceptance", "Offer Released On", "Offer Response On")]
    rows = []
    for lab, a, b in steps:
        d = (hired[b] - hired[a]).dt.days
        d = d[d >= 0]
        rows.append(dict(Stage=lab, Median=d.median(), Mean=d.mean(), P90=d.quantile(.9), n=len(d)))
    st_t = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_bar(y=st_t["Stage"], x=st_t["Mean"], orientation="h", name="Mean days", marker_color=C_OCT)
    fig.add_scatter(y=st_t["Stage"], x=st_t["P90"], mode="markers", name="90th percentile",
                    marker=dict(color=C_NEG, size=10, symbol="line-ns-open", line=dict(width=3)))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=f"Time in each stage for the {len(hired)} hired candidates")
    st.plotly_chart(plotly_layout(fig, 380), width="stretch")
    st.dataframe(st_t.style.format({"Median": "{:.0f}", "Mean": "{:.1f}", "P90": "{:.0f}"}), width="stretch",
                 hide_index=True)

    f2 = f.copy()
    f2["Hire applied"] = f2["Hired Candidate"].map(c.set_index("Candidate ID")["Applied On"])
    f2["Sourcing lag"] = (f2["Hire applied"] - f2["Req Raised On"]).dt.days
    f2["Hire sourced"] = np.where(f2["Sourcing lag"] > 20, "Late (>20 d after req opened)", "From first slate (≤20 d)")
    f2["Lost an offer first"] = np.where((f2["Declines"] + f2["Backouts"]) > 0, "Yes", "No")
    c1, c2 = st.columns(2)
    for col, box, title in [("Hire sourced", c1, "First-slate hires vs late-sourced hires"),
                            ("Lost an offer first", c2, "Reqs where an earlier offer was declined / backed out")]:
        t = f2.groupby(col).agg(Reqs=("Req ID", "size"), TTF=("TTF (days)", "median"),
                                SLA=("Within SLA (recalc)", "mean")).reset_index()
        t["SLA"] *= 100
        fig = go.Figure(go.Bar(x=t[col], y=t["TTF"], marker_color=[C_POS, C_NEG][:len(t)] if col == "Hire sourced" else [C_POS, C_NEG][:len(t)],
                               text=[f"{v:.0f} d · {s:.0f}% in SLA · n={n}" for v, s, n in zip(t["TTF"], t["SLA"], t["Reqs"])],
                               textposition="outside", cliponaxis=False))
        fig.update_layout(title=title, yaxis_title="Median TTF (days)")
        box.plotly_chart(plotly_layout(fig, 320, legend=False), width="stretch")

# Recruiters & interviewers
with tab5:
    acc = c[c["Offer Accepted"]].assign(Month=lambda d: d["Offer Response On"].dt.to_period("M").astype(str))
    a = acc.groupby(["Recruiter", "Month"]).size().rename("Accepted").reset_index()
    a = a.merge(rec.rename(columns={"Recruiter Name": "Recruiter"})[["Recruiter", "Monthly Offer Target"]], on="Recruiter")
    sc = q.groupby("Recruiter").agg(Reqs=("Req ID", "size"), Open=("Req Status", lambda s: (s == "Open").sum()),
                                    Filled=("Filled", "sum")).reset_index()
    sc = sc.merge(f.groupby("Recruiter").agg(TTF=("TTF (days)", "median"),
                                             SLA=("Within SLA (recalc)", "mean")).reset_index(), on="Recruiter", how="left")
    mm = a.groupby("Recruiter")["Accepted"].sum() / max(a["Month"].nunique(), 1)
    sc["Accepted / month"] = sc["Recruiter"].map(mm)
    sc = sc.merge(rec.rename(columns={"Recruiter Name": "Recruiter"})[["Recruiter", "Monthly Offer Target"]], on="Recruiter",
                  how="left")
    sc["% of target"] = sc["Accepted / month"] / sc["Monthly Offer Target"] * 100
    sc["SLA"] *= 100
    section("Recruiter scorecard")
    st.dataframe(sc.rename(columns={"TTF": "Median TTF", "SLA": "% in SLA"}).style
                 .format({"Median TTF": "{:.0f}", "% in SLA": "{:.0f}", "Accepted / month": "{:.1f}", "% of target": "{:.0f}"},
                         na_rep="–")
                 .background_gradient(subset=["% in SLA"], cmap="RdYlGn", vmin=40, vmax=100),
                 width="stretch", hide_index=True)
    st.caption("Accepted / month averages over the months in view. Targets are per recruiter per month (Recruiters sheet).")
    if not a.empty:
        fig = px.line(a, x="Month", y="Accepted", color="Recruiter", markers=True, title="Accepted offers per month")
        st.plotly_chart(plotly_layout(fig, 340, legend_width=900), width="stretch")

    section("Round-1 interviewers", "feedback turnaround")
    iv = c.dropna(subset=["R1 Interview Date"]).groupby(["R1 Interviewer ID", "R1 Interviewer"]).agg(
        Interviews=("Candidate ID", "size"), Median_lag=("R1 Feedback Lag (days)", "median"),
        Mean_lag=("R1 Feedback Lag (days)", "mean"),
        Over_3d=("R1 Feedback Lag (days)", lambda s: (s > 3).mean() * 100),
        Pending=("R1 Result", lambda s: (s == "Pending Feedback").sum())).reset_index()
    iv = iv.sort_values("Mean_lag", ascending=False)
    fig = px.bar(iv.head(15), x="Mean_lag", y="R1 Interviewer", orientation="h", hover_data=["Interviews", "Over_3d"],
                 title="Slowest R1 interviewers (mean days from interview to feedback)")
    fig.update_traces(marker_color=[C_NEG if v > 3 else C_APR for v in iv.head(15)["Mean_lag"]])
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="Mean days to feedback")
    st.plotly_chart(plotly_layout(fig, 26 * len(iv.head(15)) + 110, legend=False), width="stretch")
    st.dataframe(iv.rename(columns={"Median_lag": "Median lag (d)", "Mean_lag": "Mean lag (d)", "Over_3d": "% > 3 days"})
                 .style.format({"Median lag (d)": "{:.0f}", "Mean lag (d)": "{:.1f}", "% > 3 days": "{:.0f}"}, na_rep="–"),
                 width="stretch", hide_index=True, height=280)
