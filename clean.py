"""
Porter People Analytics case - data cleaning pipeline.

Reads the two raw Excel exports and writes tidy CSVs to ./clean/ plus a
data-quality register (clean/dq_log.csv) recording every issue, the number of
rows affected, and how it was treated.

Run:  python clean.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
RAW_ENPS = ROOT / "data" / "enps.xlsx"
RAW_REC = ROOT / "data" / "recruit.xlsx"
OUT = ROOT / "clean"
OUT.mkdir(exist_ok=True)

AS_OF = pd.Timestamp("2026-10-31")
WAVES = {
    "Apr-2026": (pd.Timestamp("2026-04-06"), pd.Timestamp("2026-04-17 23:59:59")),
    "Oct-2026": (pd.Timestamp("2026-10-05"), pd.Timestamp("2026-10-16 23:59:59")),
}
TECH_FUNCS = {"Engineering", "Product", "Data & Analytics", "Design & Research"}
GRADE_ORDER = ["TBA"] + [f"G{i}" for i in range(1, 11)]

DQ = []


def log(dataset, table, issue, n, treatment):
    DQ.append(dict(dataset=dataset, table=table, issue=issue, rows_affected=int(n), treatment=treatment))
    print(f"[{dataset}/{table}] {issue}: {n} -> {treatment}")


# --------------------------------------------------------------------------- helpers
def clean_id(s):
    return s.astype("string").str.strip().str.upper()


def parse_date(s):
    """Parse a mixed column: real datetimes, ISO, dd/mm/yyyy, dd-Mon-yy, Excel serials."""
    def one(v):
        if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
            return pd.NaT
        if isinstance(v, (pd.Timestamp, np.datetime64)) or hasattr(v, "year"):
            return pd.Timestamp(v)
        t = str(v).strip()
        if not t:
            return pd.NaT
        if re.fullmatch(r"\d{5}(\.0+)?", t):  # Excel serial
            return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(t)))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", t):
            return pd.to_datetime(t[:10], format="%Y-%m-%d")
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", t):
            return pd.to_datetime(t, format="%d/%m/%Y")  # Indian convention dd/mm/yyyy
        if re.fullmatch(r"\d{1,2}-[A-Za-z]{3}-\d{2}", t):
            return pd.to_datetime(t, format="%d-%b-%y")
        return pd.to_datetime(t, errors="coerce", dayfirst=True)
    return s.map(one)


def parse_inr(v):
    """'4,48,000' -> 448000 ; '2.96 LPA' / '8.44 L' / '3.64 Lakhs' -> lakhs*1e5."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    t = str(v).strip().upper().replace(",", "")
    m = re.fullmatch(r"([\d.]+)\s*(LPA|LAKHS?|L)", t)
    if m:
        return float(m.group(1)) * 1e5
    try:
        return float(t)
    except ValueError:
        return np.nan


def is_str_val(s):
    return s.map(lambda x: isinstance(x, str))


THREAD_MAP = {
    "intracity": "Intracity", "intra city": "Intracity",
    "intercity": "Intercity", "inter city": "Intercity",
    "enterprise": "Enterprise",
    "packers & movers": "Packers & Movers", "packers and movers": "Packers & Movers", "p&m": "Packers & Movers",
    "geo expansion": "Geo Expansion", "geo-expansion": "Geo Expansion",
    "central": "Central",
}
LOC_MAP = {
    "bengaluru ho": "Bengaluru HO", "blr - ho": "Bengaluru HO", "bangalore ho": "Bengaluru HO",
    "bengaluru": "Bengaluru", "blr": "Bengaluru",
    "mumbai": "Mumbai", "hyd": "Hyderabad", "hyderabad": "Hyderabad",
    "delhi": "Delhi NCR", "new delhi": "Delhi NCR", "gurugram": "Delhi NCR", "delhi ncr": "Delhi NCR",
    "kolkata": "Kolkata", "calcutta": "Kolkata", "chennai": "Chennai", "pune": "Pune",
    "ahmedabad": "Ahmedabad", "jaipur": "Jaipur", "lucknow": "Lucknow",
}


def norm_map(s, mapping, dataset, table, col):
    raw = s.astype("string").str.strip()
    out = raw.str.lower().map(mapping)
    changed = (out != s.astype("string")) & out.notna()
    unmapped = out.isna() & raw.notna()
    if unmapped.any():
        print("  UNMAPPED", col, raw[unmapped].unique()[:10])
    log(dataset, table, f"{col}: inconsistent spellings / case / whitespace", changed.sum(),
        "Mapped to canonical values")
    return out


