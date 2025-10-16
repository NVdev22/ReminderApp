# 3N Licenças (ReminderApp) 🚀

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-CustomTkinter-1f6feb.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![Build](https://img.shields.io/badge/Build-PyInstaller-444.svg)](https://www.pyinstaller.org/)
[![License](https://img.shields.io/badge/License-MIT-success.svg)](#license)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)](#)

A desktop app in **Python + CustomTkinter** for managing **business license expirations** with **Gmail email reminders**.  
Runs locally with a modern GUI and can also run automatically on a server (e.g., **Render Cron Job** or **GitHub Actions**) using **environment variables** — no secrets in code.

> **Security-first:** credentials and recipients are loaded from environment variables. Real data (CSV/JSON) is ignored by Git via `.gitignore`.

---

## 📚 Table of Contents
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Data Format](#-data-format)
- [Credentials & Security](#-credentials--security)
- [Local Setup (GUI)](#%EF%B8%8F-local-setup-gui)
- [CLI Notifier](#-cli-notifier)
- [Automation (Render / GitHub Actions)](#-automation-render--github-actions)
- [Build Windows .exe](#-build-windows-exe)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)
- [Author](#-author)

---

## ✨ Features
- Add / edit / remove clients (company + expiration date).
- Color‑coded status in the table:
  - 🟩 **Green** — far from expiring
  - 🟨 **Yellow** — ≤ 30 days
  - 🟧 **Orange** — ≤ 15 days
  - 🟥 **Red** — expired
- Export to **Excel (.xlsx)** with styling (OpenPyXL).
- Send a **summary email** to the owner.
- **CLI** (`notify.py`) for scheduled/automated runs.
- **Security**: credentials via **environment variables** (no secrets in code).

---

## 🗂 Project Structure
```
ReminderApp/
├─ Data/
│  ├─ clientes.csv        # data (company, expiration)
│  └─ config.json         # display prefs (do NOT store passwords here)
├─ appScreens.py          # GUI (CustomTkinter)
├─ main.py                # desktop entry point
├─ notify.py              # headless notifier (for cron)
└─ .github/workflows/     # (optional) scheduled workflow(s)
```

> You can rename the root directory to your preference (e.g., `3N-ReminderApp`).

---

## 🧾 Data Format
**`Data/clientes.csv` example**
```csv
empresa,vencimento
Posto de gasolina,05/11/2025
Indústria de Calçados,2025-11-01
```
Accepted date formats: `DD/MM/YYYY` or `YYYY-MM-DD`.

---

## 🔐 Credentials & Security

**Never commit real emails or passwords.** Read everything from **environment variables** (locally via `.env` if you want, or in Render/GitHub Secrets):

| Variable            | Example                           | Notes                                  |
|---------------------|-----------------------------------|----------------------------------------|
| `SMTP_EMAIL`        | `notifications.3n@gmail.com`      | Gmail account used to send emails      |
| `SMTP_APP_PASSWORD` | `abcd xxxx yyyy zzzz`             | Gmail **App Password** (2FA required)  |
| `OWNER_EMAIL`       | `owner@company.com`               | Recipient of the daily summary         |
| `FROM_NAME`         | `3N Licenças`                     | Sender display name                    |
| `DAYS_THRESHOLDS`   | `30,15,5`                          | Comma-separated alert days             |

**Optional `.env.example`**
```ini
SMTP_EMAIL=
SMTP_APP_PASSWORD=
OWNER_EMAIL=
FROM_NAME=3N Licenças
DAYS_THRESHOLDS=30,15,5
```

**Recommended `.gitignore`**
```
__pycache__/
*.pyc
dist/
build/
*.spec
.env
Data/clientes.csv
Data/config.json
Data/*.db
Data/key.txt
```

> The app reads `Data/config.json` for non-sensitive preferences only. Do **not** store passwords there.

---

## 🖥️ Local Setup (GUI)

**Requirements**
- Python **3.11+**

**Install**
```bash
pip install customtkinter openpyxl
# optional if you add them later:
# pip install python-dotenv requests cryptography
```

**Run**
```bash
python main.py
```
- Manage clients under **Clientes**.
- Use **Configurar Gmail** to set sender name; provide the Gmail **App Password** only when sending.  
  **Recommended:** keep secrets in environment variables instead of saving them.

---

## 📨 CLI Notifier

Run from a terminal/shell:

```bash
# Dry run (print list, do not send email)
python notify.py --dry-run

# Only expired licenses
python notify.py --only-expired

# Normal run (expired + thresholds)
python notify.py
```

The notifier reads `Data/clientes.csv` and uses environment variables for Gmail credentials and settings.

---

## ☁️ Automation (Render / GitHub Actions)

### Render Cron Job
- **Start Command:** `python notify.py`  
- **Schedule (UTC):** `0 7 * * *` → 04:00 BRT  
- **Environment Variables:** add `SMTP_EMAIL`, `SMTP_APP_PASSWORD`, `OWNER_EMAIL`, `FROM_NAME`, `DAYS_THRESHOLDS`.

### GitHub Actions (optional)
```yaml
name: Lembretes 3N
on:
  schedule:
    - cron: "0 7 * * *"   # 07:00 UTC
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run notifier
        env:
          SMTP_EMAIL: ${{ secrets.SMTP_EMAIL }}
          SMTP_APP_PASSWORD: ${{ secrets.SMTP_APP_PASSWORD }}
          OWNER_EMAIL: ${{ secrets.OWNER_EMAIL }}
          FROM_NAME: ${{ secrets.FROM_NAME }}
          DAYS_THRESHOLDS: ${{ secrets.DAYS_THRESHOLDS }}
        run: python notify.py
```

---

## 📦 Build Windows .exe

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "3N_Licencas" main.py
# optional icon:
# pyinstaller --onefile --noconsole --icon Data/logo3n.ico --name "3N_Licencas" main.py
```

Output: `dist/3N_Licencas.exe`.

---

## 🛠 Troubleshooting

- **Gmail login blocked**  
  Enable 2‑Factor Authentication and create a **Gmail App Password**. Use it in `SMTP_APP_PASSWORD`.

- **No email sent on server**  
  Check service logs and confirm all **environment variables** are set.

- **Dates not recognized**  
  Ensure CSV uses `DD/MM/YYYY` or `YYYY-MM-DD` and the header is exactly `empresa,vencimento`.

- **GUI freeze during send**  
  (Optional improvement) move email sending to a background thread to keep the UI responsive.

---

## 🧭 Roadmap
- Switch storage from CSV to **SQLite** (more robust).
- **REST API** for cloud sync (Flask on Render) so multiple desktops can push updates.
- Optional local **password encryption** (Fernet) if you ever allow saving app passwords.
- HTML email templates.

---

## 🤝 Contributing
Issues and pull requests are welcome! Please avoid including real client data or secrets in any contribution.

---

## 📄 License
**MIT License** — simple and permissive. See the [LICENSE](LICENSE) file for details.

---

## 👤 Author
**NV Dev** — internal tool for license & compliance reminders.  
Suggestions and improvements are welcome!
