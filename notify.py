# notify.py
# Summary:
# - Fetches clientes.csv from GitHub (private or public)
# - Falls back to Render Secret File (/etc/secrets/clientes.csv) or local Data/clientes.csv
# - Sends a summary email via Gmail (App Password) for expired and upcoming expirations
#
# Env vars required (set in Render Environment):
#   SMTP_EMAIL, SMTP_APP_PASSWORD, OWNER_EMAIL
# Optional:
#   FROM_NAME (default: "3N Licenças")
#   DAYS_THRESHOLDS (e.g., "30,15,5")
#   GITHUB_REPO (e.g., "NVdev22/3N-CLIENTES")
#   GITHUB_FILE (default: "clientes.csv")
#   GITHUB_BRANCH (default: "main")
#   GITHUB_TOKEN (required only if repo is PRIVATE)
#
# CLI:
#   python notify.py --dry-run        # list only
#   python notify.py --only-expired   # send only expired

import os
import re
import io
import csv
import ssl
import base64
import smtplib
import argparse
import requests
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path

# ---------- Helpers: dates & parsing ----------

def parse_date_any(s: str):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

def format_date_display(s: str):
    d = parse_date_any(s)
    if d is None:
        return s or ""
    return d.strftime("%d/%m/%Y")

def valid_email(email: str):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or "") is not None

def parse_thresholds(env_val: str, default_list=(30, 15, 5)):
    if not env_val:
        return list(default_list)
    try:
        vals = sorted({int(p.strip()) for p in env_val.split(",") if p.strip()})
        return [v for v in vals if v >= 0] or list(default_list)
    except Exception:
        return list(default_list)

# ---------- Sources for clientes.csv ----------

SECRET_PATH = Path("/etc/secrets/clientes.csv")
LOCAL_DATA_FILE = Path(__file__).resolve().parent / "Data" / "clientes.csv"

def _sniff_csv(text: str):
    """Return a reader for text handling comma or semicolon."""
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        delim = dialect.delimiter
    except Exception:
        delim = "," if sample.count(",") >= sample.count(";") else ";"
    return csv.DictReader(io.StringIO(text), delimiter=delim)

def load_clients_from_text(text: str):
    """Parse CSV text into [{'empresa':..., 'vencimento':...}, ...]."""
    out = []
    reader = _sniff_csv(text)

    # Normalize possible header variants
    def pick(row, *keys):
        for k in keys:
            if k in row and row[k]:
                return row[k]
        return ""

    for row in reader:
        emp = (pick(row, "empresa", "company", "nome", "name") or "").strip()
        ven = (pick(row, "vencimento", "due", "due_date", "data", "vence_em") or "").strip()
        if not emp:
            continue
        out.append({"empresa": emp, "vencimento": ven})
    return out

def load_clients_from_github():
    repo = os.environ.get("GITHUB_REPO", "").strip()
    file_path = os.environ.get("GITHUB_FILE", "clientes.csv").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not repo:
        return None, "GITHUB_REPO not set"

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            payload = r.json()
            content = payload.get("content")
            encoding = payload.get("encoding", "base64")
            if content and encoding == "base64":
                text = base64.b64decode(content).decode("utf-8-sig")
                clients = load_clients_from_text(text)
                return clients, f"github:{repo}/{file_path}@{branch}"
            return None, f"unexpected GitHub content encoding: {encoding}"
        elif r.status_code in (401, 403):
            return None, "unauthorized (private repo? set GITHUB_TOKEN)"
        elif r.status_code == 404:
            return None, "not found (check GITHUB_FILE / branch)"
        return None, f"GitHub HTTP {r.status_code}"
    except Exception as e:
        return None, f"GitHub fetch error: {e}"

def load_clients_from_file(path: Path):
    if not path.exists():
        return None, f"file not found: {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        # fallback to latin-1 if needed
        text = path.read_text(encoding="latin-1")
    clients = load_clients_from_text(text)
    return clients, str(path)

