# Biostatistic Platform

[中文](README.md) | [English](README.en.md)

A local, single-user clinical trial statistics prototype. The app opens in English; **EN/中文** switches its UI language. The links above switch the README language.

## Start

On Windows, double-click [`start-platform.cmd`](start-platform.cmd). It runs `start.ps1`, waits for the services, and opens <http://127.0.0.1:8050> in the default browser. Keep the PowerShell service window open. Alternatively, run `.\start.ps1` from the project directory.

On a new computer, run `install.ps1` to install dependencies into `.venv` and `.r-library`. If R is outside `C:\Program Files\R`, set `RSCRIPT_PATH` to the full path of `Rscript.exe`. Dash, the R API, and the service manager use local ports 8050, 8000, and 8051. Logs are in `runtime`.

## Architecture

The Dash frontend comprises `app.py`, `survival_ui.py`, `ae_ui.py`, and `dose_ui.py`; `assets/style.css` and `assets/i18n.js` provide styling and UI translation. Dash submits jobs through the plumber API in `backend/api.R`. A separate R process runs `backend/worker.R`. Uploaded data and results are cached locally in `runtime`, while the browser receives paginated previews and results. `scripts/service_manager.py` manages the Dash and R services.

`scripts/make_demo.py` generates compact ADSL, ADAE, and ADTTE demo data with a fixed seed. These are synthetic, not real trial data or CDISC-certified datasets. Uploads are limited to 100 MB, and R still loads full datasets into memory for analysis.

## Statistical conventions

- **Baseline:** Apply the population equality filter first. Continuous variables report nonmissing/missing counts, mean and sample SD, median and Q1/Q3, and range; quartiles use R `quantile` type 7. Categorical percentages use the nonmissing count for each variable within each group as denominator. Missing counts are separate. No baseline p values are calculated.
- **Survival:** Use OS/PFS endpoints already derived in ADTTE; by default `CNSR=0` denotes an event and `1` censoring. Results include KM curves, numbers at risk, median survival, and log-rank p values. The adjusted Cox model uses Efron ties and complete cases for selected covariates, reporting HR, two-sided Wald p values, and 95% CIs. The forest plot shows model coefficients, not subgroup treatment effects.
- **Adverse events:** Deduplicate each event by subject. Default filters are `AEREL=Y` and `TRTEMFL=Y`; severe means grade ≥3, and displayed terms have ≥10% any-grade incidence in either group. Prefer matching ADSL safety subjects for denominators. Without ADSL, denominators include only subjects present in ADAE.
- **Dose:** BOIN calculates escalation/de-escalation boundaries from target DLT probability and toxicity bounds, with Beta(1,1) posterior safety exclusion. mTPI recommends escalation, staying, or de-escalation from UPM in three intervals at the current dose; its fitted curve is descriptive.

## Features

### 1 Baseline

Upload ADSL (CSV/XPT/SAS7BDAT) or load demo data. An optional variables file with `variable` and `label` adds preview header tooltips. Select treatment group, population, continuous and categorical variables; drag group chips to change order; generate a three-line table and download Word/CSV. Put numerically coded categories in the categorical-variable selector.

### 2 Survival

Upload ADTTE, optionally add ADSL covariates, or load paired demo data. Select OS/PFS, reference/comparison groups, time and censoring codes, and baseline covariates. Output includes KM plots, numbers at risk, adjusted Cox PH, a forest plot, and a PH test, with PDF/CSV/JSON exports. Each subject should have one analysis record per endpoint.

### 3 Adverse Event

Upload ADAE and optionally ADSL for safety denominators, or load demo data. Configure treatment group, event term, grade, and filters. Generate a three-line table of any-grade and severe AEs by group with summary rows, and download Word/CSV. Verify relatedness, treatment-emergent flags, and action mappings against the study plan before formal use.

### 4 Dose Escalation

**BOIN:** Enter target DLT probability, lower/upper toxicity bounds, and the patient limit. Generate a colored E (escalate), S (stay), D (de-escalate), and DE (exclude) decision table, downloadable as PNG/Excel.

**mTPI:** Enter evaluated and DLT counts by dose, current dose, target probability, and epsilon. View posterior interval probabilities, UPM, the fitted toxicity curve, and the next-dose recommendation. The right panel explains the method and parameters. CRM and 3+3 are outside this prototype.

Input errors are linked to relevant controls. The prototype has no multi-user authentication or production job scheduling; local data and results remain in `runtime`.
