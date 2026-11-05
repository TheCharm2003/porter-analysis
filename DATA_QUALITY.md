# Data-quality note

Both exports were cleaned by `clean.py`; every check, row count and treatment is logged to `clean/dq_log.csv`
(also browsable on the dashboard's *Data-quality register* page). Row counts after cleaning:
Employee_Master 1,322 → **1,310**; eNPS responses 1,726 → **1,683**; Requisitions **300**; Candidates 5,815 → **5,757**.

## Issues that change the numbers

| # | Issue | Rows | Treatment | Why it matters |
|---|---|---|---|---|
| 1 | Duplicate employees (8 exact copies, 4 conflicting versions, e.g. different Location) | 12 | Dropped exact copies; kept the version with the latest *Record Updated On* | Headcount and eligibility would be overstated |
| 2 | Survey re-submissions (same employee twice in a wave; IDs like R501938 / R5019387) | 28 | Kept the latest submission | Double-counting one person's vote |
| 3 | Test and unknown respondents (TEST001, TEST002, HRTEST, EMP99xxx) | 9 | Removed | Not employees, not invited |
| 4 | Responses from people not active on the wave open date | 6 | Removed | README: only active employees were invited |
| 5 | Q1 outside 0–10 (−1, 11, 12) | 9 | Set to blank, not capped | Intent unknown; capping 12 → 10 would inflate promoters |
| 6 | Q1 typed as "8/10" | 14 | Converted to number | Would otherwise be dropped |
| 7 | Survey Wave in 8 spellings (April'26, apr 2026, Oct …) | 716 | Mapped to Apr-2026 / Oct-2026 | 42% of rows would fall out of a wave filter |
| 8 | CTC as text ("4,48,000", "2.96 LPA", "8.44 L", "3.64 Lakhs") | 102 | Parsed to INR | Pay analysis |
| 9 | CTC keyed as a monthly figure (e.g. 38,700 for a G2) | 6 | ×12 (lands inside the grade band every time) | Would show as extreme under-payment |
| 10 | CTC implausible after parsing (G7 at ₹2.95 L) / blank | 1 / 11 | Set blank; excluded from pay metrics only | |
| 11 | Status "Active" with an exit date, type and classification | 4 | Recoded to Exited | Exit counts |
| 12 | Candidates on REQ_4xxx reqs that are not in Requisitions | 36 | Removed (pre-FY26 reqs, out of scope) | Includes 13 "Joined" rows that would inflate joins |
| 13 | Candidate Req ID without "REQ_" prefix | 805 | Prefix added | 14% of candidates would not join to their req |
| 14 | Exact duplicate candidate rows | 22 | Dropped | Funnel counts |
| 15 | ATS "SLA Status (System)" contradicts the README TTF rule | 14 (+8 blank) | Recomputed SLA from Req Raised On → hire's Offer Response On | The ATS marks 14 breached reqs as within SLA |
| 16 | Source in 21 spellings (Vendor / Consultant = Agency, Website = Careers Page, LI = LinkedIn, IJP = Internal) | 690 | Mapped to 6 channels | Source yield and agency cost |

## Formatting fixes (no judgement involved)

Employee IDs with spaces or lower case (26 HRMS, 25 survey); Thread (91 + 15 reqs) and Location (82) spellings such
as "Intra City", "P&M", "BLR - HO", "Calcutta", "Gurugram"; Grade as "g3", "Grade 3", "3", "Trainee" (131); blank
Location Type derived from Location (26); dates stored as text in dd/mm/yyyy, yyyy-mm-dd, dd-Mon-yy or Excel serial
form (117 DOJ, 19 exit, 12 req, 291 candidate fields); recruiter names abbreviated ("Rhea", "Divya M") mapped to the
Recruiters sheet (24); Req Status variants (20); Candidate Status variants (94); notice period text ("2 months",
"Immediate") to days (345); Expected CTC in LPA (90); blank Criticality derived from the README rule (9).

## Assumptions

* **Dates:** ambiguous slash dates are read as dd/mm/yyyy (Indian convention). Every parsed date fell inside a plausible range.
* **"Bengaluru" vs "Bengaluru HO":** the 76 "Bengaluru"/"BLR" rows are tagged Location Type = City, so they are treated as the Bengaluru city hub, not head office.
* **Performance rating:** blanks and "New Joiner" (232) are all joiners on/after 01-Jan-2026, so recoded to "Not Rated - New Joiner". One post-January joiner carries a rating; flagged, left as is.
* **Compa-ratio:** uses the FY26 band set (effective 01-Apr-2026) for everyone, since CTC is the current value.
* **Attributes are current, not historical:** Thread, manager and CTC are as of 31-Oct. A person who moved thread between waves is counted in their current thread in both waves.
* **Hired candidate per req:** the joiner if there is one, otherwise the accepted-yet-to-join candidate; backed-out candidates are not hires. No req has two joiners.
* **Exited with no exit date (3):** treated as eligible for both waves; excluded from monthly exit trends.
* **Reorg cohort:** employees whose Manager Effective From falls in June 2026 and is after their joining date (63; 61 report to EMP38671 or EMP32993).
* **Comment themes:** keyword-coded (manager, pay, workload, onboarding, growth, positive); the comment set is small and templated, so this is indicative.

## Known limitations

* No historical HRMS snapshot, so changes in thread, grade or pay between waves cannot be separated from sentiment change.
* October response rate fell to 71% (from 81%); Enterprise (24%) and Packers & Movers (46%) are too low to trust their October scores.
* Candidates cannot be linked to the employee IDs they received, so joiner sentiment cannot be tied to hire source or recruiter.
* Requisitions raised in Sep–Oct are right-censored: only fast fills have closed, so recent TTF looks better than it is.
* 16 candidate rows have stage dates out of order; they are flagged and excluded from stage-duration metrics.
* Segments with fewer than 5 responses are hidden in the dashboard by default.
