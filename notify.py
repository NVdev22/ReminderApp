# notify.py
# Atualizado: versão segura para uso com repositório GitHub PRIVADO
# ---------------------------------------------------------------
# Lê o arquivo clientes.csv diretamente do GitHub usando variáveis
# de ambiente para autenticação e executa a análise de vencimentos.
#
# Variáveis obrigatórias:
#   GITHUB_REPO      -> Ex: "NVdev22/3N-CLIENTES"
#   GITHUB_TOKEN     -> Token com "Contents: Read and write"
#   SMTP_EMAIL       -> E-mail de envio (Gmail)
#   SMTP_APP_PASSWORD-> Senha de app do Gmail
#   OWNER_EMAIL      -> Destinatário
#
# O arquivo 'clientes.csv' será obtido do branch principal
# e nunca armazenado localmente nem impresso no terminal.

import os
import io
import re
import csv
import ssl
import base64
import smtplib
import argparse
import requests
from email.message import EmailMessage
from datetime import datetime

# ---------- Helpers de data ----------

def parse_date_any(s: str):
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            continue
    return None

def format_date_display(s: str):
    d = parse_date_any(s)
    return d.strftime("%d/%m/%Y") if d else s or ""

# ---------- CSV ----------

def load_clients_from_text(text: str):
    """Converte CSV em lista de dicts."""
    reader = csv.DictReader(io.StringIO(text))
    clients = []
    for row in reader:
        emp = (row.get("empresa") or "").strip()
        ven = (row.get("vencimento") or "").strip()
        if emp:
            clients.append({"empresa": emp, "vencimento": ven})
    return clients

# ---------- GitHub fetch seguro ----------

def load_clients_from_github():
    repo = os.environ.get("GITHUB_REPO", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    file_path = os.environ.get("GITHUB_FILE", "clientes.csv").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip()

    if not repo or not token:
        raise SystemExit("❌ Variáveis GITHUB_REPO e GITHUB_TOKEN obrigatórias.")

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code != 200:
        raise SystemExit(f"❌ Falha ao obter CSV do GitHub: {r.status_code} {r.text[:150]}")

    payload = r.json()
    content = payload.get("content")
    if not content:
        raise SystemExit("❌ Nenhum conteúdo encontrado no clientes.csv")

    text = base64.b64decode(content).decode("utf-8-sig")
    clients = load_clients_from_text(text)
    print(f"✅ {len(clients)} clientes carregados de {repo}/{file_path}")
    return clients

# ---------- Lógica de prazos ----------

def selecionar_vencimentos(clients):
    hoje = datetime.today().date()
    expirados = []
    proximos = []
    for c in clients:
        d = parse_date_any(c.get("vencimento"))
        if not d:
            continue
        delta = (d - hoje).days
        if delta < 0:
            expirados.append((c, delta))
        elif delta <= 30:
            proximos.append((c, delta))
    return expirados, proximos

# ---------- E-mail ----------

def enviar_email(cfg, expirados, proximos):
    linhas = []
    if expirados:
        linhas.append("⚠️ Licenças vencidas:")
        for c, delta in expirados:
            linhas.append(f"- {c['empresa']} (vencida há {-delta} dias, {format_date_display(c['vencimento'])})")
        linhas.append("")
    if proximos:
        linhas.append("📅 Vencendo em até 30 dias:")
        for c, delta in proximos:
            linhas.append(f"- {c['empresa']} (vence em {delta} dias, {format_date_display(c['vencimento'])})")
        linhas.append("")
    if not linhas:
        linhas.append("✅ Nenhuma licença vencida ou próxima do vencimento.")

    corpo = "\n".join(linhas)
    msg = EmailMessage()
    msg["Subject"] = "[3N] Resumo de Licenças - Vencimentos"
    msg["From"] = f"{cfg['FROM_NAME']} <{cfg['SMTP_EMAIL']}>"
    msg["To"] = cfg["OWNER_EMAIL"]
    msg.set_content(corpo)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(cfg["SMTP_EMAIL"], cfg["SMTP_APP_PASSWORD"])
        s.send_message(msg)
    print("📨 E-mail enviado com sucesso!")

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    clients = load_clients_from_github()
    expirados, proximos = selecionar_vencimentos(clients)

    print(f"💾 {len(expirados)} vencidos | {len(proximos)} próximos")

    if args.dry_run:
        for c, delta in expirados + proximos:
            status = "vencida" if delta < 0 else f"vence em {delta} dias"
            print(f"- {c['empresa']}: {format_date_display(c['vencimento'])} ({status})")
        return

    cfg = {
        "SMTP_EMAIL": os.environ.get("SMTP_EMAIL", ""),
        "SMTP_APP_PASSWORD": os.environ.get("SMTP_APP_PASSWORD", ""),
        "OWNER_EMAIL": os.environ.get("OWNER_EMAIL", ""),
        "FROM_NAME": os.environ.get("FROM_NAME", "3N Licenças"),
    }

    if not all(cfg.values()):
        raise SystemExit("❌ Configure SMTP_EMAIL, SMTP_APP_PASSWORD e OWNER_EMAIL nas variáveis de ambiente.")

    enviar_email(cfg, expirados, proximos)

if __name__ == "__main__":
    main()
