## Cleaning and Running

```bash
pip install -r requirements.txt
python clean.py
streamlit run Home.py
```
## What the dashboards do

| | Employee sentiment | Recruitment |
|---|---|---|
| **Slicers** | Company, Thread, Function, Job Family, Grade, Location, Location Type, Performance rating, Compa-ratio band, Intercity Jun-26 reorg flag, tenure at survey, manager change | Req-raised month range, Thread, Function, Grade, Location, Recruiter, Criticality, Position type, Job family, Req status, Source |
| **Trends** | Apr vs Oct: eNPS, promoter/detractor mix, five driver items, change by any segment | Monthly reqs raised / offers accepted / joiners; TTF and SLA by month raised |
| **Drill-down** | Overall → Level 1 dimension → pick a segment → Level 2 dimension (+ item heatmap) | Overall → Level 1 → segment → Level 2 (+ requisition list, CSV download) |
| **Extra** | Key-driver map, comment themes and browser, compa-ratio and tenure cuts, Apr sentiment → later exits | Funnel, source yield, agency table, offer-gap vs outcome, stage-by-stage time, recruiter scorecard vs target, interviewer feedback lag |

All metrics are computed from row-level data after filters are applied (nothing is pre-aggregated), so they
recalculate correctly under any combination. Sentiment segments with n < 5 are hidden by default.

## Metric definitions

* **eNPS** = % scoring 9–10 minus % scoring 0–6 on Q1 (blank / invalid Q1 excluded from the denominator).
* **Response rate** = respondents ÷ employees active on the wave open date (06-Apr / 05-Oct-2026).
* **Compa-ratio** = Annual CTC ÷ band mid of the FY26 band set (effective 01-Apr-2026) for the employee's job family and grade.
* **Time to fill (TTF)** = Offer Response On of the hired candidate (joined, else accepted-yet-to-join) − Req Raised On.
* **SLA** = 30 d (TBA–G2), 45 d (G3–G5), 60 d (G6+). SLA status is recomputed; the ATS field is kept for comparison only.
* **Agency fee** = 8.33% of offered CTC, only for agency-sourced hires who joined.
