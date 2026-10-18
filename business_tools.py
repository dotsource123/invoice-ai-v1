"""Read-only business tools used by the dashboard Q&A agent.

All queries are built with SQLAlchemy ORM. No model-generated SQL is executed.
"""
from decimal import Decimal

from sqlalchemy import func, or_

from database import SessionLocal
from models import Invoice, InvoiceItem


def _num(value):
    return float(value) if value is not None else None


def _invoice_dict(row):
    return {
        "invoice_id": row.id,
        "invoice_number": row.invoice_number,
        "date": row.invoice_date.isoformat() if row.invoice_date else None,
        "vendor": row.vendor,
        "type": row.invoice_type,
        "currency": row.currency or "UNKNOWN",
        "subtotal": _num(row.subtotal),
        "tax": _num(row.tax),
        "total": _num(row.total),
        "status": row.status,
    }


def get_invoice_summary():
    """Get confirmed invoice counts and totals, separated by currency and type."""
    db = SessionLocal()
    try:
        rows = (
            db.query(
                Invoice.currency,
                Invoice.invoice_type,
                func.count(Invoice.id).label("invoice_count"),
                func.count(Invoice.total).label("invoices_with_total"),
                func.sum(Invoice.total).label("total_amount"),
            )
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type.in_(["purchase", "sales"]),
            )
            .group_by(Invoice.currency, Invoice.invoice_type)
            .all()
        )
        return {
            "basis": "Confirmed invoices only; currencies are never combined.",
            "groups": [
                {
                    "currency": row.currency or "UNKNOWN",
                    "invoice_type": row.invoice_type,
                    "invoice_count": row.invoice_count,
                    "invoices_with_total": row.invoices_with_total,
                    "invoices_missing_total": row.invoice_count - row.invoices_with_total,
                    "total_amount": _num(row.total_amount),
                }
                for row in rows
            ],
        }
    finally:
        db.close()


def get_vendor_spending(currency=None, limit=10):
    """Get confirmed purchase spending grouped by vendor and currency."""
    limit = max(1, min(int(limit or 10), 20))
    db = SessionLocal()
    try:
        query = (
            db.query(
                Invoice.currency,
                Invoice.vendor,
                func.count(Invoice.id).label("invoice_count"),
                func.count(Invoice.total).label("invoices_with_total"),
                func.sum(Invoice.total).label("total_spent"),
            )
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type == "purchase",
            )
        )
        if currency:
            query = query.filter(func.upper(Invoice.currency) == currency.upper())
        rows = (
            query.group_by(Invoice.currency, Invoice.vendor)
            .order_by(func.sum(Invoice.total).desc())
            .limit(limit)
            .all()
        )
        return {
            "basis": "Confirmed purchase invoices only. Results are separated by currency.",
            "vendors": [
                {
                    "vendor": row.vendor or "Unknown vendor",
                    "currency": row.currency or "UNKNOWN",
                    "invoice_count": row.invoice_count,
                    "invoices_with_total": row.invoices_with_total,
                    "total_spent": _num(row.total_spent),
                }
                for row in rows
            ],
        }
    finally:
        db.close()


def get_monthly_trend(currency=None, limit=24):
    """Get monthly confirmed purchase and sales totals, grouped by currency."""
    limit = max(1, min(int(limit or 24), 36))
    db = SessionLocal()
    try:
        month_expr = func.strftime("%Y-%m", Invoice.invoice_date)
        query = (
            db.query(
                month_expr.label("month"),
                Invoice.currency,
                Invoice.invoice_type,
                func.count(Invoice.id).label("invoice_count"),
                func.count(Invoice.total).label("invoices_with_total"),
                func.sum(Invoice.total).label("total_amount"),
            )
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type.in_(["purchase", "sales"]),
                Invoice.invoice_date.isnot(None),
            )
        )
        if currency:
            query = query.filter(func.upper(Invoice.currency) == currency.upper())
        rows = (
            query.group_by(month_expr, Invoice.currency, Invoice.invoice_type)
            .order_by(month_expr.desc())
            .limit(limit * 2)
            .all()
        )
        results = [
            {
                "month": row.month,
                "currency": row.currency or "UNKNOWN",
                "invoice_type": row.invoice_type,
                "invoice_count": row.invoice_count,
                "invoices_with_total": row.invoices_with_total,
                "total_amount": _num(row.total_amount),
            }
            for row in rows
        ]
        return {
            "basis": "Confirmed invoices with a date; each month, type, and currency is separate.",
            "rows": sorted(results, key=lambda x: (x["month"] or "", x["currency"], x["invoice_type"])),
        }
    finally:
        db.close()


def search_invoices(query, invoice_type=None, limit=10):
    """Search confirmed invoices by vendor, invoice number, or line-item name."""
    query = (query or "").strip()
    if not query:
        return {"matches": [], "note": "A non-empty search query is required."}
    limit = max(1, min(int(limit or 10), 20))
    pattern = f"%{query[:100]}%"
    db = SessionLocal()
    try:
        q = (
            db.query(Invoice)
            .filter(
                Invoice.status == "confirmed",
                or_(
                    Invoice.vendor.ilike(pattern),
                    Invoice.invoice_number.ilike(pattern),
                    Invoice.items.any(InvoiceItem.name.ilike(pattern)),
                ),
            )
        )
        if invoice_type in ("purchase", "sales"):
            q = q.filter(Invoice.invoice_type == invoice_type)
        rows = q.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).limit(limit).all()
        return {
            "matches": [_invoice_dict(row) for row in rows],
            "count_returned": len(rows),
            "note": "Search is limited to confirmed invoices.",
        }
    finally:
        db.close()


def get_top_items(currency=None, limit=10):
    """Get line items with the highest recorded amounts on confirmed purchase invoices."""
    limit = max(1, min(int(limit or 10), 20))
    db = SessionLocal()
    try:
        query = (
            db.query(
                Invoice.currency,
                InvoiceItem.name,
                func.count(InvoiceItem.id).label("line_count"),
                func.sum(InvoiceItem.amount).label("total_amount"),
            )
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type == "purchase",
                InvoiceItem.amount.isnot(None),
            )
        )
        if currency:
            query = query.filter(func.upper(Invoice.currency) == currency.upper())
        rows = (
            query.group_by(Invoice.currency, InvoiceItem.name)
            .order_by(func.sum(InvoiceItem.amount).desc())
            .limit(limit)
            .all()
        )
        return {
            "basis": "Recorded line-item amounts from confirmed purchase invoices; not necessarily inventory cost or profit.",
            "items": [
                {
                    "item": row.name,
                    "currency": row.currency or "UNKNOWN",
                    "line_count": row.line_count,
                    "total_amount": _num(row.total_amount),
                }
                for row in rows
            ],
        }
    finally:
        db.close()
