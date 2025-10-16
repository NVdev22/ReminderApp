import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import os
import csv
import json
import re
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        #Variaveis
        self.initialAppWidth = 1500
        self.initialAppHeight = 630
        self.screenWidth = self.winfo_screenwidth()
        self.screenHeight = self.winfo_screenheight()
        self.appTitle = {"menu":"3N Menu", "verClientes":"3N Clientes"}
        self.appInitialPosX = int((self.screenWidth / 2) - (self.initialAppWidth / 2))
        self.appInitialPosY = int((self.screenHeight / 2) - (self.initialAppHeight / 2))
        self.data_dir = os.path.join(os.path.dirname(__file__), "Data")
        self.data_file = os.path.join(self.data_dir, "clientes.csv")
        self.config_file = os.path.join(self.data_dir, "config.json")
        self.clients = []  # [{"empresa": str, "vencimento": str(YYYY-MM-DD)}]
        # Only non-sensitive preferences persist here (e.g., from_name)
        self.gmail_prefs = {"from_name": "3N Licenças"}
        # Runtime-only overrides (temporary for this session; never saved)
        self.runtime_cfg = {"smtp_email": None, "app_password": None, "owner_email": None, "days_thresholds": None, "from_name": None}

        #App Config
        self.title(self.appTitle["menu"])
        ctk.set_appearance_mode("dark")
        self.geometry(f"{self.initialAppWidth}x{self.initialAppHeight}+{self.appInitialPosX}+{self.appInitialPosY}")
        self.minsize(700, 420)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Load .env if available (local runs)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
        self._ensure_data_store()
        self._load_clients()
        self._load_config()

        #Frames Logic
        self.menu_frame = self.create_menu()
        self.last_frame = None
        self.clients_frame = self.create_clients_view()
        # Inicia no menu (mais intuitivo / minimalista)
        self.show_menu()

        # Friendly warning if key env vars are missing
        self.after(300, self._check_env_warn)


    def create_menu(self):
        frame = ctk.CTkFrame(self)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(frame)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Card central minimalista
        card = ctk.CTkFrame(container, corner_radius=12)
        card.grid(row=0, column=0, padx=30, pady=30)
        for i in range(6):
            card.grid_rowconfigure(i, weight=1)
        card.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(card, text="3N", font=ctk.CTkFont(size=36, weight="bold"))
        title.grid(row=0, column=0, padx=30, pady=(30, 6))
        subtitle = ctk.CTkLabel(card, text="Gestão de Licenças", font=ctk.CTkFont(size=16))
        subtitle.grid(row=1, column=0, padx=30, pady=(0, 20))

        btn_clientes = ctk.CTkButton(card, width=280, height=46, corner_radius=10, text="Clientes", command=self.show_clients)
        btn_clientes.grid(row=2, column=0, padx=30, pady=8)

        btn_gmail = ctk.CTkButton(card, width=180, height=36, corner_radius=8, text="Configurar Gmail", command=self._open_gmail_config)
        btn_gmail.grid(row=3, column=0, padx=30, pady=(8, 16))

        btn_sair = ctk.CTkButton(card, width=140, height=34, corner_radius=8, text="Sair", command=self.destroy)
        btn_sair.grid(row=4, column=0, padx=30, pady=(0, 24))
        return frame

    def show_menu(self):
        if self.last_frame is not None:
            self.last_frame.pack_forget()

        if self.last_frame == self.menu_frame:
            return
        
        self.title(self.appTitle["menu"])
        self.menu_frame.pack(fill="both", expand=True)
        self.last_frame = self.menu_frame

    def show_clients(self):
        if self.last_frame == self.clients_frame:
            return
        
        if self.last_frame is not None:
            self.last_frame.pack_forget()
        self.title(self.appTitle["verClientes"])
        self.clients_frame.pack(fill="both", expand=True)
        self.refresh_table()
        self.last_frame = self.clients_frame

    def create_clients_view(self):
        frame = ctk.CTkFrame(self)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Top bar
        top = ctk.CTkFrame(frame)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top.grid_columnconfigure(0, weight=1)
        title = ctk.CTkLabel(top, text="Clientes (Empresa / Vencimento)", font=ctk.CTkFont(size=18, weight="bold"))
        title.grid(row=0, column=0, sticky="w")
        self.menu_btn = ctk.CTkButton(top, width=120, height=30, corner_radius=6, text="Menu", command=self.show_menu)
        self.menu_btn.grid(row=0, column=1, padx=6)
        cfgBtn = ctk.CTkButton(top, width=160, height=30, corner_radius=6, text="Configurar Gmail", command=self._open_gmail_config)
        cfgBtn.grid(row=0, column=2, padx=6)

        # Table area
        table_frame = ctk.CTkFrame(frame)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Treeview inside native tkinter Frame for scrollbars compatibility
        tv_container = tk.Frame(table_frame)
        tv_container.grid(row=0, column=0, sticky="nsew")
        tv_container.grid_rowconfigure(0, weight=1)
        tv_container.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tv_container, columns=("empresa", "vencimento"), show="headings", selectmode="browse")
        self.tree.heading("empresa", text="Empresa")
        self.tree.heading("vencimento", text="Vencimento (DD/MM/AAAA)")
        self.tree.column("empresa", anchor=tk.W, width=520, stretch=True)
        self.tree.column("vencimento", anchor=tk.CENTER, width=200, stretch=True)

        y_scroll = ttk.Scrollbar(tv_container, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tv_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        # Configure fonts and readability for the Treeview
        style = ttk.Style(self)
        # Ensure a theme compatible with custom styling
        try:
            style.theme_use(style.theme_use())
        except Exception:
            pass
        self._tv_font = tkfont.Font(family='Segoe UI', size=13, weight='bold')
        self._tv_head_font = tkfont.Font(family='Segoe UI', size=14, weight='bold')
        style.configure('Treeview', font=self._tv_font, rowheight=30)
        style.configure('Treeview.Heading', font=self._tv_head_font)

        # Configure row tags for highlighting and zebra stripes
        self.tree.tag_configure('expired', background='#7a2f2f', foreground='#ffffff')  # vermelho
        self.tree.tag_configure('due_15', background='#a85f00', foreground='#ffffff')   # laranja
        self.tree.tag_configure('due_month', background='#b59f3b', foreground='#ffffff')  # amarelo
        self.tree.tag_configure('ok_far', background='#2f7a3d', foreground='#ffffff')   # verde
        self.tree.tag_configure('normal', background='')
        self.tree.tag_configure('even', background='#1f1f1f')
        self.tree.tag_configure('odd', background='#262626')

        # Controls
        controls = ctk.CTkFrame(frame)
        controls.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        for i in range(10):
            controls.grid_columnconfigure(i, weight=1)

        empresa_label = ctk.CTkLabel(controls, text="Empresa:")
        empresa_label.grid(row=0, column=0, padx=6, pady=6, sticky="e")
        self.empresa_entry = ctk.CTkEntry(controls, placeholder_text="Nome da empresa")
        self.empresa_entry.grid(row=0, column=1, padx=6, pady=6, sticky="ew")

        venc_label = ctk.CTkLabel(controls, text="Vencimento:")
        venc_label.grid(row=0, column=2, padx=6, pady=6, sticky="e")
        self.venc_entry = ctk.CTkEntry(controls, placeholder_text="DD/MM/AAAA")
        self.venc_entry.grid(row=0, column=3, padx=6, pady=6, sticky="ew")

        add_btn = ctk.CTkButton(controls, text="Adicionar", width=110, command=self.add_client)
        add_btn.grid(row=0, column=4, padx=6, pady=6)

        remove_btn = ctk.CTkButton(controls, text="Remover selecionado", width=160, command=self.remove_selected_client)
        remove_btn.grid(row=0, column=5, padx=6, pady=6)

        edit_btn = ctk.CTkButton(controls, text="Editar selecionado", width=150, command=self.edit_selected_client)
        edit_btn.grid(row=0, column=6, padx=6, pady=6)

        export_x_btn = ctk.CTkButton(controls, text="Exportar (Excel)", width=120, command=self.export_clients_excel)
        export_x_btn.grid(row=0, column=7, padx=6, pady=6)

        refresh_btn = ctk.CTkButton(controls, text="Recarregar", width=110, command=self.refresh_table)
        refresh_btn.grid(row=0, column=8, padx=6, pady=6)

        notify_btn = ctk.CTkButton(controls, text="Enviar lembrete (dono)", width=170, command=self.send_notifications)
        notify_btn.grid(row=0, column=9, padx=6, pady=6)

        legend = ctk.CTkLabel(frame, text="Legenda: Longe (verde), 30 dias (amarelo), 15 dias (laranja), Vencidas (vermelho)")
        legend.grid(row=3, column=0, padx=12, pady=(0, 10), sticky='w')

        return frame

    # Data helpers
    def _ensure_data_store(self):
        if not os.path.isdir(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["empresa", "vencimento"])  # header

    def _load_clients(self):
        self.clients = []
        try:
            with open(self.data_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    emp = (row.get("empresa") or "").strip()
                    ven = (row.get("vencimento") or "").strip()
                    if not emp:
                        continue
                    d = self._parse_date_any(ven)
                    ven_iso = d.strftime("%Y-%m-%d") if d else ven
                    self.clients.append({"empresa": emp, "vencimento": ven_iso})
        except FileNotFoundError:
            self._ensure_data_store()

    def _save_clients(self):
        with open(self.data_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["empresa", "vencimento"])
            for c in self.clients:
                writer.writerow([c["empresa"], self._format_date_display(c.get("vencimento", ""))])

    # UI actions
    def refresh_table(self):
        # Clear rows
        for i in self.tree.get_children():
            self.tree.delete(i)
        # Sort by vencimento if valid date, else by empresa
        def sort_key(c):
            d = self._parse_date_any(c.get("vencimento", ""))
            if d is not None:
                return (0, d)
            return (1, c.get("empresa", ""))
        for idx, c in enumerate(sorted(self.clients, key=sort_key)):
            tag = self._row_tag_for_client(c)
            display_date = self._format_date_display(c.get("vencimento", ""))
            if tag == 'normal':
                zebra = 'even' if idx % 2 == 0 else 'odd'
                tags = (zebra,)
            else:
                tags = (tag,)
            self.tree.insert("", tk.END, values=(c.get("empresa",""), display_date), tags=tags)

    def add_client(self):
        empresa = self.empresa_entry.get().strip()
        venc = self.venc_entry.get().strip()
        if not empresa:
            messagebox.showerror("Erro", "Informe o nome da empresa.")
            return
        if venc:
            if not self._valid_date(venc):
                messagebox.showerror("Erro", "Data inválida. Use DD/MM/AAAA.")
                return
            venc_iso = self._to_iso_str(venc)
        else:
            venc_iso = ""
        self.clients.append({"empresa": empresa, "vencimento": venc_iso})
        self._save_clients()
        self.empresa_entry.delete(0, tk.END)
        self.venc_entry.delete(0, tk.END)
        self.refresh_table()

    def remove_selected_client(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Remover", "Selecione um cliente na tabela.")
            return
        values = self.tree.item(sel[0], "values")
        empresa_sel, venc_sel = values[0], values[1]
        venc_sel_iso = self._to_iso_str(venc_sel) if venc_sel else ""
        # Remove first match
        removed = False
        for i, c in enumerate(self.clients):
            if c.get("empresa") != empresa_sel:
                continue
            stored = c.get("vencimento", "")
            if (venc_sel_iso and stored == venc_sel_iso) or (not venc_sel_iso and self._format_date_display(stored) == venc_sel):
                del self.clients[i]
                removed = True
                break
        if removed:
            self._save_clients()
            self.refresh_table()
        else:
            messagebox.showwarning("Aviso", "Cliente não encontrado nos dados.")

    def edit_selected_client(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecione um cliente na tabela.")
            return
        values = self.tree.item(sel[0], "values")
        old_empresa, old_venc_disp = values[0], values[1]
        old_venc_iso = self._to_iso_str(old_venc_disp) if old_venc_disp else ""

        dlg = ctk.CTkToplevel(self)
        dlg.title("Editar Cliente - 3N")
        dlg.geometry("420x200")
        dlg.grab_set()
        dlg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="Empresa:").grid(row=0, column=0, padx=10, pady=(15, 8), sticky="e")
        empresa_e = ctk.CTkEntry(dlg)
        empresa_e.grid(row=0, column=1, padx=10, pady=(15, 8), sticky="ew")
        empresa_e.insert(0, old_empresa)

        ctk.CTkLabel(dlg, text="Vencimento (DD/MM/AAAA):").grid(row=1, column=0, padx=10, pady=8, sticky="e")
        venc_e = ctk.CTkEntry(dlg, placeholder_text="DD/MM/AAAA")
        venc_e.grid(row=1, column=1, padx=10, pady=8, sticky="ew")
        venc_e.insert(0, old_venc_disp)

        def on_save():
            new_emp = empresa_e.get().strip()
            new_venc = venc_e.get().strip()
            if not new_emp:
                messagebox.showerror("Editar", "Informe o nome da empresa.")
                return
            if new_venc and not self._valid_date(new_venc):
                messagebox.showerror("Editar", "Data inválida. Use DD/MM/AAAA.")
                return
            new_venc_iso = self._to_iso_str(new_venc) if new_venc else ""
            # Update first match
            updated = False
            for i, c in enumerate(self.clients):
                if c.get("empresa") != old_empresa:
                    continue
                stored = c.get("vencimento", "")
                if (old_venc_iso and stored == old_venc_iso) or (not old_venc_iso and self._format_date_display(stored) == old_venc_disp):
                    self.clients[i] = {"empresa": new_emp, "vencimento": new_venc_iso}
                    updated = True
                    break
            if not updated:
                messagebox.showwarning("Editar", "Registro original não encontrado. Recarregue a tabela.")
            else:
                self._save_clients()
                self.refresh_table()
            dlg.destroy()

        btn_row = ctk.CTkFrame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=15)
        ctk.CTkButton(btn_row, text="Salvar", width=120, command=on_save).pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(btn_row, text="Cancelar", width=120, command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    # CSV export removed from UI; use Excel export

    def export_clients_excel(self):
        if not self.clients:
            messagebox.showinfo("Exportar", "Não há dados para exportar.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            title="Salvar lista de clientes (Excel)"
        )
        if not file_path:
            return
        # Build a formatted, print-friendly Excel using openpyxl
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            wb = Workbook()
            ws = wb.active
            ws.title = 'Clientes 3N'

            # Title
            title = "3N - Clientes e Vencimentos"
            ws.merge_cells('A1:B1')
            c = ws['A1']
            c.value = title
            c.font = Font(size=18, bold=True)
            c.alignment = Alignment(horizontal='center')

            # Generated time
            ws.merge_cells('A2:B2')
            gen = ws['A2']
            gen.value = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            gen.font = Font(size=12)
            gen.alignment = Alignment(horizontal='center')

            # Header
            ws['A3'].value = 'Empresa'
            ws['B3'].value = 'Vencimento'
            header_fill = PatternFill('solid', fgColor='1F4E78')
            header_font = Font(color='FFFFFF', bold=True, size=14)
            for col in ('A', 'B'):
                cell = ws[f'{col}3']
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center')

            # Data rows
            thin = Side(style='thin', color='CCCCCC')
            border = Border(left=thin, right=thin, top=thin, bottom=thin)
            row_start = 4

            # Prepare sorted list with status
            def sort_key(crow):
                d = self._parse_date_any(crow.get('vencimento',''))
                return (0, d) if d else (1, crow.get('empresa',''))

            sorted_rows = sorted(self.clients, key=sort_key)
            for i, cdata in enumerate(sorted_rows):
                empresa = cdata.get('empresa','')
                venc = self._format_date_display(cdata.get('vencimento',''))
                status = self._row_tag_for_client(cdata)
                r = row_start + i
                ws[f'A{r}'].value = empresa
                ws[f'B{r}'].value = venc
                # Styling
                for col in ('A', 'B'):
                    cell = ws[f'{col}{r}']
                    cell.font = Font(size=14)
                    cell.border = border
                    cell.alignment = Alignment(horizontal='left' if col=='A' else 'center', vertical='center')
                # Row fill by status
                if status == 'expired':
                    fill = PatternFill('solid', fgColor='FFC7CE')  # light red
                elif status == 'due_15':
                    fill = PatternFill('solid', fgColor='FCE4D6')  # light orange
                elif status == 'due_month':
                    fill = PatternFill('solid', fgColor='FFF2CC')  # light yellow
                elif status == 'ok_far':
                    fill = PatternFill('solid', fgColor='E2EFDA')  # light green
                else:
                    fill = None
                if fill:
                    ws[f'A{r}'].fill = fill
                    ws[f'B{r}'].fill = fill
                # Row height
                ws.row_dimensions[r].height = 24

            # Column widths
            ws.column_dimensions['A'].width = 60
            ws.column_dimensions['B'].width = 20

            # Freeze header
            ws.freeze_panes = 'A4'

            # Print setup
            ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
            ws.page_setup.fitToWidth = 1
            ws.sheet_view.showGridLines = False
            ws.print_title_rows = '1:3'
            ws.page_margins.left = 0.4
            ws.page_margins.right = 0.4
            ws.page_margins.top = 0.5
            ws.page_margins.bottom = 0.5

            wb.save(file_path)
            messagebox.showinfo("Exportar", f"Exportado com sucesso para:\n{file_path}")
        except Exception as e:
            messagebox.showerror(
                "Erro ao exportar Excel",
                "Falha ao exportar para Excel com formatação. Instale o pacote 'openpyxl'.\n\nErro: " + str(e)
            )

    def _valid_date(self, s):
        try:
            datetime.strptime(s, "%d/%m/%Y")
            return True
        except Exception:
            return False

    def _parse_date_any(self, s):
        if not s:
            return None
        s = s.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        return None

    def _to_iso_str(self, s):
        d = self._parse_date_any(s)
        if d is None:
            return ""
        return d.strftime("%Y-%m-%d")

    def _format_date_display(self, s):
        d = self._parse_date_any(s)
        if d is None:
            return s or ""
        return d.strftime("%d/%m/%Y")

    def _row_tag_for_client(self, c):
        ven = c.get("vencimento", "").strip()
        if not ven:
            return 'normal'
        d = self._parse_date_any(ven)
        if d is None:
            return 'normal'
        today = datetime.today().date()
        if d < today:
            return 'expired'
        delta = (d - today).days
        if delta <= 15:
            return 'due_15'
        if delta <= 30:
            return 'due_month'
        return 'ok_far'

    def _valid_email(self, email):
        # Simplified email validation
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or "") is not None

    # Config helpers
    def _load_config(self):
        # Load only non-sensitive preferences (e.g., from_name)
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f) or {}
                if isinstance(data, dict):
                    fn = data.get('from_name') or data.get('fromName')
                    if isinstance(fn, str) and fn.strip():
                        self.gmail_prefs['from_name'] = fn.strip()
        except Exception:
            pass

    def _save_config(self):
        # Persist ONLY non-sensitive preferences
        data = {"from_name": self.gmail_prefs.get('from_name', '3N Licenças')}
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # Menu helpers
    def _open_add_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Adicionar Cliente - 3N")
        dlg.geometry("400x200")
        dlg.grab_set()

        dlg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="Empresa:").grid(row=0, column=0, padx=10, pady=(15, 8), sticky="e")
        empresa_e = ctk.CTkEntry(dlg)
        empresa_e.grid(row=0, column=1, padx=10, pady=(15, 8), sticky="ew")

        ctk.CTkLabel(dlg, text="Vencimento (DD/MM/AAAA):").grid(row=1, column=0, padx=10, pady=8, sticky="e")
        venc_e = ctk.CTkEntry(dlg, placeholder_text="DD/MM/AAAA")
        venc_e.grid(row=1, column=1, padx=10, pady=8, sticky="ew")

        def on_add():
            emp = empresa_e.get().strip()
            ven = venc_e.get().strip()
            if not emp:
                messagebox.showerror("Erro", "Informe o nome da empresa.")
                return
            if ven and not self._valid_date(ven):
                messagebox.showerror("Erro", "Data inválida. Use DD/MM/AAAA.")
                return
            ven_iso = self._to_iso_str(ven) if ven else ""
            self.clients.append({"empresa": emp, "vencimento": ven_iso})
            self._save_clients()
            self.refresh_table()
            dlg.destroy()

        btn_row = ctk.CTkFrame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=15)
        ctk.CTkButton(btn_row, text="Adicionar", width=120, command=on_add).pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(btn_row, text="Cancelar", width=120, command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    def _go_to_remove(self):
        self.show_clients()
        messagebox.showinfo("Remover", "Selecione um cliente e clique em 'Remover selecionado'.")

    def _open_gmail_config(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Configurar Gmail - 3N")
        dlg.geometry("520x360")
        dlg.grab_set()

        for i in range(6):
            dlg.grid_rowconfigure(i, weight=1)
        dlg.grid_columnconfigure(1, weight=1)

        # Read current env as defaults
        env_smtp = os.environ.get('SMTP_EMAIL', '')
        env_owner = os.environ.get('OWNER_EMAIL', '')
        env_from = os.environ.get('FROM_NAME', self.gmail_prefs.get('from_name', '3N Licenças'))
        env_ths = os.environ.get('DAYS_THRESHOLDS', '30,15,5')

        ctk.CTkLabel(dlg, text="Seu Gmail (env ou sessão):").grid(row=0, column=0, padx=10, pady=(15, 6), sticky="e")
        e_email = ctk.CTkEntry(dlg)
        e_email.grid(row=0, column=1, padx=10, pady=(15, 6), sticky="ew")
        e_email.insert(0, env_smtp)

        ctk.CTkLabel(dlg, text="App password (sessão):").grid(row=1, column=0, padx=10, pady=6, sticky="e")
        e_pass = ctk.CTkEntry(dlg, show='*')
        e_pass.grid(row=1, column=1, padx=10, pady=6, sticky="ew")

        ctk.CTkLabel(dlg, text="Nome do remetente (preferência):").grid(row=2, column=0, padx=10, pady=6, sticky="e")
        e_from = ctk.CTkEntry(dlg)
        e_from.grid(row=2, column=1, padx=10, pady=6, sticky="ew")
        e_from.insert(0, env_from)

        ctk.CTkLabel(dlg, text="Dias para alerta (env/sessão, ex: 30,15,5):").grid(row=3, column=0, padx=10, pady=6, sticky="e")
        e_days = ctk.CTkEntry(dlg)
        e_days.grid(row=3, column=1, padx=10, pady=6, sticky="w")
        e_days.insert(0, env_ths)

        ctk.CTkLabel(dlg, text="Enviar para (email do dono):").grid(row=4, column=0, padx=10, pady=6, sticky="e")
        e_owner = ctk.CTkEntry(dlg)
        e_owner.grid(row=4, column=1, padx=10, pady=6, sticky="ew")
        e_owner.insert(0, env_owner or env_smtp)

        info = ctk.CTkLabel(dlg, text="As credenciais não serão salvas em disco.\nPara produção, use variáveis de ambiente (.env/Render).")
        info.grid(row=5, column=0, columnspan=2, padx=10, pady=6)

        def on_save():
            email_val = e_email.get().strip()
            pass_val = e_pass.get().strip()
            from_val = e_from.get().strip() or '3N Licenças'
            raw_days = e_days.get().strip()
            owner_val = e_owner.get().strip() or email_val
            if email_val and not self._valid_email(email_val):
                messagebox.showerror("Configuração", "Email do Gmail inválido.")
                return
            if owner_val and not self._valid_email(owner_val):
                messagebox.showerror("Configuração", "Email do dono inválido.")
                return
            try:
                parts = [p.strip() for p in raw_days.split(',') if p.strip()]
                days_vals = sorted({int(p) for p in parts if int(p) >= 0})
                if not days_vals:
                    raise ValueError
            except Exception:
                messagebox.showerror("Configuração", "Informe dias válidos separados por vírgula, ex: 30,15,5")
                return
            # Save only non-sensitive preference
            self.gmail_prefs['from_name'] = from_val
            self._save_config()
            # Keep sensitive/runtime overrides only in memory
            self.runtime_cfg.update({
                'smtp_email': email_val or None,
                'app_password': pass_val or None,
                'owner_email': owner_val or None,
                'days_thresholds': days_vals or None,
                'from_name': from_val or None,
            })
            messagebox.showinfo("Configuração", "Preferências aplicadas para esta sessão.")
            dlg.destroy()

        btns = ctk.CTkFrame(dlg)
        btns.grid(row=6, column=0, columnspan=2, pady=14)
        ctk.CTkButton(btns, text="Salvar", width=120, command=on_save).pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(btns, text="Cancelar", width=120, command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    def send_notifications(self):
        if not self.clients:
            messagebox.showinfo("Lembretes", "Não há clientes cadastrados.")
            return
        cfg = self._get_env_cfg()
        if not cfg.get('smtp_email'):
            messagebox.showwarning("Lembretes", "Configure seu Gmail primeiro no botão 'Configurar Gmail'.")
            return
        if not cfg.get('app_password'):
            # Se não armazenado, pedir no momento
            dlg = ctk.CTkToplevel(self)
            dlg.title("Senha do App Gmail")
            dlg.geometry("360x140")
            dlg.grab_set()
            ctk.CTkLabel(dlg, text="Digite o App Password do Gmail:").pack(pady=(16,6))
            e = ctk.CTkEntry(dlg, show='*', width=280)
            e.pack(pady=6)
            ok = {'val': False}
            def ok_cmd():
                cfg['app_password'] = e.get().strip()
                ok['val'] = True
                dlg.destroy()
            ctk.CTkButton(dlg, text="OK", width=100, command=ok_cmd).pack(pady=10)
            self.wait_window(dlg)
            if not ok['val'] or not cfg.get('app_password'):
                return

        # Seleciona itens para o resumo (vencidos ou nos dias exatos configurados)
        today = datetime.today().date()
        due_list = []
        ths_set = set(cfg.get('days_thresholds') or [30, 15, 5])
        for c in self.clients:
            d = self._parse_date_any(c.get('vencimento',''))
            if not d:
                continue
            delta = (d - today).days
            if delta < 0 or delta in ths_set:
                due_list.append((c, delta))

        if not due_list:
            messagebox.showinfo("Lembretes", "Nenhum cliente com vencimento próximo.")
            return

        # Confirmação
        if not messagebox.askyesno("Lembretes", "Enviar resumo por e-mail agora?"):
            return

        try:
            context = ssl.create_default_context()
            owner = cfg.get('owner_email') or cfg.get('smtp_email')
            if not owner or not self._valid_email(owner):
                messagebox.showerror("Lembretes", "Email do dono inválido. Configure em 'Configurar Gmail'.")
                return
            subject = "[3N] Resumo de licenças - vencidas e próximas"
            lines = []
            if not due_list:
                lines.append("Nenhuma licença vencida ou próxima do vencimento.")
            else:
                lines.append("Empresas com atenção:")
                for c, delta in sorted(due_list, key=lambda x: x[1]):
                    emp = c.get('empresa','')
                    ven_str = self._format_date_display(c.get('vencimento',''))
                    status_line = 'vencida' if delta < 0 else f'vence em {delta} dia(s)'
                    lines.append(f"- {emp} | {ven_str} | {status_line}")
            body = ("Olá,\n\n" + "\n".join(lines) + "\n\n" + f"Atenciosamente,\n{cfg.get('from_name','3N Licenças')}")

            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
                server.login(cfg['smtp_email'], cfg['app_password'])
                msg = EmailMessage()
                msg['Subject'] = subject
                msg['From'] = f"{cfg.get('from_name','3N Licenças')} <{cfg['smtp_email']}>"
                msg['To'] = owner
                msg.set_content(body)
                server.send_message(msg)
            messagebox.showinfo("Lembretes", "Resumo enviado ao dono com sucesso.")
        except Exception as e:
            messagebox.showerror("Lembretes", f"Falha ao enviar: {e}")

    def _get_env_cfg(self):
        """Build config from environment with optional runtime overrides, no disk writes."""
        smtp_email = os.environ.get('SMTP_EMAIL', '')
        app_password = os.environ.get('SMTP_APP_PASSWORD', '')
        owner_email = os.environ.get('OWNER_EMAIL', '')
        from_name = os.environ.get('FROM_NAME', self.gmail_prefs.get('from_name', '3N Licenças'))
        ths_env = os.environ.get('DAYS_THRESHOLDS', '')
        ths = None
        if ths_env:
            try:
                parts = [p.strip() for p in ths_env.split(',') if p.strip()]
                vals = sorted({int(p) for p in parts if int(p) >= 0})
                if vals:
                    ths = vals
            except Exception:
                ths = None
        if not ths:
            ths = [30, 15, 5]

        # Apply runtime overrides if provided in this session
        rc = self.runtime_cfg
        smtp_email = rc.get('smtp_email') or smtp_email
        app_password = rc.get('app_password') or app_password
        owner_email = rc.get('owner_email') or owner_email
        from_name = rc.get('from_name') or from_name
        ths = rc.get('days_thresholds') or ths

        return {
            'smtp_email': smtp_email,
            'app_password': app_password,
            'owner_email': owner_email,
            'from_name': from_name,
            'days_thresholds': ths,
        }

    def _check_env_warn(self):
        missing = []
        if not (os.environ.get('SMTP_EMAIL') or self.runtime_cfg.get('smtp_email')):
            missing.append('SMTP_EMAIL')
        if not (os.environ.get('OWNER_EMAIL') or self.runtime_cfg.get('owner_email')):
            missing.append('OWNER_EMAIL')
        # Password can be entered on demand; we don't force it here.
        if missing:
            msg = (
                "Algumas variáveis de ambiente não estão definidas:\n- "
                + "\n- ".join(missing)
                + "\n\nVá em 'Configurar Gmail' para definir temporariamente nesta sessão,\n"
                  "ou crie um arquivo .env para uso local."
            )
            try:
                messagebox.showwarning("Ambiente incompleto", msg)
            except Exception:
                pass
    
if __name__ == "__main__":
    app = App()
    app.mainloop()
