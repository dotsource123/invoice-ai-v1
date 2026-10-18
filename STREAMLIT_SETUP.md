# Invoice AI — Streamlit dashboard setup

This folder includes the existing FastAPI + Ollama Cloud agent backend and a Streamlit dashboard (`app.py`).

## Preserve your existing local files

The ZIP intentionally excludes `.env` and `invoices.db` because they can contain API credentials and private invoice data. When integrating into your existing project folder, keep your existing copies of both files. Do not replace your database with a new empty database if you want to preserve invoices.

## 1. Install dependencies

Open PowerShell in this project folder and activate your existing virtual environment, if you use one. Then run:

```powershell
pip install -r requirements.txt
```

This project includes PaddleOCR dependencies, so installing all requirements can take a while. If those are already installed, you can install only the dashboard additions:

```powershell
pip install streamlit plotly pandas
```

## 2. Configure Ollama Cloud

Make sure your local `.env` has your existing key and model configuration:

```dotenv
OLLAMA_API_KEY=your_actual_key
OLLAMA_URL=https://ollama.com/api/chat
OLLAMA_MODEL=gemma4:cloud
```

Do not commit `.env` to Git.

## 3. Start FastAPI

In terminal 1, from this folder:

```powershell
uvicorn main:app --reload
```

Check `http://127.0.0.1:8000/docs`.

## 4. Start Streamlit

In terminal 2, from the same folder:

```powershell
streamlit run app.py
```

Open the local URL Streamlit prints, usually `http://localhost:8501`.

If the backend runs at a different URL, set `INVOICE_AI_API_URL` before starting Streamlit, for example:

```powershell
$env:INVOICE_AI_API_URL="http://127.0.0.1:8000"
streamlit run app.py
```

## What the UI uses

- `GET /dashboard/summary` — KPIs grouped by currency
- `GET /dashboard/vendor-spending` — top vendors chart
- `GET /dashboard/monthly-trend` — monthly chart
- `GET /invoices` — recent invoices
- `POST /extract-invoice` — upload and process an invoice with the existing OCR flow
- `POST /ask-dashboard` — ask the agent a question about saved invoice data

The Streamlit frontend makes server-side HTTP requests, so browser CORS configuration is not needed for this setup.

## Notes

- Analytics endpoints are based on the current backend logic; summary/vendor/trend tools may use confirmed invoices only.
- Currency totals are kept separate.
- The app is a local development prototype. Test with known invoices and do not expose it publicly without authentication and suitable security controls.
