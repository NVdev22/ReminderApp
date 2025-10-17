from pathlib import Path
import appScreens

try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent
    env_files = [root / "DadApp.env", root / ".env"]
    for p in env_files:
        if p.exists():
            load_dotenv(dotenv_path=p, override=False)
except Exception:
    pass

app = appScreens.App()
app.mainloop()
