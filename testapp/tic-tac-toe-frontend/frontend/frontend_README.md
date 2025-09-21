# Frontend (Create React App) — Run on localhost

This React UI calls the Flask backend running at `http://127.0.0.1:5000`.  
It sends the board as a 9-character string (with spaces encoded as `+`).

## Prerequisites
- Node.js 18+ (includes `npm`)
- The backend is running on `http://127.0.0.1:5000`

---

## 1) Install dependencies
```bash
cd frontend
npm install
```

---

## 2) Start the app
```bash
npm start
```

Open http://localhost:3000 in your browser.

Click a square (you = X). The UI will call:
```
GET http://127.0.0.1:5000/?board=XXXXXXXXX
```
and render the computer’s move (O).

---



