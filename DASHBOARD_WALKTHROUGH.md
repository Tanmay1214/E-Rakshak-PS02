# E-RAKSHAK Dashboard & Unified Pipeline Integration Walkthrough

We've completely overhauled the E-RAKSHAK Dashboard to enforce forensic integrity requirements, and successfully integrated our local UI work with the massive backend updates introduced in the remote `main` branch.

## What changed?

### 1. Mandatory Case Intake Gating (Frontend)
To ensure absolute chain of custody and forensic accountability, we designed a mandatory intake flow that blocks access to the forensic data until the examiner logs their details.
- **Case Intake Wizard (`CaseIntakeWizard.tsx`)**: A full-screen, 3-step modern wizard using dynamic micro-animations and a sleek dark mode UI. It prompts the user for:
  1. **Examiner Details**: Name, agency, and badge number.
  2. **Evidence Logging**: Seized items, original filenames, hash algorithms, and acquisition methods.
  3. **Chain of Custody**: Documenting who collected the data, storage location, and exact timestamps.
- **Gated Dashboard (`CaseDashboard.tsx`)**: The main React layout now verifies the database for existing intake metadata on load. If missing, it immediately redirects the user to the Intake Wizard. No data is exposed until this form is completed.
- **Editable Case Info Page (`CaseInfoPage.tsx`)**: A dedicated settings view where examiners can update the intake details and add new chain of custody transfer events over time.

### 2. Backend Metadata Architecture (Phase 2)
The backend now permanently stores and serves this critical administrative metadata.
- **New SQLite Schema**: We implemented 3 new tables (`examiner_info`, `chain_of_custody`, `evidence_metadata`) in `db.py`.
- **Persistent Data Protection**: Updated `clear_all()` to ensure that when the dashboard dynamically refreshes its timeline indexing, the human-entered examiner metadata is *never* deleted.
- **8 New API Endpoints**: Created robust CRUD operations in `api.py` (e.g., `/api/case/examiner`, `/api/case/custody`) for the React frontend to communicate with.
- **Automated Reporting (`report_export.py`)**: The HTML Export report has been modified to automatically inject the Examiner name, Chain of Custody log, and Evidence Hashes at the very top of the finalized document.

### 3. Merging the Unified Forensic Timeline (Git Sync)
We pulled down the 9 remote commits from `origin/main` without losing any of our dashboard work:
- **Collision Resolution**: The remote branch introduced a new `timeline_builder.py` designed to compile the unified Phase 1 timeline directly from ADB devices. Since our dashboard branch *also* created a file named `timeline_builder.py`, we meticulously separated the logic, renaming our frontend tool to `dashboard_indexer.py`.
- **CLI Unified Merge**: The E-RAKSHAK CLI (`cli.py`) now harmoniously contains both sets of features:
  - `acquire-part-a`, `build-timeline`, and the massive `unified-pipeline` from the remote branch.
  - `dashboard` and `build-dashboard-index` from our local frontend work.

## Verification
- **Test Suite**: Updated the backend test suite to use the separated indexer. All 14 tests (`pytest backend/tests/test_dashboard.py`) passed cleanly.
- **Build**: The React frontend (`npm run build`) compiled successfully with 0 errors.

You can start the fully integrated environment via:
```powershell
python -m erakshak dashboard --case CASE001 --exhibit EX001
```
