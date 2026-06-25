"""
pdf_report.py — Generates a ShiftIQ PDF report using reportlab.
"""

import os
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from config import APP_NAME, APP_VERSION, PROJECTION_WEEKS
import database as db
import shift_analytics as sa

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN      = colors.HexColor("#2D6A4F")
GREEN_LIGHT= colors.HexColor("#E8F4EE")
RED        = colors.HexColor("#C0392B")
GREY       = colors.HexColor("#888880")
DARK       = colors.HexColor("#1A1A1A")
WHITE      = colors.white


def generate_pdf_report(state, insight_engine, path: str) -> str:
    """
    Generate a PDF financial report for the given state.
    Saves to `path`. Returns the path on success.
    """
    doc    = SimpleDocTemplate(path, pagesize=letter,
                               leftMargin=0.75*inch, rightMargin=0.75*inch,
                               topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story  = []

    # ── Custom styles ──
    title_style = ParagraphStyle("FRETitle",
        fontSize=22, textColor=GREEN, spaceAfter=4, fontName="Helvetica-Bold")
    h1_style = ParagraphStyle("FREH1",
        fontSize=14, textColor=GREEN, spaceBefore=16, spaceAfter=6,
        fontName="Helvetica-Bold")
    h2_style = ParagraphStyle("FREH2",
        fontSize=11, textColor=DARK, spaceBefore=10, spaceAfter=4,
        fontName="Helvetica-Bold")
    body_style = ParagraphStyle("FREBody",
        fontSize=10, textColor=DARK, spaceAfter=4, fontName="Helvetica")
    muted_style = ParagraphStyle("FREMuted",
        fontSize=9, textColor=GREY, spaceAfter=4, fontName="Helvetica")

    def divider():
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#E8E8E4")))
        story.append(Spacer(1, 6))

    def section(title):
        story.append(Paragraph(title, h1_style))
        story.append(HRFlowable(width="100%", thickness=2, color=GREEN))
        story.append(Spacer(1, 6))

    def table(data, col_widths, header=True):
        t = Table(data, colWidths=col_widths)
        style = [
            ("FONTNAME",  (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("BACKGROUND",(0,0), (-1,0),  GREEN),
            ("TEXTCOLOR", (0,0), (-1,0),  WHITE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, GREEN_LIGHT]),
            ("GRID",      (0,0), (-1,-1), 0.5, colors.HexColor("#E8E8E4")),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ] if header else [
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("GRID",      (0,0), (-1,-1), 0.5, colors.HexColor("#E8E8E4")),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, GREEN_LIGHT]),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ]
        t.setStyle(TableStyle(style))
        story.append(t)
        story.append(Spacer(1, 8))

    # ── Cover ──────────────────────────────────────────────────────────────────
    today = datetime.date.today().strftime("%B %d, %Y")
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(APP_NAME, title_style))
    story.append(Paragraph(f"Financial Report  —  {today}  |  v{APP_VERSION}", muted_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=3, color=GREEN))
    story.append(Spacer(1, 0.2*inch))

    # ── Summary ────────────────────────────────────────────────────────────────
    section("Summary")
    risk   = insight_engine.risk_score(state)
    health = insight_engine.financial_health_score(state)
    sr     = state.savings_rate()

    summary_data = [
        ["Metric",           "Value"],
        ["Current Balance",  f"${state.current_balance():,.2f}"],
        ["Weekly Income",    f"${state.total_income_per_week():,.2f}"],
        ["Weekly Expenses",  f"${state.total_expense_per_week():,.2f}"],
        ["Net Weekly Flow",  f"${state.net_weekly_flow():+,.2f}"],
        ["Savings Rate",     f"{sr*100:.1f}%"],
        ["Health Score",     f"{health}/100  —  {insight_engine.health_label(health)}"],
        ["Risk Score",       f"{risk}/100  —  {insight_engine.risk_label(risk)}"],
    ]
    table(summary_data, [2.5*inch, 4.5*inch])

    # ── Insights ───────────────────────────────────────────────────────────────
    section("Insights")
    insights = insight_engine.generate_insights(state)
    for i, txt in enumerate(insights, 1):
        story.append(Paragraph(f"{i}.  {txt}", body_style))
    story.append(Spacer(1, 8))

    # ── Income Sources ─────────────────────────────────────────────────────────
    section("Income Sources")
    if state.jobs:
        job_data = [["Name", "Amount", "Frequency", "Weekly Equiv."]]
        for job in state.jobs:
            job_data.append([
                job.name,
                f"${job.amount:,.2f}",
                job.frequency,
                f"${job.weekly_income():,.2f}",
            ])
        job_data.append([
            "TOTAL", "", "",
            f"${state.total_income_per_week():,.2f}"
        ])
        t = Table(job_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        ts = TableStyle([
            ("FONTNAME",   (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",   (0,0),  (-1,-1), 9),
            ("BACKGROUND", (0,0),  (-1,0),  GREEN),
            ("TEXTCOLOR",  (0,0),  (-1,0),  WHITE),
            ("BACKGROUND", (0,-1), (-1,-1), GREEN_LIGHT),
            ("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [WHITE, GREEN_LIGHT]),
            ("GRID",       (0,0),  (-1,-1), 0.5, colors.HexColor("#E8E8E4")),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ])
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("No income sources on file.", muted_style))

    # ── Expenses ───────────────────────────────────────────────────────────────
    section("Expenses")
    if state.expenses:
        exp_data = [["Name", "Amount", "Frequency", "Category", "Weekly Equiv."]]
        for exp in state.expenses:
            exp_data.append([
                exp.name,
                f"${exp.amount:,.2f}",
                exp.frequency,
                exp.category,
                f"${exp.weekly_amount():,.2f}",
            ])
        exp_data.append([
            "TOTAL", "", "", "",
            f"${state.total_expense_per_week():,.2f}"
        ])
        t = Table(exp_data, colWidths=[1.8*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.3*inch])
        ts = TableStyle([
            ("FONTNAME",   (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",   (0,0),  (-1,-1), 9),
            ("BACKGROUND", (0,0),  (-1,0),  GREEN),
            ("TEXTCOLOR",  (0,0),  (-1,0),  WHITE),
            ("BACKGROUND", (0,-1), (-1,-1), GREEN_LIGHT),
            ("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [WHITE, GREEN_LIGHT]),
            ("GRID",       (0,0),  (-1,-1), 0.5, colors.HexColor("#E8E8E4")),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ])
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("No expenses on file.", muted_style))

    # ── Projections ────────────────────────────────────────────────────────────
    section("Balance Projections")
    proj_data = [["Horizon", "Projected Balance", "vs Today"]]
    current = state.current_balance()
    for wks in PROJECTION_WEEKS:
        projected = state.project_balance(wks)
        diff      = projected - current
        proj_data.append([
            f"{wks} weeks",
            f"${projected:,.2f}",
            f"{'+' if diff >= 0 else ''}{diff:,.2f}",
        ])
    table(proj_data, [2*inch, 2.5*inch, 2.5*inch])

    # ── Schedule Summary ───────────────────────────────────────────────────────
    all_events = db.get_events()
    sched_summary = sa.date_range_summary(all_events)

    if sched_summary.total_hours > 0:
        section("Schedule Summary")

        meta_data = [
            ["Date Range",   f"{sched_summary.start}  →  {sched_summary.end}"],
            ["Total Hours",  f"{sched_summary.total_hours:.1f} hrs"],
            ["Work Days",    str(sched_summary.work_days)],
            ["Total Earned", f"${sched_summary.total_income:,.2f}"],
        ]
        table(meta_data, [2.5*inch, 4.5*inch], header=False)

        # Per-job breakdown
        if sched_summary.job_groups:
            story.append(Paragraph("Income by Job", h2_style))
            job_rows = [["Job", "Hours", "Avg $/hr", "Shifts", "Total Earned"]]
            for group in sched_summary.job_groups.values():
                job_rows.append([
                    group.name,
                    f"{group.total_hours:.1f}",
                    f"${group.avg_rate:.2f}",
                    str(len(group.shifts)),
                    f"${group.total_income:,.2f}",
                ])
            table(job_rows, [2.2*inch, 1.2*inch, 1.2*inch, 1.0*inch, 1.6*inch])

        # Job efficiency
        efficiency = sa.job_efficiency_report(all_events)
        if efficiency:
            story.append(Paragraph("Job Efficiency Ranking", h2_style))
            eff_rows = [["Rank", "Job", "$/hr", "Early Starts", "Late Ends", "Note"]]
            for rank, je in enumerate(efficiency, 1):
                eff_rows.append([
                    f"#{rank}",
                    je.name,
                    f"${je.income_per_hour:.2f}",
                    str(je.early_starts),
                    str(je.late_ends),
                    je.efficiency_note,
                ])
            table(eff_rows, [0.5*inch, 1.5*inch, 0.8*inch, 1.0*inch, 0.8*inch, 2.6*inch])

        # Top earning days
        top_days = sa.top_earning_days(all_events, n=5)
        if top_days:
            story.append(Paragraph("Top Earning Days", h2_style))
            day_rows = [["Date", "Income"]]
            for date_str, amt in top_days:
                day_rows.append([date_str, f"${amt:,.2f}"])
            table(day_rows, [3*inch, 4*inch])

    # ── Footer note ────────────────────────────────────────────────────────────
    divider()
    story.append(Paragraph(
        f"Generated by {APP_NAME} v{APP_VERSION}  —  {today}. "
        "Projections are estimates based on current income and expenses.",
        muted_style
    ))

    doc.build(story)
    return path
