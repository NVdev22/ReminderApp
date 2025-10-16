import os
import csv
import json
import re
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
import argparse

# Load .env if available (local runs)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'Data'
CLIENTS_FILE = DATA_DIR / 'clientes.csv'
CONFIG_FILE = DATA_DIR / 'config.json'

def parse_date_any(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

def format_date_display(s):
    d = parse_date_any(s)
    if d is None:
        return s or ""
    return d.strftime("%d/%m/%Y")

def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or "") is not None

def load_clients():
    clients = []
    if not CLIENTS_FILE.exists():
        return clients
    with CLIENTS_FILE.open('r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            emp = (row.get('empresa') or '').strip()
            ven = (row.get('vencimento') or '').strip()
            if not emp:
                continue
            clients.append({'empresa': emp, 'vencimento': ven})
    return clients

def load_config():
    """Load non-sensitive preferences from config.json, and all sensitive values from env.

    Sensitive: SMTP_EMAIL, SMTP_APP_PASSWORD, OWNER_EMAIL, DAYS_THRESHOLDS
    Non-sensitive: FROM_NAME (fallback from config.json if env empty)
    """
    cfg = {
        'smtp_email': os.environ.get('SMTP_EMAIL', ''),
        'app_password': os.environ.get('SMTP_APP_PASSWORD', ''),
        'owner_email': os.environ.get('OWNER_EMAIL', ''),
        'from_name': os.environ.get('FROM_NAME', '3N Licenças'),
        'days_thresholds': None,
    }

    env_multi = os.environ.get('DAYS_THRESHOLDS')
    if env_multi:
        try:
            parts = [p.strip() for p in env_multi.split(',') if p.strip()]
            vals = sorted({int(p) for p in parts if int(p) >= 0})
            if vals:
                cfg['days_thresholds'] = vals
        except Exception:
            cfg['days_thresholds'] = None
    if not cfg['days_thresholds']:
        cfg['days_thresholds'] = [30, 15, 5]

    # Fallback only for from_name from config.json (ignore any sensitive fields present)
    try:
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if not os.environ.get('FROM_NAME') and isinstance(data, dict):
                fn = data.get('from_name') or data.get('fromName')
                if isinstance(fn, str) and fn.strip():
                    cfg['from_name'] = fn.strip()
    except Exception:
        pass
    return cfg

def send_notifications(dry_run=False, only_expired=False):
    cfg = load_config()
    if not cfg.get('smtp_email') or not cfg.get('app_password'):
        raise SystemExit('Configuração incompleta: defina SMTP_EMAIL e SMTP_APP_PASSWORD ou configure Data/config.json')
    owner = cfg.get('owner_email') or cfg.get('smtp_email')
    if not valid_email(owner):
        raise SystemExit('Email do dono inválido: defina OWNER_EMAIL ou smtp_email válido')

    clients = load_clients()
    today = datetime.today().date()
    selected = []
    ths = cfg.get('days_thresholds') or []
    if not ths:
        ths = [30, 15, 5]
    ths_set = set(int(x) for x in ths if isinstance(x, int) and x >= 0)
    for c in clients:
        d = parse_date_any(c.get('vencimento'))
        if not d:
            continue
        delta = (d - today).days
        if only_expired:
            if delta < 0:
                selected.append((c, delta))
        else:
            if delta < 0 or delta in ths_set:
                selected.append((c, delta))

    if dry_run:
        print(f"Selecionados {len(selected)} empresas (dry-run):")
        for c, delta in selected:
            status = 'vencida' if delta < 0 else f'vence em {delta} dia(s)'
            print(f"- {c['empresa']}: {format_date_display(c['vencimento'])} ({status})")
        return

    context = ssl.create_default_context()
    # Compose single summary email
    subject = "[3N] Resumo de licenças - vencidas e próximas"
    lines = []
    if not selected:
        lines.append("Nenhuma licença vencida ou próxima do vencimento.")
    else:
        lines.append("Empresas com atenção:")
        for c, delta in sorted(selected, key=lambda x: x[1]):
            emp = c['empresa']
            ven_str = format_date_display(c['vencimento'])
            status = 'vencida' if delta < 0 else f'vence em {delta} dia(s)'
            lines.append(f"- {emp} | {ven_str} | {status}")
    body = ("Olá,\n\n" + "\n".join(lines) + "\n\n" + f"Atenciosamente,\n{cfg.get('from_name','3N Licenças')}")

    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
        server.login(cfg['smtp_email'], cfg['app_password'])
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = f"{cfg.get('from_name','3N Licenças')} <{cfg['smtp_email']}>"
        msg['To'] = owner
        msg.set_content(body)
        server.send_message(msg)
    print("Resumo enviado ao dono com sucesso.")

def main():
    parser = argparse.ArgumentParser(description='Enviar lembretes de vencimento (3N)')
    parser.add_argument('--dry-run', action='store_true', help='Somente listar destinatários, sem enviar')
    parser.add_argument('--only-expired', action='store_true', help='Enviar somente para vencidos')
    args = parser.parse_args()
    send_notifications(dry_run=args.dry_run, only_expired=args.only_expired)

if __name__ == '__main__':
    main()
