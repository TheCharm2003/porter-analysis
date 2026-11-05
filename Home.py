import streamlit as st

from lib import enps, hero, load_dq, load_enps, load_recruitment, page_style, section, stat, summary, tone, topbar

st.set_page_config(page_title="Porter People Analytics", layout="wide")
page_style()

r, e = load_enps()
q, c, rec = load_recruitment()
dq = load_dq()
a, o = r[r["Survey Wave"] == "Apr-2026"]["Q1"], r[r["Survey Wave"] == "Oct-2026"]["Q1"]
f = q[q["Filled"]]
ea, eo = enps(a), enps(o)
sla = f["Within SLA (recalc)"].astype(float).mean() * 100

topbar("Overview", "Executive summary across sentiment and hiring",
       [])
hero("Porter · People Analytics · FY26 H1", "People scorecard",
     "Employee sentiment from the April and October 2026 pulse surveys, linked to HRMS records, alongside Talent "
     "Acquisition performance for requisitions raised this financial year.",
     [(f"{eo:.1f}", "eNPS · Oct-26", f"{eo - ea:+.1f} vs Apr", tone(eo - ea)),
      (f"{o.notna().sum()}", "Survey responses · Oct"),
      (f"{f['TTF (days)'].median():.0f} d", "Median time to fill"),
      (f"{sla:.0f}%", "Filled within SLA", "below 85%" if sla < 85 else "on track", "down" if sla < 85 else "up"),
      (f"{int((q['SLA Status (recalc)'] == 'Open - Breached').sum())}", "Open reqs past SLA")])

summary(f"eNPS moved <b>{ea:.1f} → {eo:.1f}</b>; the drop is concentrated in the Intercity reorg team and city-hub "
        f"new joiners. Hiring fills in a median <b>{f['TTF (days)'].median():.0f} days</b>, but <b>{100 - sla:.0f}%</b> of fills "
        "miss SLA, mostly after a failed first slate.")

c1, c2, c3 = st.columns(3)
with c1.container(key="card_enps"):
    st.markdown('<div class="card-title">Employee sentiment <span class="hint">eNPS pulse</span></div>',
                unsafe_allow_html=True)
    st.markdown("Wave comparison, segment drill-down, driver map, comment themes and the link from April sentiment "
                "to later exits.")
    st.page_link("pages/1_Employee_Sentiment.py", label="Open dashboard →")
with c2.container(key="card_rec"):
    st.markdown('<div class="card-title">Recruitment <span class="hint">FY26 requisitions</span></div>',
                unsafe_allow_html=True)
    st.markdown("Monthly hiring trends, time to fill and SLA drill-down, funnel and source yield, "
                "recruiter and interviewer scorecards.")
    st.page_link("pages/2_Recruitment.py", label="Open dashboard →")
with c3.container(key="card_dq"):
    st.markdown('<div class="card-title">Data quality <span class="hint">cleaning register</span></div>',
                unsafe_allow_html=True)
    st.markdown(f"{int((dq['rows_affected'] > 0).sum())} issues found across both exports, each with rows affected "
                "and the treatment applied.")
    st.page_link("pages/3_Data_Quality.py", label="Open register →")

section("At a glance")
k = st.columns(4)
reorg = r[(r["Intercity Jun-26 reorg"] == "Yes") & (r["Survey Wave"] == "Oct-2026")]["Q1"]
stat(k[0], "Intercity reorg team eNPS", f"{enps(reorg):.0f}", f"n = {reorg.notna().sum()}", "red")
city_nj = r[(r["Survey Wave"] == "Oct-2026") & (r["Tenure Band"].isin(["0-3m", "3-6m"])) & (r["Location Type"] == "City")]
stat(k[1], "City joiners (<6m) eNPS", f"{enps(city_nj['Q1']):.0f}", f"onboarding {city_nj['Q5'].mean():.1f}/5", "red")
stat(k[2], "Offer acceptance", f"{(c[c['Reached Offer']]['Offer Status'] == 'Accepted').mean() * 100:.0f}%",
     f"{int(c['Reached Offer'].sum())} offers", "amber")
stat(k[3], "Agency fees FY26", f"₹{q['Agency Fee (INR)'].sum() / 1e5:.1f}L", "8.33% of joiner CTC", "gray")

section("Notes")
with st.container(key="card_howto"):
    st.markdown(
        """
- **Filters** live in the sidebar on each page. Leave a filter empty to include everything. 
- **Drill-down:** pick a *Level 1* dimension, select one segment, then pick a *Level 2* dimension.
- **Small segments:** Groups with fewer than 5 responses are hidden from sentiment charts by default.
- **Definitions:** eNPS = % promoters (9–10) − % detractors (0–6) on Q1. Time to fill = *Req Raised On* → hired
  candidate's *Offer Response On*. SLA = 30 / 45 / 60 days for TBA–G2 / G3–G5 / G6+.
"""
    )