def norm_grade(s):
    def one(v):
        if pd.isna(v):
            return np.nan
        t = str(v).strip().upper().replace("GRADE", "").strip()
        if t in ("TBA", "TRAINEE"):
            return "TBA"
        t = t.lstrip("G").strip()
        return f"G{int(t)}" if t.isdigit() else np.nan
    return s.map(one)


# =========================================================================== eNPS FILE
D = "Employee & eNPS"
em = pd.read_excel(RAW_ENPS, "Employee_Master")
raw_em_n = len(em)

em["Employee ID"] = clean_id(em["Employee ID"])
n = (em["Employee ID"] != pd.read_excel(RAW_ENPS, "Employee_Master")["Employee ID"]).sum()
log(D, "Employee_Master", "Employee ID with leading/trailing spaces or lower-case 'emp'", n, "Trimmed and upper-cased")
em["Reporting Manager ID"] = clean_id(em["Reporting Manager ID"])

em["Record Updated On"] = pd.to_datetime(em["Record Updated On"])
exact = em.duplicated().sum()
dups = em["Employee ID"].duplicated(keep=False)
log(D, "Employee_Master", "Duplicate Employee ID rows (exact copies + conflicting versions, e.g. differing Location)",
    em["Employee ID"].duplicated().sum(),
    f"{exact} exact duplicates dropped; for conflicting versions kept the row with the latest 'Record Updated On'")
em = em.sort_values("Record Updated On").drop_duplicates("Employee ID", keep="last").reset_index(drop=True)

em["Thread"] = norm_map(em["Thread"], THREAD_MAP, D, "Employee_Master", "Thread")
em["Location"] = norm_map(em["Location"], LOC_MAP, D, "Employee_Master", "Location")

g = norm_grade(em["Grade"])
log(D, "Employee_Master", "Grade in mixed formats ('g3', 'Grade 3', '3', 'Trainee')", (g != em["Grade"]).sum(),
    "Standardised to TBA, G1..G10")
em["Grade"] = g

lt_derived = np.where(em["Location"] == "Bengaluru HO", "HO", "City")
log(D, "Employee_Master", "Location Type blank", em["Location Type"].isna().sum(),
    "Derived from Location (Bengaluru HO = HO, else City)")
log(D, "Employee_Master", "'Bengaluru' (city hub) vs 'Bengaluru HO'", (em["Location"] == "Bengaluru").sum(),
    "Kept separate: these rows are tagged Location Type = City, so treated as the Bengaluru city hub, not HO")
em["Location Type"] = lt_derived

for col in ["Date of Joining", "Date of Exit"]:
    n = is_str_val(em[col]).sum()
    em[col] = parse_date(em[col])
    log(D, "Employee_Master", f"{col} stored as text in mixed formats (dd/mm/yyyy, yyyy-mm-dd, dd-Mon-yy)", n,
        "Parsed to dates (dd/mm assumed, Indian convention)")
em["Manager Effective From"] = pd.to_datetime(em["Manager Effective From"])

ctc_raw = em["Annual CTC (INR)"]
em["Annual CTC (INR)"] = ctc_raw.map(parse_inr)
log(D, "Employee_Master", "Annual CTC as text ('4,48,000', '2.96 LPA', '8.44 L', '3.64 Lakhs')",
    is_str_val(ctc_raw).sum(), "Converted to numeric INR (lakh notations x 100,000)")

st = em["Employment Status"].str.strip().str.title()
log(D, "Employee_Master", "Employment Status in mixed case / trailing spaces", (st != em["Employment Status"]).sum(),
    "Standardised to Active / Exited")
em["Employment Status"] = st
bad = (em["Employment Status"] == "Active") & em["Date of Exit"].notna() & (em["Date of Exit"] <= AS_OF)
log(D, "Employee_Master", "Status 'Active' but has an exit date, exit type and classification", bad.sum(),
    "Recoded to Exited (exit date is on/before 31-Oct-2026; HRMS status not updated)")
em.loc[bad, "Employment Status"] = "Exited"
bad = (em["Employment Status"] == "Exited") & em["Date of Exit"].isna()
log(D, "Employee_Master", "Status 'Exited' but no Date of Exit", bad.sum(),
    "Kept as Exited; exit month unknown so excluded from exit trends; treated as eligible for both waves")

