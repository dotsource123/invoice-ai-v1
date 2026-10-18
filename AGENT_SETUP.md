# Invoice AI: Dashboard Q&A Agent

## What was added

- `POST /ask-dashboard`: a natural-language assistant for questions about saved invoice data.
- `GET /dashboard/summary`: confirmed invoice counts and totals by currency/type.
- `GET /dashboard/vendor-spending`: confirmed purchase spending by vendor.
- `GET /dashboard/monthly-trend`: monthly purchase/sales totals.
- `business_tools.py`: read-only SQLAlchemy queries the assistant is allowed to use.
- `sql_agent.py`: a two-stage agent: Gemma 4 chooses tools, Python executes the allowed read-only tools, and Gemma explains the returned evidence.

## Run locally

1. Create `.env` from `.env.example` and set your Ollama Cloud API key.
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize your local SQLite schema: `python init_db.py`
4. Start the API: `uvicorn main:app --reload`
5. Open `http://127.0.0.1:8000/docs`.

This agent uses the same `OLLAMA_URL`, `OLLAMA_API_KEY`, and `OLLAMA_MODEL` configuration as invoice extraction. The default model is `gemma4:cloud`.

## Ask a question

Request:

```http
POST /ask-dashboard
Content-Type: application/json
```

```json
{
  "question": "Which vendors account for the highest purchase spending?"
}
```

Other example questions:
- "What are my total purchase spending and sales totals?"
- "How has purchase spending changed month by month?"
- "Find invoices from SHIV SHANKAR."
- "Which recorded items have the highest purchase amounts?"
- "Why did purchase spending increase in the latest months?"

Example response shape:

```json
{
  "answer": "Based on the confirmed invoices ...",
  "tools_used": ["vendor_spending"],
  "data": [
    {
      "tool": "vendor_spending",
      "arguments": {"limit": 10},
      "result": {"basis": "...", "vendors": []}
    }
  ]
}
```

Actual answer and data depend on the database. `data` is included so the frontend can optionally display evidence or build source cards.

## Frontend integration

Example browser request:

```javascript
const response = await fetch("http://127.0.0.1:8000/ask-dashboard", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: "Which vendors account for the highest purchase spending?"
  })
});

if (!response.ok) {
  const error = await response.json();
  throw new Error(error.detail || "Dashboard question failed");
}

const result = await response.json();
console.log(result.answer);
```

If your frontend runs on a different origin/port, configure FastAPI CORS for that specific frontend origin before calling this endpoint from the browser.

## Safety and data interpretation

- The model selects from a fixed catalogue of Python functions. It does **not** generate or execute SQL.
- All tools are read-only SQLAlchemy ORM queries; the agent cannot insert, update, delete, or drop database records.
- Results use confirmed invoices and separate currencies. Amounts in different currencies are never combined.
- Purchase spending is not the same as profit; recorded sales totals are not necessarily recognized revenue.
- Missing amounts remain missing and are not treated as zero in the tool outputs.
- The assistant should only explain what the returned data supports. If data is absent or incomplete, it should say so.
- Keep `.env` private. Do not commit API keys or customer invoice data to source control.
