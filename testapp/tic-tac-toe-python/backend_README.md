# Backend (Flask) — Run on localhost

This server exposes a GET endpoint that accepts a 9-character board string (spaces allowed) and returns the updated 9-character board after the computer's move.

## Prerequisites
- Python 3.9+ installed
- Pip installed (bundled with Python)

> Tip (Mac): confirm versions  
> `python3 --version` • `pip3 --version`

---

## 1) Create and activate a virtual environment

### macOS / Linux
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your terminal prompt.

---

## 2) Install dependencies
pip install -r requirements.txt




## 3) Run the server on localhost

### Easiest
```bash
python app.py
```

By default it listens on `http://127.0.0.1:5000`.

### (Optional) Dual-stack (IPv6 + IPv4) with Flask CLI
```bash
# macOS/Linux
export FLASK_APP=app.py && flask run --host="::" --port=5000
# Windows PowerShell
$env:FLASK_APP="app.py"; flask run --host="::" --port=5000
```

---

## 4) Sanity check (from a terminal)

> Exactly **9 chars** are required. Your server accepts `+` as spaces.

```bash
# X then 8 spaces (using + for spaces)
curl "http://127.0.0.1:5000/?board=X++++++++"
```

You should get back 9 characters (e.g., `XO+++++++`).

---

## 5) Stop the server
Press `Ctrl + C` in the terminal running the server.

