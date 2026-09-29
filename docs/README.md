# Project documentation

| Document | What it tracks |
|---|---|
| [logic-changelog.md](logic-changelog.md) | Every change to our own cleaning/analysis logic: what was wrong before, what changed, effect on results |
| [method-differences.md](method-differences.md) | Differences between our analysis and the TSMS draft report, including feedback items and questions for TSMS |
| [sensor-failures.md](sensor-failures.md) | Catalog of sensor failures and malfunctions (SF-xx), with removal periods and evidence |
| [potential-fixes.md](potential-fixes.md) | Backlog of identified but unimplemented or deferred improvements (PF-xx) |
| [qc-framework.md](qc-framework.md) | The QC procedure step by step (one job per step), principles from WMO-No. 8, status, and questions for the team |
| [station-events.csv](station-events.csv) | Machine-readable station events (maintenance visits, sensor changes, documented failures, known bad periods) applied by QC Step 1: remove / flag / note |
| [Maintenance-Logs/](Maintenance-Logs/) | January 2024 site-visit logs, evaluation plan and photos (source for station-events.csv) |
| [methods.md](methods.md) | Draft methods text: data sources, the CHORDS column correction, the TSMS04 temperature exclusion, recovered-data windows |
| [siting.md](siting.md) | Known site limitations (Konya courtyard/wall, Ankara hill) and how they affect interpretation |
| [oscar-requirements.md](oscar-requirements.md) | Extract of WMO OSCAR/Requirements for surface variables (goal/breakthrough/threshold by application area) |
| [figures/](figures/) | Diagnostic figures referenced by the documents above |

Framing: `3D-PAWS as a Baseline Tier Observing Network.pdf` (Vision 2040 tiers). TSMS reference sensors: `TSMS Sensors.docx`.

Team briefing (2026-09-28): https://claude.ai/artifact/1Q1vqMdyTmExMce5eYGEfL, built from `scripts/comparison/compare_with_report.py` output.

WMO references: WMO-No. 8 Vol. I (2024), Vol. III (2024), Vol. V (2023); see potential-fixes PF-15 for the relevant sections.

Source report: `TSMS_3D-PAWS_DATA_ANALYSIS_REPORT (2).pdf` (draft). It's treated as a
comparison target, not ground truth.