pr = em["Performance Rating FY25-26"].copy()
newj = em["Date of Joining"] >= "2026-01-01"
fix = pr.isna() | (pr == "New Joiner")
log(D, "Employee_Master", "Rating blank or 'New Joiner' (vs 'Not Rated - New Joiner')", fix.sum(),
    "Recoded to 'Not Rated - New Joiner' (all are joiners on/after 01-Jan-2026, per dictionary)")
pr[fix] = "Not Rated - New Joiner"
odd = newj & (pr != "Not Rated - New Joiner")
log(D, "Employee_Master", "Joiner after 01-Jan-2026 carrying a performance rating", odd.sum(),
    "Flagged, left as is (could be a DOJ error)")
em["Performance Rating FY25-26"] = pr

bad = em["Manager Effective From"] < em["Date of Joining"]
log(D, "Employee_Master", "Manager Effective From earlier than Date of Joining", bad.sum(),
    "Set to Date of Joining")
em.loc[bad, "Manager Effective From"] = em.loc[bad, "Date of Joining"]
log(D, "Employee_Master", "Reporting Manager ID not found in Employee_Master",
    (~em["Reporting Manager ID"].isin(em["Employee ID"])).sum(),
    "Kept (manager may sit outside this export, e.g. left before Apr-2026)")

# Derived HR fields
em["Job Family"] = np.where(em["Function"].isin(TECH_FUNCS), "Tech", "Non-Tech")
pb = pd.read_excel(RAW_ENPS, "Pay_Bands")
pb26 = pb[pb["Effective From"] == pb["Effective From"].max()]
em = em.merge(pb26[["Job Family", "Grade", "Band Min (INR)", "Band Mid (INR)", "Band Max (INR)"]],
              on=["Job Family", "Grade"], how="left")
em["Compa Ratio"] = em["Annual CTC (INR)"] / em["Band Mid (INR)"]
em["Below Band Min"] = em["Annual CTC (INR)"] < em["Band Min (INR)"]
log(D, "Pay_Bands", "Two band sets (FY25 eff. 01-Apr-2025, FY26 eff. 01-Apr-2026, mids ~+6%)", len(pb),
    "Compa-ratio uses the band in force on the data date (01-Apr-2026 set) for all employees")
log(D, "Employee_Master", "Annual CTC blank", em["Annual CTC (INR)"].isna().sum(),
    "Left blank; excluded from pay metrics only")
monthly = em["Annual CTC (INR)"] < 150000
log(D, "Employee_Master", "CTC below INR 1.5L (e.g. 38,700 for a G2) - monthly figure keyed in annual field",
    monthly.sum(), "Multiplied by 12 (result lands inside the grade band in every case)")
em.loc[monthly, "Annual CTC (INR)"] *= 12
em["Compa Ratio"] = em["Annual CTC (INR)"] / em["Band Mid (INR)"]
cr = em["Compa Ratio"]
bad = (cr < .4) | (cr > 2.5)
log(D, "Employee_Master", "CTC still implausible for grade (compa-ratio <0.4 or >2.5; e.g. G7 at INR 2.95L)",
    bad.sum(), "Set to blank (unit unclear)")
em.loc[bad, ["Annual CTC (INR)", "Compa Ratio"]] = np.nan
em["Below Band Min"] = em["Annual CTC (INR)"] < em["Band Min (INR)"]

em["Tenure (months) @Oct"] = ((AS_OF - em["Date of Joining"]).dt.days / 30.44).round(1)
em["Mgr Tenure (months) @Oct"] = ((pd.Timestamp("2026-10-05") - em["Manager Effective From"]).dt.days / 30.44).round(1)
em["Manager changed since Apr-26"] = (em["Manager Effective From"] > pd.Timestamp("2026-04-17")) & \
                                     (em["Manager Effective From"] > em["Date of Joining"])
em["Grade Rank"] = em["Grade"].map({g: i for i, g in enumerate(GRADE_ORDER)})
for w, (start, _) in WAVES.items():
    em[f"Eligible {w}"] = (em["Date of Joining"] <= start) & (em["Date of Exit"].isna() | (em["Date of Exit"] >= start))
em["Exit Month"] = em["Date of Exit"].dt.to_period("M").astype("string")

