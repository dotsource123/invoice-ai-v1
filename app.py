import os
from datetime import date

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="Invoice AI Dashboard",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.getenv("INVOICE_AI_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 180


def api_get(path):
    response = requests.get(f"{API_BASE}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(path, **kwargs):
    response = requests.post(f"{API_BASE}{path}", timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json()


def fmt_amount(value, currency):
    if value is None or value == "None" or value == "":
        return "Not available"
    try:
        amount = float(value)
        return f"{currency} {amount:,.2f}" if currency != "UNKNOWN" else f"{amount:,.2f} (currency unknown)"
    except (TypeError, ValueError):
        return "Not available"


def safe_float(value):
    if value is None or value == "None" or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


st.title("Invoice AI")
st.caption("Invoice analytics and a Gemma-powered assistant grounded in your saved invoice data.")

with st.sidebar:
    if st.button("↻ Refresh dashboard", use_container_width=True):
        st.rerun()
    st.divider()
    st.subheader("Upload invoice")
    with st.form("invoice_upload_form", clear_on_submit=False):
        invoice_type = st.radio(
            "Invoice type",
            options=["purchase", "sales"],
            format_func=lambda value: "Purchase" if value == "purchase" else "Sales",
            horizontal=True,
            help="Choose whether this invoice records a purchase or a sale. Other fields are extracted automatically.",
        )
        uploaded_file = st.file_uploader(
            "Choose a JPG, PNG, or WebP image",
            type=["jpg", "jpeg", "png", "webp"],
            help="OCR and AI will extract the remaining invoice attributes.",
        )
        upload_clicked = st.form_submit_button(
            "Extract invoice",
            type="primary",
            use_container_width=True,
        )

if upload_clicked:
    if uploaded_file is None:
        st.sidebar.error("Please upload an invoice image.")
    else:
        with st.spinner("Running OCR and extracting invoice fields…"):
            try:
                result = api_post(
                    "/extract-invoice",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type or "application/octet-stream",
                        )
                    },
                    data={"invoice_type": invoice_type},
                )
                # The user's selection is authoritative, not the OCR model's classification.
                extracted_invoice = result.get("invoice")
                st.success(result.get("message", "Invoice processed."))
                with st.expander("Extraction result", expanded=True):
                    st.json(result.get("invoice", result))
            except requests.RequestException as exc:
                detail = "Could not reach the Invoice AI API."
                if getattr(exc, "response", None) is not None:
                    try:
                        detail = exc.response.json().get("detail", str(exc))
                    except ValueError:
                        detail = exc.response.text or str(exc)
                st.error(f"Invoice upload failed: {detail}")

try:
    summary_response = api_get("/dashboard/summary")
    vendor_response = api_get("/dashboard/vendor-spending")
    trend_response = api_get("/dashboard/monthly-trend")
    invoices_response = api_get("/invoices")
except requests.RequestException as exc:
    detail = "Could not reach the FastAPI backend."
    if getattr(exc, "response", None) is not None:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except ValueError:
            detail = exc.response.text or str(exc)
    st.error(f"{detail} Make sure FastAPI is running at {API_BASE}.")
    st.info("In another terminal, run: `uvicorn main:app --reload`")
    st.stop()

currency_summaries = summary_response.get("currencies", [])
currencies = sorted({
    str(item.get("currency") or "UNKNOWN")
    for item in currency_summaries
})
if not currencies:
    currencies = ["UNKNOWN"]

currency = st.selectbox("Currency", currencies, index=0, help="Currency totals are kept separate; different currencies are never added together.")

selected_summary = next(
    (item for item in currency_summaries if (item.get("currency") or "UNKNOWN") == currency),
    {},
)

purchase_total = safe_float(selected_summary.get("purchase_total"))
sales_total = safe_float(selected_summary.get("sales_total"))
purchase_count = int(selected_summary.get("purchase_invoice_count") or 0)
sales_count = int(selected_summary.get("sales_invoice_count") or 0)
avg_purchase = safe_float(selected_summary.get("average_purchase_value"))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Purchase spending", fmt_amount(purchase_total, currency))
c2.metric("Recorded sales", fmt_amount(sales_total, currency))
c3.metric("Purchase invoices", f"{purchase_count:,}")
c4.metric("Average purchase value", fmt_amount(avg_purchase, currency))

st.caption(summary_response.get("note", "Totals are based on confirmed invoices. Missing amounts are not treated as zero."))

trend_rows = [
    row for row in trend_response.get("trends", [])
    if (row.get("currency") or "UNKNOWN") == currency
]
vendor_rows = [
    row for row in vendor_response.get("vendors", [])
    if (row.get("currency") or "UNKNOWN") == currency
]

left, right = st.columns(2)
with left:
    st.subheader("Monthly totals")
    if trend_rows:
        trend_df = pd.DataFrame(trend_rows)
        if "month" in trend_df.columns:
            trend_df = trend_df.sort_values("month")
            chart_df = trend_df.melt(
                id_vars=["month"],
                value_vars=["purchase_total", "sales_total"],
                var_name="invoice_type",
                value_name="amount",
            )
            chart_df["invoice_type"] = chart_df["invoice_type"].map({
                "purchase_total": "Purchase spending",
                "sales_total": "Recorded sales",
            }).fillna(chart_df["invoice_type"])
            fig = px.line(
                chart_df,
                x="month",
                y="amount",
                color="invoice_type",
                markers=True,
                labels={"month": "Month", "amount": f"Amount ({currency})", "invoice_type": "Series"},
            )
            fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No dated invoice trends are available.")
    else:
        st.info("No confirmed, dated invoices found for this currency.")

with right:
    st.subheader("Top vendors by purchase spending")
    if vendor_rows:
        vendor_df = pd.DataFrame(vendor_rows).sort_values("total_spent", ascending=True).tail(10)
        fig = px.bar(
            vendor_df,
            x="total_spent",
            y="vendor",
            orientation="h",
            labels={"total_spent": f"Recorded spending ({currency})", "vendor": "Vendor"},
            hover_data=["invoice_count"],
        )
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No confirmed purchase invoices found for this currency.")

st.divider()
st.subheader("Recent invoices")
invoice_rows = invoices_response.get("invoices", [])
if invoice_rows:
    invoice_df = pd.DataFrame(invoice_rows)
    display_columns = [
        column for column in
        ["id", "invoice_number", "vendor", "invoice_date", "invoice_type", "currency", "total", "status"]
        if column in invoice_df.columns
    ]
    if "currency" in invoice_df.columns:
        invoice_df = invoice_df[invoice_df["currency"].fillna("UNKNOWN").astype(str) == currency]
    st.dataframe(
        invoice_df[display_columns].head(25),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Showing up to 25 most recent invoices for the selected currency. Invoice status is shown as stored.")
else:
    st.info("No invoices are saved yet. Upload an invoice using the form in the sidebar.")

st.divider()
st.subheader("Ask your invoice assistant")
st.write("Ask about confirmed purchase spending, sales totals, vendor rankings, monthly trends, or recorded items.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tools_used"):
            st.caption("Data tools used: " + ", ".join(message["tools_used"]))

question = st.chat_input("e.g. Which vendors account for the highest purchase spending?")
if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Checking invoice data and preparing an explanation…"):
            try:
                answer_result = api_post("/ask-dashboard", json={"question": question})
                answer = answer_result.get("answer", "The assistant returned no answer.")
                st.markdown(answer)
                tools_used = answer_result.get("tools_used", [])
                if tools_used:
                    st.caption("Data tools used: " + ", ".join(tools_used))
                with st.expander("View supporting data"):
                    st.json(answer_result.get("data", []))
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer,
                    "tools_used": tools_used,
                })
            except requests.RequestException as exc:
                detail = "The dashboard assistant could not complete the request."
                if getattr(exc, "response", None) is not None:
                    try:
                        detail = exc.response.json().get("detail", str(exc))
                    except ValueError:
                        detail = exc.response.text or str(exc)
                st.error(detail)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Error: {detail}",
                })
