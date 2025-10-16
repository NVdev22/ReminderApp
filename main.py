import appScreens

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = appScreens.App()
app.mainloop()