# ------------------------------------------------------------------ eNPS responses
r = pd.read_excel(RAW_ENPS, "eNPS_Responses")
r.columns = ["Response ID", "Employee ID", "Survey Wave", "Submitted On", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Comment"]
raw_r_n = len(r)
r_eid_raw = r["Employee ID"].copy()
r["Employee ID"] = clean_id(r["Employee ID"])
log(D, "eNPS_Responses", "Employee ID with spaces / lower case", (r["Employee ID"] != r_eid_raw).sum(), "Trimmed, upper-cased")

wv = r["Survey Wave"].str.strip().str.lower().str[:3].map({"apr": "Apr-2026", "oct": "Oct-2026"})
log(D, "eNPS_Responses", "Survey Wave in 8 spellings (Apr-2026, April'26, apr 2026, Apr, Oct 2026, ...)",
    (wv != r["Survey Wave"]).sum(), "Mapped to Apr-2026 / Oct-2026")
r["Survey Wave"] = wv

test = ~r["Employee ID"].str.match(r"^EMP\d{5}$")
log(D, "eNPS_Responses", "Test submissions (TEST001, TEST002, HRTEST)", test.sum(), "Removed")
r = r[~test]
unk = ~r["Employee ID"].isin(em["Employee ID"])
log(D, "eNPS_Responses", "Employee ID not in Employee_Master (EMP99xxx series)", unk.sum(),
    "Removed - cannot be attributed to an invited employee")
r = r[~unk]

win_bad = r.apply(lambda x: not (WAVES[x["Survey Wave"]][0] <= x["Submitted On"] <= WAVES[x["Survey Wave"]][1]), axis=1)
log(D, "eNPS_Responses", "Submitted outside the wave window", win_bad.sum(), "Removed" if win_bad.sum() else "None found")
r = r[~win_bad]

q1raw = r["Q1"].astype("string").str.strip()
q1 = pd.to_numeric(q1raw.str.replace(r"/10$", "", regex=True), errors="coerce")
log(D, "eNPS_Responses", "Q1 entered as 'x/10' text", q1raw.str.contains("/10", na=False).sum(), "Converted to number")
oor = (q1 < 0) | (q1 > 10)
log(D, "eNPS_Responses", "Q1 out of 0-10 range (-1, 11, 12)", oor.sum(), "Set to blank (not capped - intent unknown)")
q1[oor] = np.nan
log(D, "eNPS_Responses", "Q1 blank", q1raw.isna().sum(), "Excluded from eNPS denominator only; Q2-Q6 retained")
r["Q1"] = q1
for c in ["Q2", "Q3", "Q4", "Q5", "Q6"]:
    bad = ~r[c].isin([1, 2, 3, 4, 5]) & r[c].notna()
    if bad.any():
        r.loc[bad, c] = np.nan
log(D, "eNPS_Responses", "Blank Q2-Q6 items", r[["Q2", "Q3", "Q4", "Q5", "Q6"]].isna().any(axis=1).sum(),
    "Left blank; item averages use available answers")

r = r.sort_values("Submitted On")
d = r.duplicated(["Employee ID", "Survey Wave"], keep="last")
log(D, "eNPS_Responses", "Same employee submitted twice in a wave (re-submission, IDs like R501938 / R5019387)",
    d.sum(), "Kept the latest submission per employee per wave")
r = r[~d]

r = r.merge(em[["Employee ID", "Date of Joining", "Date of Exit", "Eligible Apr-2026", "Eligible Oct-2026"]],
            on="Employee ID", how="left")
inel = ((r["Survey Wave"] == "Apr-2026") & ~r["Eligible Apr-2026"]) | ((r["Survey Wave"] == "Oct-2026") & ~r["Eligible Oct-2026"])
log(D, "eNPS_Responses", "Response from employee not active on the wave open date (joined after / exited before)",
    inel.sum(), "Removed (not invited per README)")
r = r[~inel].drop(columns=["Date of Joining", "Date of Exit", "Eligible Apr-2026", "Eligible Oct-2026"])

cm = r["Comment"].astype("string").str.strip()
r["Comment"] = cm.where(cm != "", pd.NA)
THEMES = {
    "Manager": ["manager", "micromanagement", "1:1", "feedback", "unheard", "clarity"],
    "Pay": ["salary", "pay", "earn", "increment"],
    "Workload": ["workload", "weekend", "late-night", "escalation"],
    "Onboarding": ["onboarding", "induction", "training", "laptop", "buddy", "first month"],
    "Growth": ["career", "next role", "growth"],
    "Positive": ["love", "proud", "great team", "supportive"],
}


def theme(t):
    if pd.isna(t):
        return pd.NA
    tl = t.lower()
    if any(k in tl for k in THEMES["Positive"]):
        return "Positive"
    for k, kws in THEMES.items():
        if any(w in tl for w in kws):
            return k
    return "Other"


r["Comment Theme"] = r["Comment"].map(theme)
r["eNPS Group"] = pd.cut(r["Q1"], [-1, 6, 8, 10], labels=["Detractor", "Passive", "Promoter"]).astype("string")

# attach HR attributes to responses (as of data date)
keep = ["Employee ID", "Company", "Thread", "Function", "Job Family", "Grade", "Grade Rank", "Location", "Location Type",
        "Date of Joining", "Manager Effective From", "Reporting Manager ID", "Performance Rating FY25-26",
        "Compa Ratio", "Employment Status", "Date of Exit", "Exit Type", "Exit Classification"]
r = r.merge(em[keep], on="Employee ID", how="left")
wave_start = r["Survey Wave"].map({k: v[0] for k, v in WAVES.items()})
r["Tenure Band"] = pd.cut((wave_start - r["Date of Joining"]).dt.days / 30.44, [-1, 3, 6, 12, 24, 1e4],
                          labels=["0-3m", "3-6m", "6-12m", "1-2y", "2y+"]).astype("string")
r["Mgr Changed <6m"] = ((wave_start - r["Manager Effective From"]).dt.days < 183) & \
                       (r["Manager Effective From"] > r["Date of Joining"])
r["Compa Band"] = pd.cut(r["Compa Ratio"], [0, .85, .95, 1.05, 10],
                         labels=["<0.85", "0.85-0.95", "0.95-1.05", ">1.05"]).astype("string")

em.to_csv(OUT / "employees.csv", index=False)
r.to_csv(OUT / "enps_responses.csv", index=False)
print(f"Employees {raw_em_n} -> {len(em)} ; responses {raw_r_n} -> {len(r)}")

# =========================================================================== RECRUITMENT FILE
D = "Recruitment"
q = pd.read_excel(RAW_REC, "Requisitions")
q["Req ID"] = q["Req ID"].str.strip().str.upper()
q["Thread"] = norm_map(q["Thread"], THREAD_MAP, D, "Requisitions", "Thread")
q["Location"] = norm_map(q["Location"], LOC_MAP, D, "Requisitions", "Location")
n = is_str_val(q["Req Raised On"]).sum()
q["Req Raised On"] = parse_date(q["Req Raised On"])
log(D, "Requisitions", "Req Raised On as dd/mm/yyyy text", n, "Parsed to dates")

rec = pd.read_excel(RAW_REC, "Recruiters")


def map_rec(v):
    t = str(v).strip().lower()
    for name in rec["Recruiter Name"]:
        first, last = name.lower().split()
        if t == name.lower() or t == first or t == f"{first} {last[0]}" or t == f"{first} {last[0]}.":
            return name
    return np.nan


rr = q["Recruiter"].map(map_rec)
log(D, "Requisitions", "Recruiter names abbreviated / case variants ('Rhea', 'Divya M', 'rhea kapoor')",
    (rr != q["Recruiter"]).sum(), "Mapped to Recruiters master (first name / first + initial match is unique)")
q["Recruiter"] = rr

STATUS_MAP = {"closed - joined": "Closed - Joined", "closed-joined": "Closed - Joined", "joined": "Closed - Joined",
              "offer accepted": "Offer Accepted", "open": "Open", "on hold": "On Hold", "hold": "On Hold",
              "archived": "Archived"}
s = q["Req Status"].str.strip().str.lower().map(STATUS_MAP)
log(D, "Requisitions", "Req Status variants ('Closed-Joined', 'Joined', 'OPEN', 'Hold')", (s != q["Req Status"]).sum(),
    "Mapped to Open / Offer Accepted / Closed - Joined / On Hold / Archived")
q["Req Status"] = s

q["Job Family"] = np.where(q["Function"].isin(TECH_FUNCS), "Tech", "Non-Tech")
q["Grade Rank"] = q["Grade"].map({g: i for i, g in enumerate(GRADE_ORDER)})
crit = np.where(((q["Job Family"] == "Tech") & (q["Grade Rank"] >= 6)) | (q["Grade Rank"] >= 8), "Critical", "Non-Critical")
log(D, "Requisitions", "Criticality blank", q["Criticality"].isna().sum(), "Derived from README rule")
log(D, "Requisitions", "Criticality conflicts with README rule", (q["Criticality"].notna() & (q["Criticality"] != crit)).sum(),
    "Overwritten with rule-based value")
q["Criticality"] = crit
sla = np.select([q["Grade Rank"] <= 2, q["Grade Rank"] <= 5], [30, 45], 60)
log(D, "Requisitions", "SLA (Days) conflicts with grade rule", (q["SLA (Days)"] != sla).sum(), "Overwritten with rule-based SLA")
q["SLA (Days)"] = sla
log(D, "Requisitions", "Replacement reqs whose replaced employee is not in Employee_Master",
    ((q["Position Type"] == "Replacement") & ~clean_id(q["Replaced Employee ID"]).isin(em["Employee ID"])).sum(),
    "Kept; per dictionary these employees exited before 01-Apr-2026")
q["Replaced Employee ID"] = clean_id(q["Replaced Employee ID"])

# ------------------------------------------------------------------ candidates
c = pd.read_excel(RAW_REC, "Candidates")
raw_c_n = len(c)
n = c.duplicated().sum()
c = c.drop_duplicates()
log(D, "Candidates", "Exact duplicate candidate rows", n, "Dropped")
d = c["Candidate ID"].duplicated().sum()
if d:
    log(D, "Candidates", "Candidate ID reused with different data", d, "Kept latest stage")
    c = c.drop_duplicates("Candidate ID", keep="last")

rid = c["Req ID"].astype("string").str.strip().str.upper()
fixed = ~rid.str.startswith("REQ_")
c["Req ID"] = np.where(fixed, "REQ_" + rid, rid)
log(D, "Candidates", "Req ID missing 'REQ_' prefix (numeric only)", fixed.sum(), "Prefix added")
orphan = ~c["Req ID"].isin(q["Req ID"])
log(D, "Candidates", "Candidates on REQ_4xxx requisitions not in Requisitions (raised before FY26 scope)", orphan.sum(),
    "Removed - out of scope (no req attributes to analyse)")
c = c[~orphan]

SRC_MAP = {"agency": "Agency", "vendor": "Agency", "consultant": "Agency",
           "naukri": "Naukri", "naukri.com": "Naukri",
           "employee referral": "Employee Referral", "referral": "Employee Referral", "emp referral": "Employee Referral",
           "careers page": "Careers Page", "career page": "Careers Page", "website": "Careers Page",
           "linkedin": "LinkedIn", "li": "LinkedIn",
           "internal (ijp)": "Internal (IJP)", "ijp": "Internal (IJP)", "internal": "Internal (IJP)"}
s = c["Source"].str.strip().str.lower().map(SRC_MAP)
log(D, "Candidates", "Source in 21 spellings (Vendor/Consultant = Agency, Website = Careers Page, LI = LinkedIn)",
    (s != c["Source"]).sum(), "Mapped to 6 channels")
c["Source"] = s
noag = (c["Source"] == "Agency") & c["Agency Name"].isna()
log(D, "Candidates", "Agency-sourced candidate without Agency Name", noag.sum(), "Agency Name = 'Unknown agency'")
c.loc[noag, "Agency Name"] = "Unknown agency"

date_cols = ["Applied On", "Shortlisted On", "Screening Done On", "R1 Interview Date", "R1 Feedback Submitted On",
             "R2 Interview Date", "Offer Released On", "Offer Response On", "Expected DOJ", "Actual DOJ"]
for col in date_cols:
    n = is_str_val(c[col]).sum()
    c[col] = parse_date(c[col])
    if n:
        log(D, "Candidates", f"{col} as text (mixed formats; Offer Released On includes Excel serials like '46209')", n,
            "Parsed to dates")

for col in ["Expected CTC (INR)", "Current CTC (INR)", "Offered CTC (INR)"]:
    n = is_str_val(c[col]).sum()
    c[col] = c[col].map(parse_inr)
    if n:
        log(D, "Candidates", f"{col} in LPA text ('5.9 LPA')", n, "Converted to INR")


def notice(v):
    if pd.isna(v):
        return np.nan
    t = str(v).strip().lower()
    if t == "immediate":
        return 0
    m = re.match(r"(\d+)\s*(month|months)", t)
    if m:
        return int(m.group(1)) * 30
    m = re.match(r"(\d+)", t)
    return int(m.group(1)) if m else np.nan


n = is_str_val(c["Notice Period (Days)"]).sum()
c["Notice Period (Days)"] = c["Notice Period (Days)"].map(notice)
log(D, "Candidates", "Notice Period as text ('2 months', 'Immediate', '30 days')", n, "Converted to days (1 month = 30)")

CS = {"rejected-profile": "Rejected - Profile", "profile reject": "Rejected - Profile", "r1 reject": "Rejected - R1",
      "joined": "Joined", "declined": "Offer Declined", "r1 feedback pending": "R1 Feedback Pending"}
s = c["Candidate Status"].str.strip()
s2 = s.str.lower().map(CS).fillna(s)
log(D, "Candidates", "Candidate Status variants ('Rejected-Profile', 'Profile Reject', 'R1 Reject', 'joined')",
    (s2 != c["Candidate Status"]).sum(), "Mapped to canonical statuses")
c["Candidate Status"] = s2

j_nodoj = (c["Candidate Status"] == "Joined") & c["Actual DOJ"].isna()
log(D, "Candidates", "Status 'Joined' with no Actual DOJ (after removing out-of-scope reqs)", j_nodoj.sum(),
    "Kept as joined; DOJ unknown")

# stage-order checks
seq = ["Applied On", "Shortlisted On", "Screening Done On", "R1 Interview Date", "R2 Interview Date",
       "Offer Released On", "Offer Response On", "Actual DOJ"]
viol = pd.Series(False, index=c.index)
for a, b in zip(seq, seq[1:]):
    viol |= c[b].notna() & c[a].notna() & (c[b] < c[a])
log(D, "Candidates", "Stage dates out of order (later stage dated before earlier stage)", viol.sum(),
    "Flagged (column 'Date Order Issue'); excluded from stage-duration metrics where negative")
c["Date Order Issue"] = viol
c = c.merge(q[["Req ID", "Req Raised On"]], on="Req ID", how="left")
pre = c["Applied On"] < c["Req Raised On"]
log(D, "Candidates", "Applied before the requisition was raised", pre.sum(),
    "Kept (possible talent-pool tagging); applied->stage timings use Applied On as is")
fb_bad = c["R1 Feedback Submitted On"] < c["R1 Interview Date"]
log(D, "Candidates", "R1 feedback dated before the interview", fb_bad.sum(), "Feedback lag set to blank for these")
c["R1 Feedback Lag (days)"] = (c["R1 Feedback Submitted On"] - c["R1 Interview Date"]).dt.days
c.loc[fb_bad, "R1 Feedback Lag (days)"] = np.nan
c["R1 Interviewer ID"] = clean_id(c["R1 Interviewer ID"])
c = c.drop(columns=["Req Raised On"])

# Stage reached flags (funnel) - derived from dates/results, not the status label
c["Reached Shortlist"] = c["Shortlisted On"].notna()
c["Reached Screening"] = c["Screening Done On"].notna()
c["Reached R1"] = c["R1 Interview Date"].notna()
c["Reached R2"] = c["R2 Interview Date"].notna()
c["Reached Offer"] = c["Offer Released On"].notna()
c["Offer Accepted"] = c["Offer Status"] == "Accepted"
c["Joined"] = (c["Candidate Status"] == "Joined") | c["Actual DOJ"].notna()

# ------------------------------------------------------------------ req-level metrics
acc = c[c["Offer Accepted"] & ~c["Candidate Status"].isin(["Not Joined - Backed Out"])]
# hired candidate = joined, else accepted & yet to join; take the earliest acceptance among them
acc = acc.assign(pri=np.where(acc["Joined"], 0, 1)).sort_values(["Req ID", "pri", "Offer Response On"])
hire = acc.drop_duplicates("Req ID")[["Req ID", "Candidate ID", "Source", "Agency Name", "Offer Response On",
                                     "Offered CTC (INR)", "Joined", "Actual DOJ", "Notice Period (Days)",
                                     "Offer Released On"]]
hire.columns = ["Req ID", "Hired Candidate", "Hire Source", "Hire Agency", "Hire Accept Date", "Hire Offered CTC",
                "Hire Joined", "Hire DOJ", "Hire Notice Days", "Hire Offer Date"]
multi = c[c["Joined"]].groupby("Req ID").size()
log(D, "Candidates", "Requisitions with more than one joiner", (multi > 1).sum(),
    "TTF uses the first joiner; extra joiners kept in candidate counts")
q = q.merge(hire, on="Req ID", how="left")

stat_vs = (q["Req Status"].isin(["Closed - Joined", "Offer Accepted"]) & q["Hired Candidate"].isna())
log(D, "Requisitions", "Status Closed/Offer Accepted but no accepted candidate in Candidates", stat_vs.sum(),
    "Kept status; TTF blank")
q["Filled"] = q["Hire Accept Date"].notna()
q["TTF (days)"] = (q["Hire Accept Date"] - q["Req Raised On"]).dt.days
q["Age (days)"] = np.where(q["Filled"], q["TTF (days)"], (AS_OF - q["Req Raised On"]).dt.days)
q["Within SLA (recalc)"] = np.where(q["Filled"], q["TTF (days)"] <= q["SLA (Days)"], np.nan)
q["SLA Status (recalc)"] = np.select(
    [q["Filled"] & (q["TTF (days)"] <= q["SLA (Days)"]), q["Filled"],
     q["Req Status"].isin(["On Hold", "Archived"]),
     ~q["Filled"] & (q["Age (days)"] > q["SLA (Days)"])],
    ["Within SLA", "Breached", "On Hold / Archived", "Open - Breached"], "Open - Within SLA")
mism = q["SLA Status (System)"].notna() & (q["SLA Status (System)"] != q["SLA Status (recalc)"]) & \
       ~q["Req Status"].isin(["On Hold", "Archived"])
log(D, "Requisitions", "ATS 'SLA Status (System)' disagrees with SLA recomputed from README TTF definition",
    mism.sum(), "Used recomputed status throughout; system field kept for reference")
log(D, "Requisitions", "SLA Status (System) blank", q["SLA Status (System)"].isna().sum(), "Recomputed")
q["Over Budget Offer"] = q["Hire Offered CTC"] > q["Budgeted Max CTC (INR)"]
q["Req Month"] = q["Req Raised On"].dt.to_period("M").astype("string")
q["Agency Fee (INR)"] = np.where((q["Hire Source"] == "Agency") & (q["Hire Joined"] == True),
                                 q["Hire Offered CTC"] * 0.0833, 0)

# per-req funnel counts and interview lag
agg = c.groupby("Req ID").agg(Applicants=("Candidate ID", "count"), Offers=("Reached Offer", "sum"),
                              Declines=("Offer Status", lambda s: (s == "Declined").sum()),
                              Backouts=("Candidate Status", lambda s: (s == "Not Joined - Backed Out").sum()),
                              Median_R1_Lag=("R1 Feedback Lag (days)", "median"))
q = q.merge(agg, left_on="Req ID", right_index=True, how="left")

# directory lookups
pdir = pd.read_excel(RAW_REC, "People_Directory")
q = q.merge(pdir[["Employee ID", "Employee Name"]].rename(columns={"Employee ID": "Hiring Manager ID",
                                                                     "Employee Name": "Hiring Manager"}),
            on="Hiring Manager ID", how="left")
c = c.merge(q[["Req ID", "Thread", "Function", "Grade", "Grade Rank", "Location", "Recruiter", "Criticality",
               "Position Type", "Job Family", "Budgeted Max CTC (INR)", "Req Raised On", "Req Month"]],
            on="Req ID", how="left")
c = c.merge(pdir[["Employee ID", "Employee Name"]].rename(columns={"Employee ID": "R1 Interviewer ID",
                                                                     "Employee Name": "R1 Interviewer"}),
            on="R1 Interviewer ID", how="left")
c["Applied Month"] = c["Applied On"].dt.to_period("M").astype("string")
c["Offer Month"] = c["Offer Released On"].dt.to_period("M").astype("string")
c["Expected Hike %"] = (c["Expected CTC (INR)"] / c["Current CTC (INR)"] - 1) * 100
c["Offer vs Expected %"] = (c["Offered CTC (INR)"] / c["Expected CTC (INR)"] - 1) * 100

q.to_csv(OUT / "requisitions.csv", index=False)
c.to_csv(OUT / "candidates.csv", index=False)
rec.to_csv(OUT / "recruiters.csv", index=False)
pdir.to_csv(OUT / "people_directory.csv", index=False)
pb.to_csv(OUT / "pay_bands.csv", index=False)
print(f"Requisitions {len(q)} ; candidates {raw_c_n} -> {len(c)}")

pd.DataFrame(DQ).to_csv(OUT / "dq_log.csv", index=False)
print(f"DQ log: {len(DQ)} entries")
