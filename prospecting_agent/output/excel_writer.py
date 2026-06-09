import os
from datetime import datetime
from typing import List

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
from openpyxl.utils import get_column_letter

import config
from models.lead import Lead
from utils.logger import get_logger

log = get_logger("excel_writer")

PUROLATOR_PURPLE = "4B0082"
PUROLATOR_LIGHT = "F0E6FF"
GREEN_FILL = "C6EFCE"
YELLOW_FILL = "FFEB9C"
RED_FILL = "FFC7CE"

COLUMNS = [
    ("Company Name", 28),
    ("Industry", 22),
    ("Website", 28),
    ("Employees", 11),
    ("City", 16),
    ("Province", 10),
    ("Decision Maker", 22),
    ("Title", 26),
    ("Email", 30),
    ("Phone", 16),
    ("LinkedIn Sales Nav", 20),
    ("Lead Type", 14),
    ("Carrier (Est.)", 14),
    ("3PL Risk", 10),
    ("Score", 8),
    ("Est. Spend ($/yr)", 16),
    ("Talking Points", 60),
    ("Date", 12),
    ("Email Verified", 14),
]


def _header_style() -> dict:
    return {
        "font": Font(name="Calibri", bold=True, color="FFFFFF", size=11),
        "fill": PatternFill(fill_type="solid", fgColor=PUROLATOR_PURPLE),
        "alignment": Alignment(horizontal="center", vertical="center", wrap_text=True),
    }


def _apply_header(ws) -> None:
    header_s = _header_style()
    for col_idx, (col_name, col_width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_s["font"]
        cell.fill = header_s["fill"]
        cell.alignment = header_s["alignment"]
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws.row_dimensions[1].height = 30


def _score_cell_color(score: int) -> str:
    if score >= 8:
        return GREEN_FILL
    if score >= 5:
        return YELLOW_FILL
    return RED_FILL


def _write_lead_row(ws, row_idx: int, lead: Lead) -> None:
    def cell(col, value, hyperlink=None, wrap=False):
        c = ws.cell(row=row_idx, column=col, value=value)
        c.alignment = Alignment(vertical="center", wrap_text=wrap)
        if hyperlink:
            c.hyperlink = hyperlink
            c.font = Font(color="0563C1", underline="single")
        return c

    cell(1, lead.company_name)
    cell(2, lead.industry)
    cell(3, lead.website or "", hyperlink=lead.website if lead.website else None)
    cell(4, lead.employee_count)
    cell(5, lead.city)
    cell(6, lead.province)
    cell(7, lead.full_name if lead.full_name.strip() else "—")
    cell(8, lead.title)
    cell(9, lead.email or "", hyperlink=f"mailto:{lead.email}" if lead.email else None)
    cell(10, lead.phone)
    cell(11, "Find Decision Maker →" if not lead.full_name.strip() else "Open Sales Nav",
         hyperlink=lead.sales_nav_url if lead.sales_nav_url else None)
    cell(12, lead.lead_type)
    cell(13, lead.current_carrier_estimated)
    cell(14, "⚠ YES" if lead.three_pl_risk else "")
    score_cell = cell(15, lead.shipping_score)
    score_fill = _score_cell_color(lead.shipping_score)
    score_cell.fill = PatternFill(fill_type="solid", fgColor=score_fill)
    score_cell.alignment = Alignment(horizontal="center", vertical="center")
    spend_cell = cell(16, lead.est_annual_shipping_spend or None)
    spend_cell.number_format = "$#,##0"
    spend_cell.alignment = Alignment(horizontal="right", vertical="center")
    cell(17, lead.talking_points, wrap=True)
    cell(18, lead.date_generated)
    cell(19, "Yes" if lead.email_verified else "No")

    ws.row_dimensions[row_idx].height = 60 if lead.talking_points else 20


def _write_summary_sheet(wb, leads: List[Lead], run_start: datetime, sector_names: List[str]) -> None:
    ws = wb.create_sheet("Run Summary")
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 20

    rows = [
        ("Run Date", run_start.strftime("%Y-%m-%d %H:%M")),
        ("Total Leads", len(leads)),
        ("Sectors", ", ".join(sector_names)),
        ("", ""),
        ("Avg Est. Spend ($/yr)",
         f"${sum(l.est_annual_shipping_spend for l in leads) // max(1, sum(1 for l in leads if l.est_annual_shipping_spend)):,}"
         if any(l.est_annual_shipping_spend for l in leads) else "n/a"),
        ("", ""),
        ("Score Breakdown", ""),
        ("High (8-10)", sum(1 for l in leads if l.shipping_score >= 8)),
        ("Medium (5-7)", sum(1 for l in leads if 5 <= l.shipping_score < 8)),
        ("Low (1-4)", sum(1 for l in leads if l.shipping_score < 5)),
        ("", ""),
        ("Lead Types", ""),
        ("New", sum(1 for l in leads if l.lead_type == "NEW")),
        ("Reactivation", sum(1 for l in leads if l.lead_type == "REACTIVATION")),
        ("", ""),
        ("Carrier Targeting", ""),
        ("FedEx Prospects", sum(1 for l in leads if "fedex" in l.current_carrier_estimated.lower())),
        ("UPS Prospects", sum(1 for l in leads if "ups" in l.current_carrier_estimated.lower())),
        ("3PL Risk Flagged", sum(1 for l in leads if l.three_pl_risk)),
        ("", ""),
        ("Top 10 by Score", ""),
    ]

    for r_idx, (label, value) in enumerate(rows, start=1):
        ws.cell(row=r_idx, column=1, value=label).font = Font(bold=True) if label and not value == "" else Font()
        ws.cell(row=r_idx, column=2, value=value)

    top10 = sorted(leads, key=lambda l: l.shipping_score, reverse=True)[:10]
    start_row = len(rows) + 1
    for i, lead in enumerate(top10):
        ws.cell(row=start_row + i, column=1, value=lead.company_name)
        ws.cell(row=start_row + i, column=2, value=lead.shipping_score)


def write_excel(leads: List[Lead], sector_names: List[str]) -> str:
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    now = datetime.now()
    sector_code = "_".join(s[:3].upper() for s in sector_names)
    filename = f"purolator_leads_{sector_code}_{now.strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = os.path.join(config.REPORTS_DIR, filename)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}1"

    _apply_header(ws)

    for row_idx, lead in enumerate(leads, start=2):
        _write_lead_row(ws, row_idx, lead)

    _write_summary_sheet(wb, leads, now, sector_names)

    wb.save(filepath)
    log.info("Excel saved: %s (%d leads)", filepath, len(leads))
    return filepath
