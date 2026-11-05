import streamlit as st

from lib import load_dq, load_enps, load_recruitment, page_style, enps

st.set_page_config(page_title="Porter People Analytics", page_icon="📊", layout="wide")
page_style()

st.title("Porter People Analytics")
st.caption("Employee sentiment (eNPS pulse, Apr vs Oct 2026) and Talent Acquisition performance (FY26 requisitions). "
           "Synthetic data, as of 31-Oct-2026.")

r, e = load_enps()
q, c, rec = load_recruitment()

a, o = r[r["Survey Wave"] == "Apr-2026"]["Q1"], r[r["Survey Wave"] == "Oct-2026"]["Q1"]
f = q[q["Filled"]]
c1, c2, c3, c4 = st.columns(4)
c1.metric("eNPS Oct-2026", f"{enps(o):.1f}", f"{enps(o) - enps(a):+.1f} vs Apr", delta_color="normal")
c2.metric("Survey responses (Apr / Oct)", f"{a.notna().sum()} / {o.notna().sum()}")
c3.metric("Median time to fill", f"{f['TTF (days)'].median():.0f} days", help="Req raised → hired candidate accepts offer")
c4.metric("Filled within SLA", f"{f['Within SLA (recalc)'].mean() * 100:.0f}%", help=f"{len(f)} filled requisitions")

st.markdown("### Pages")
st.page_link("pages/1_Employee_Sentiment.py", label="Employee sentiment (eNPS) dashboard", icon="💬")
st.page_link("pages/2_Recruitment.py", label="Recruitment dashboard", icon="🧲")
st.page_link("pages/3_Data_Quality.py", label="Data-quality register", icon="🧹")

st.markdown("### How to use")
st.markdown(
    """
- **Filters live in the sidebar** of each page. Leave a filter empty to include everything. Every number on the page
  (KPIs, trends, drill-downs) is recalculated from the filtered rows, never pre-aggregated.
- **Drill-down:** pick a dimension in *Level 1*, then click into one segment and pick a *Level 2* dimension to break it down further.
- **Small segments:** groups with fewer than 5 responses are hidden from sentiment charts (noise and confidentiality).
- **Definitions:** eNPS = % promoters (9–10) − % detractors (0–6) on Q1. Time to fill = days from *Req Raised On* to the
  hired candidate's *Offer Response On*. SLA = 30 / 45 / 60 days for TBA–G2 / G3–G5 / G6+.
"""
)
with st.expander("Data cleaning summary"):
    dq = load_dq()
    st.write(f"{len(dq)} data-quality checks logged. See the *Data-quality register* page for the full list.")
