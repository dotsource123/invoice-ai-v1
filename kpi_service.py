
# kpi_service.py

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func

from database import SessionLocal
from models import Invoice


def _to_float(value):
    """Convert SQLAlchemy Decimal values to JSON-friendly floats."""
    return float(value or 0)


def get_invoice_summary():
    """
    Return confirmed invoice summaries, separated by currency.
    Unknown invoice types are excluded.
    """
    db = SessionLocal()

    try:
        rows = (
            db.query(
                Invoice.currency,
                Invoice.invoice_type,
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total), 0).label("total_amount"),
                func.coalesce(func.avg(Invoice.total), 0).label("average_amount"),
            )
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type.in_(["purchase", "sales"]),
            )
            .group_by(Invoice.currency, Invoice.invoice_type)
            .all()
        )

        summary = defaultdict(
            lambda: {
                "currency": None,
                "purchase_total": 0.0,
                "sales_total": 0.0,
                "purchase_invoice_count": 0,
                "sales_invoice_count": 0,
                "average_purchase_value": 0.0,
            }
        )

        for row in rows:
            currency = row.currency or "UNKNOWN"
            entry = summary[currency]
            entry["currency"] = currency

            if row.invoice_type == "purchase":
                entry["purchase_total"] = _to_float(row.total_amount)
                entry["purchase_invoice_count"] = row.invoice_count
                entry["average_purchase_value"] = _to_float(
                    row.average_amount
                )

            elif row.invoice_type == "sales":
                entry["sales_total"] = _to_float(row.total_amount)
                entry["sales_invoice_count"] = row.invoice_count

        return {
            "currencies": list(summary.values()),
            "note": (
                "Purchase totals represent spending recorded on invoices; "
                "sales totals represent recorded sales invoices. "
                "Neither necessarily represents profit."
            ),
        }

    finally:
        db.close()


def get_spending_by_vendor():
    """Return confirmed purchase spending grouped by currency and vendor."""
    db = SessionLocal()

    try:
        rows = (
            db.query(
                Invoice.currency,
                Invoice.vendor,
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total), 0).label("total_spent"),
            )
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type == "purchase",
            )
            .group_by(Invoice.currency, Invoice.vendor)
            .order_by(func.sum(Invoice.total).desc())
            .all()
        )

        return [
            {
                "currency": row.currency or "UNKNOWN",
                "vendor": row.vendor or "Unknown vendor",
                "invoice_count": row.invoice_count,
                "total_spent": _to_float(row.total_spent),
            }
            for row in rows
        ]

    finally:
        db.close()


def get_monthly_trend():
    """
    Return monthly purchase spending and sales totals.
    Results are separated by currency and invoice type.
    """
    db = SessionLocal()

    try:
        rows = (
            db.query(
                func.strftime("%Y-%m", Invoice.invoice_date).label("month"),
                Invoice.currency,
                Invoice.invoice_type,
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total), 0).label("total_amount"),
            )
            .filter(
                Invoice.status == "confirmed",
                Invoice.invoice_type.in_(["purchase", "sales"]),
                Invoice.invoice_date.isnot(None),
            )
            .group_by(
                func.strftime("%Y-%m", Invoice.invoice_date),
                Invoice.currency,
                Invoice.invoice_type,
            )
            .order_by(
                func.strftime("%Y-%m", Invoice.invoice_date).asc()
            )
            .all()
        )

        trends = {}

        for row in rows:
            currency = row.currency or "UNKNOWN"
            month = row.month

            key = (currency, month)

            if key not in trends:
                trends[key] = {
                    "month": month,
                    "currency": currency,
                    "purchase_total": 0.0,
                    "sales_total": 0.0,
                    "purchase_invoice_count": 0,
                    "sales_invoice_count": 0,
                }

            entry = trends[key]

            if row.invoice_type == "purchase":
                entry["purchase_total"] = _to_float(row.total_amount)
                entry["purchase_invoice_count"] = row.invoice_count

            elif row.invoice_type == "sales":
                entry["sales_total"] = _to_float(row.total_amount)
                entry["sales_invoice_count"] = row.invoice_count

        return list(trends.values())

    finally:
        db.close()
