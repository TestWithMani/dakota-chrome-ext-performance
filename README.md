# Dakota Chrome Extension Performance

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-4.35%2B-43B02A.svg)](https://www.selenium.dev/)
[![pytest](https://img.shields.io/badge/pytest-7.4%2B-0A9EDC.svg)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

End-to-end performance automation for the **Dakota Marketplace** Chrome extension. The framework logs into the Dakota portal, loads the extension in headless Chrome, measures real user flows (search, detail views, tabs, load more), and produces **Excel**, **Allure**, and **JUnit** reports.

Built for CI/CD with **Jenkins** and local development on Windows.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [Running tests](#running-tests)
- [Reports](#reports)
- [Configuration](#configuration)
- [Jenkins CI/CD](#jenkins-cicd)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Capability | Description |
|------------|-------------|
| **Portal + extension login** | Authenticates on the Dakota Marketplace site and completes extension SSO |
| **BiDi extension install** | Downloads and installs the unpacked extension via Selenium 4 WebDriver BiDi |
| **Performance benchmarks** | Five timed scenarios with configurable companies, iterations, and thresholds |
| **Excel reporting** | Color-coded workbook: `reports/dakota_chrome_extension_results.xlsx` |
| **Allure + JUnit** | Rich HTML trends in Jenkins; machine-readable `test-results/` artifacts |
| **Headless CI** | Automatic headless Chrome when `CI`, `JENKINS_URL`, or `DAKOTA_HEADLESS=1` is set |
| **Parameterized Jenkins job** | Run full suite, smoke, or individual tests with email notifications |

---

## Architecture

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│  Dakota Portal  │────▶│  Chrome + Ext.   │────▶│  Performance tests      │
│  (Salesforce)   │     │  (Selenium BiDi) │     │  (pytest + Page Objects)│
└─────────────────┘     └──────────────────┘     └───────────┬─────────────┘
                                                               │
                     ┌─────────────────────────────────────────┼─────────────────────────┐
                     ▼                     ▼                     ▼                         ▼
              Excel report           Allure results          JUnit XML              Jenkins email
```

**Test flow (performance suite)**

1. Open [Dakota Marketplace](https://dakotanetworks.my.site.com/dakotaMarketplace/s/)
2. Log in with portal credentials
3. Install and activate the Dakota extension
4. Complete extension SSO (Salesforce sign-in button)
5. Execute timed actions (search, open company, tabs, load more)
6. Compare timings against benchmarks and write results to Excel

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.11+** | 3.13 recommended; Selenium 4.35+ required for WebExtension BiDi |
| **Google Chrome** | Latest stable channel |
| **Git** | Clone and Jenkins SCM checkout |
| **Dakota portal account** | Valid Marketplace login (not Jenkins credentials) |

**Optional (CI / reporting)**

- [Allure Commandline](https://github.com/allure-framework/allure2/releases) for local Allure reports
- Jenkins with **Allure Jenkins Plugin** and **Email Extension Plugin**

---

## Project structure

```text
.
├── conftest.py                 # Pytest fixtures (Chrome, login session, performance helper)
├── download_extension.py       # Downloads & unpacks Dakota .crx from Chrome Web Store
├── Jenkinsfile                 # Declarative Jenkins pipeline (SCM-based)
├── jenkins_setup.py            # One-time Jenkins job + credential provisioning
├── pages/
│   ├── dakota_auth.py          # Portal login and extension SSO
│   └── dakota_performance.py   # Timed search, detail, tab, and load-more actions
├── tests/
│   ├── test_dakota_search_time.py
│   ├── test_company_detail_loading_time.py
│   ├── test_company_contacts_loading_time.py
│   ├── test_company_type_specific_tab_loading_time.py
│   ├── test_search_load_more_time.py
│   └── test_dakota_login.py    # Portal + extension login (smoke)
├── utils/
│   ├── performance_config.py   # Companies, iterations, benchmark thresholds
│   └── search_report.py        # Excel report generation
├── requirements.txt            # Runtime dependencies
├── requirements-ci.txt         # CI-only plugins (Allure, HTML, JSON, reruns)
└── extensions/                 # Extension artifacts (gitignored; created at runtime)
```

---

## Quick start

### 1. Clone the repository

```powershell
git clone https://github.com/TestWithMani/dakota-chrome-ext-performance.git
cd dakota-chrome-ext-performance
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For local Allure/HTML reports, also install CI dependencies:

```powershell
pip install -r requirements-ci.txt
```

### 3. Configure credentials

Create `credentials.env` in the project root (gitignored), or set environment variables:

```env
DAKOTA_USERNAME=your_portal_email@example.com
DAKOTA_PASSWORD=your_portal_password
```

> **Important:** Jenkins UI login credentials are separate from Dakota portal credentials.

Or export environment variables:

```powershell
$env:DAKOTA_USERNAME = "your_portal_email@example.com"
$env:DAKOTA_PASSWORD = "your_portal_password"
```

### 4. Download the extension

```powershell
python download_extension.py
```

This creates `extensions/dakota.crx` and unpacks to `extensions/dakota/`.

### 5. Run tests

```powershell
# Full performance suite (~10 minutes)
pytest tests/ -m performance -v

# Smoke: login + search timing
pytest tests/ -m smoke -v
```

---

## Running tests

### Performance suite (all benchmarks)

```powershell
pytest tests/ -m performance -v
```

| Test file | What it measures |
|-----------|------------------|
| `test_dakota_search_time.py` | Company search response time |
| `test_company_detail_loading_time.py` | Company detail panel load time |
| `test_company_contacts_loading_time.py` | Contacts tab load time |
| `test_company_type_specific_tab_loading_time.py` | Profile tab by company type |
| `test_search_load_more_time.py` | Search “Load more” action time |

### Login / smoke

```powershell
pytest tests/test_dakota_login.py -m smoke -v
```

### Single test

```powershell
pytest tests/test_dakota_search_time.py -v
```

### Visual debugging (headed browser)

```powershell
# Omit CI/headless flags; optionally pause or keep browser open
pytest tests/test_dakota_login.py::test_dakota_login_step_by_step -v --keep-open
```

### Pytest markers

| Marker | Purpose |
|--------|---------|
| `performance` | Timing benchmarks with Excel output |
| `smoke` | Quick login validation |
| `auth` | Portal authentication flows |
| `extension` | Requires Chrome with Dakota extension |
| `visual` | Step-by-step login for manual observation |

---

## Reports

### Excel (primary performance output)

| Property | Value |
|----------|-------|
| **Path** | `reports/dakota_chrome_extension_results.xlsx` |
| **Columns** | Row Type, Test Case, Tab (company), Sample #, Time (s), Min, Max, Benchmark, Result, Browser, Recorded At, Platform |
| **Rows** | 3 iterations per company + 1 Run summary per company. Full suite: **5 tests × 2 companies = 10 run summaries** |
| **Pass/fail** | Each sample is compared to thresholds in `utils/performance_config.py` |

### Allure (local)

Reports include **step-by-step flows** (login, search, tab loads) and **screenshots** after each step. A failure screenshot and page URL are attached automatically.

After a test run with `allure-pytest` installed:

```powershell
allure serve allure-results
```

Generate a single-file offline report:

```powershell
allure generate allure-results -o allure-report --clean --single-file
```

> Multi-file Allure folders do not work when opened via `file://` in a browser (CORS). Use `allure serve`, Jenkins **Allure Report**, or `--single-file`.

### JUnit / HTML / JSON

Produced under `test-results/` when CI dependencies are installed (automatic on Jenkins).

---

## Configuration

### Benchmarks and test data

Edit `utils/performance_config.py`:

```python
DAKOTA_SEARCH_ITERATIONS = 3
DAKOTA_SEARCH_TEST_TERMS = ("Microsoft", "KPMG")
DAKOTA_SEARCH_PERFORMANCE_BENCHMARK_SEC = 10
```

### Headless mode

Enabled automatically when any of these are set:

- `DAKOTA_HEADLESS=1`
- `CI=true`
- `JENKINS_URL` is present

Force headed local runs by unsetting those variables.

### Extension ID

The Dakota Marketplace extension ID is defined in `download_extension.py`. Re-run `download_extension.py` after changing it.

---

## Jenkins CI/CD

### Repository

Pipeline is loaded from this repo via SCM:

| Setting | Value |
|---------|-------|
| **Repository** | `https://github.com/TestWithMani/dakota-chrome-ext-performance.git` |
| **Branch** | `main` |
| **Script path** | `Jenkinsfile` |
| **Job name** | `Dakota-Chrome-Extension-Performance` |

The same job runs on a **weekly schedule** defined in `Jenkinsfile` (`triggers { cron('33 16 * * 4') }` — Thursday 4:33 PM, Jenkins server timezone). Timer-triggered builds automatically use a different email preset:

| Scheduled run | Value |
|---------------|-------|
| **Default email** | `usman.arshad@rolustech.com` |
| **Additional emails** | `omer.shafiq@rolustech.net`, `imad.ali@rolustech.com`, `schal.hasnain@rolustech.com`, `faseeh.ahmad@rolustech.com` |
| **Other parameters** | Same as manual builds (`draftcrmdev@rolustech.com` default only applies to manual runs) |

Manual builds keep the parameter defaults (`DEFAULT_EMAIL`, `ADDITIONAL_EMAILS`, etc.).

### Provision the job (first time)

```powershell
pip install requests
python jenkins_setup.py
```

Optional: provision and trigger a build:

```powershell
python jenkins_setup.py --trigger-build
```

Configure `JENKINS_URL`, `JENKINS_USER`, and `JENKINS_PASSWORD` via environment variables before running the setup script in production.

### Jenkins credentials

Create a **Username with password** credential:

| Field | Value |
|-------|-------|
| **ID** | `dakota-portal-creds` |
| **Username** | Dakota portal email |
| **Password** | Dakota portal password |

### Pipeline parameters

| Parameter | Description |
|-----------|-------------|
| `DEFAULT_EMAIL` | Primary report recipient (default: `draftcrmdev@rolustech.com`) |
| `ADDITIONAL_EMAILS` | Comma-separated extra recipients |
| `DAKOTA_CREDENTIALS_ID` | Jenkins credential ID for portal login |
| `INFRA_RETRY_COUNT` | Retry flaky Selenium failures (always enabled; set `0` to disable) |
| `RUN_ALLURE` | Generate and publish Allure report in Jenkins |
| `SEND_EMAIL` | Send HTML summary email with attachments |

Each build **always runs the full test suite** (5 performance tests + login) and **always generates fresh** Excel, Allure, and JUnit artifacts.

### Allure in Jenkins

1. Install **Allure Jenkins Plugin**
2. **Manage Jenkins → Global Tool Configuration → Allure Commandline** — add installation (e.g. `allure-2.39`)
3. After a build, open **Allure Report** in the build sidebar (`…/allure/`)

### Viewing reports

| Method | Action |
|--------|--------|
| **Jenkins (recommended)** | Build → **Allure Report** |
| **Email** | Excel + summary attached when `SEND_EMAIL=true` |
| **Artifacts** | Download `reports/` and `test-results/` from build |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Dakota credentials not found` | Create `credentials.env` or set `DAKOTA_USERNAME` / `DAKOTA_PASSWORD` |
| Extension not loaded | Run `python download_extension.py`; ensure Selenium ≥ 4.35 |
| ChromeDriver mismatch | `webdriver-manager` resolves the driver automatically on first run |
| Tests slow or timeout | Increase waits in `pages/dakota_auth.py` / `dakota_performance.py` for slow networks |
| Allure `index.html` spins forever | Use Jenkins Allure UI, `allure serve`, or `--single-file` — not raw `file://` |
| Jenkins `checkout scm` fails | Ensure job uses **Pipeline script from SCM**, not inline script only |

---

## Contributing

1. Fork the repository and create a feature branch from `main`
2. Follow existing patterns: Page Objects in `pages/`, shared fixtures in `conftest.py`
3. Do not commit `credentials.env`, downloaded extensions, or local Chrome profiles
4. Run `pytest tests/ -m performance -v` before opening a pull request
5. Keep Jenkins parameters in sync with `Jenkinsfile` when adding tests

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Dakota Marketplace](https://chromewebstore.google.com/detail/dakota-marketplace/pkjcjmhoaajnghcgbkkdfgakcbdnpefj) Chrome extension
- [Selenium](https://www.selenium.dev/), [pytest](https://docs.pytest.org/), [Allure Report](https://allurereport.org/)