def load_clients():
    """Try GitHub -> Secret File -> Local file."""
    # 1) GitHub
    clients, src = load_clients_from_github()
    if clients is not None:
        return clients, src

    # 2) Render Secret File
    clients, src2 = load_clients_from_file(SECRET_PATH)
    if clients is not None:
        return clients, src2

    # 3) Local Data file
    clients, src3 = load_clients_from_file(LOCAL_DATA_FILE)
    if clients is not None:
        return clients, src3

    # None worked
    return [], f"no source available (GitHub: {src}; SecretFile: {src2}; Local: {src3})"

# ---------- Email + business logic ----------

def build_config():
    cfg = {
        "smtp_email": os.environ.get("SMTP_EMAIL", "").strip(),
        "app_password": os.environ.get("SMTP_APP_PASSWORD", "").strip(),
        "owner_email": os.environ.get("OWNER_EMAIL", "").strip(),
        "from_name": os.environ.get("FROM_NAME", "3N Licenças").strip(),
        "thresholds": parse_thresholds(os.environ.get("DAYS_THRESHOLDS", "")),
    }
    return cfg

def select_due(clients, thresholds, only_expired=False):
    today = datetime.today().date()
    ths = set(int(x) for x in thresholds if isinstance(x, int))
    selected = []
    for c in clients:
        d = parse_date_any(c.get("vencimento"))
        if not d:
            continue
        delta = (d - today).days
        if only_expired:
            if delta < 0:
                selected.append((c, delta))
        else:
            if delta < 0 or delta in ths:
                selected.append((c, delta))
    return selected

def compose_email_lines(selected):
    if not selected:
        return ["Nenhuma licença vencida ou próxima do vencimento."]
    lines = ["Empresas com atenção:"]
    for c, delta in sorted(selected, key=lambda x: x[1]):
        emp = c.get("empresa", "")
        ven_str = format_date_display(c.get("vencimento", ""))
        status = "vencida" if delta < 0 else f"vence em {delta} dia(s)"
        lines.append(f"- {emp} | {ven_str} | {status}")
    return lines

def send_email(cfg, lines):
    subject = "[3N] Resumo de licenças - vencidas e próximas"
    body = "Olá,\n\n" + "\n".join(lines) + "\n\nAtenciosamente,\n" + cfg.get("from_name", "3N Licenças")

    owner = cfg.get("owner_email") or cfg.get("smtp_email")
    if not valid_email(owner):
        raise SystemExit("❌ OWNER_EMAIL inválido (ou defina SMTP_EMAIL).")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(cfg["smtp_email"], cfg["app_password"])
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{cfg.get('from_name','3N Licenças')} <{cfg['smtp_email']}>"
        msg["To"] = owner
        msg.set_content(body)
        server.send_message(msg)

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Enviar lembretes de vencimento (3N)")
    parser.add_argument("--dry-run", action="store_true", help="Somente listar, sem enviar")
    parser.add_argument("--only-expired", action="store_true", help="Enviar somente vencidos")
    args = parser.parse_args()

    cfg = build_config()
    if not cfg["smtp_email"] or not cfg["app_password"]:
        raise SystemExit("❌ Defina SMTP_EMAIL e SMTP_APP_PASSWORD.")

    clients, source = load_clients()
    if not clients:
        print(f"⚠️  Nenhum cliente carregado ({source}).")
        if args.dry_run:
            return
        # Envia mesmo assim avisando lista vazia
        send_email(cfg, ["Nenhuma licença cadastrada."])
        print("✅ Email enviado (lista vazia).")
        return

    selected = select_due(clients, cfg["thresholds"], only_expired=args.only_expired)

    if args.dry_run:
        print(f"Fonte dos dados: {source}")
        print(f"Selecionados {len(selected)} empresas (dry-run):")
        for c, delta in selected:
            status = "vencida" if delta < 0 else f"vence em {delta} dia(s)"
            print(f"- {c['empresa']}: {format_date_display(c['vencimento'])} ({status})")
        return

    lines = compose_email_lines(selected)
    send_email(cfg, lines)
    print(f"✅ Resumo enviado com sucesso. Fonte dos dados: {source}")

if __name__ == "__main__":
    main()
