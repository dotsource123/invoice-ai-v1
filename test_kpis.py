
from pprint import pprint

from kpi_service import (
    get_invoice_summary,
    get_spending_by_vendor,
    get_monthly_trend,
)

print("\n=== INVOICE SUMMARY ===")
pprint(get_invoice_summary())

print("\n=== SPENDING BY VENDOR ===")
pprint(get_spending_by_vendor())

print("\n=== MONTHLY TREND ===")
pprint(get_monthly_trend())
