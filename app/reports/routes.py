from flask import Blueprint, render_template, request, session

from app.reports.services import build_report
from app.utils.decorators import owner_required


bp = Blueprint("reports", __name__)


@bp.route("/owner/reports")
@owner_required
def owner_reports():
    return render_template(
        "owner_financial_reports.html",
        owner_name=session.get("full_name") or "Owner",
        active_page="reports",
        report=build_report(request.args),
    )


@bp.route("/owner/reports/print")
@owner_required
def owner_reports_print():
    return render_template(
        "owner_financial_report_print.html",
        owner_name=session.get("full_name") or "Owner",
        active_page="reports",
        report=build_report(request.args),
    )

