import streamlit as st

from lib import load_dq, page_style

st.set_page_config(page_title="Data Quality · Porter", page_icon="🧹", layout="wide")
page_style()
st.title("Data-quality register")
st.caption("Every check run by clean.py on the raw exports: what was found, how many rows, and how it was treated.")

dq = load_dq()
ds = st.multiselect("Dataset", dq["dataset"].unique().tolist(), placeholder="All")
v = dq[dq["dataset"].isin(ds)] if ds else dq
show_zero = st.toggle("Show checks that found nothing", value=False)
if not show_zero:
    v = v[v["rows_affected"] > 0]
st.dataframe(v.rename(columns=str.title), width="stretch", hide_index=True, height=700)
st.download_button("Download register (CSV)", dq.to_csv(index=False), "dq_log.csv")
