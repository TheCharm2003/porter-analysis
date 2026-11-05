import streamlit as st

from lib import hero, load_dq, page_style, topbar

st.set_page_config(page_title="Data Quality",layout="wide")
page_style()
dq = load_dq()

topbar("Data-quality register", "Every check run by clean.py on the raw exports",
       [])
found = dq[dq["rows_affected"] > 0]
hero("Porter · Data preparation", "Cleaning & validation log",
     "What was found in each raw export, how many rows it touched, and how it was treated. Full assumptions are in "
     "DATA_QUALITY.md.",
     [(f"{len(dq)}", "Checks run"), (f"{len(found)}", "Issues found"),
      (f"{int(found['rows_affected'].sum()):,}", "Row-level fixes"),
      ("1,322 → 1,310", "Employees"), ("1,726 → 1,683", "Survey responses"), ("5,815 → 5,757", "Candidates")])

st.sidebar.markdown('<div class="sb-label">Filters</div>', unsafe_allow_html=True)
ds = st.sidebar.multiselect("Dataset", dq["dataset"].unique().tolist(), placeholder="All")
show_zero = st.sidebar.toggle("Show checks that found nothing", value=False)
v = dq[dq["dataset"].isin(ds)] if ds else dq
if not show_zero:
    v = v[v["rows_affected"] > 0]
st.dataframe(v.rename(columns=lambda x: x.replace("_", " ").title()), width="stretch", hide_index=True, height=680,
             column_config={"Rows Affected": st.column_config.ProgressColumn(
                 "Rows affected", format="%d", min_value=0, max_value=int(dq["rows_affected"].max()))})
st.download_button("Download register (CSV)", dq.to_csv(index=False), "dq_log.csv")
