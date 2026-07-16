from io import BytesIO

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from app.pos.services import (
    build_qris_payload,
    category_filters,
    create_transaction,
    current_shift,
    generate_invoice_code,
    list_active_menus,
    normalize_order_code,
    parse_amount,
    payment_details,
    remember_payment,
    transaction_detail,
)
from app.utils.decorators import cashier_required
from app.utils.formatters import format_currency
from app.utils.timezone import jakarta_now


bp = Blueprint("pos", __name__)


@bp.route("/pos")
@cashier_required
def pos():
    products = list_active_menus()
    return render_template(
        "pos.html",
        shift=current_shift(),
        staff_name=session.get("full_name", "Kasir"),
        menu_categories=category_filters(products),
        products=products,
    )


@bp.route("/api/pos/menus")
@cashier_required
def pos_menus_api():
    return jsonify({"success": True, "menus": list_active_menus()})


@bp.route("/pos/payment")
@cashier_required
def pos_payment():
    return render_template("pos_payment.html", shift=current_shift(), staff_name=session.get("full_name", "Kasir"))


@bp.route("/api/pos/checkout", methods=["POST"])
@cashier_required
def pos_checkout():
    data = request.get_json(silent=True) or {}
    try:
        result = create_transaction(data)
        method = "QRIS" if str(data.get("payment_method") or "").lower() == "qris" else "Cash"
        received = result["total_amount"] if method == "QRIS" else parse_amount(data.get("received_amount"), "Nominal diterima")
        change = max(received - result["total_amount"], 0)
        remember_payment(result["order_code"], method, result["total_amount"], received, change)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Penyimpanan transaksi POS gagal.")
        return jsonify({"success": False, "message": "Gagal menyimpan transaksi POS. Silakan coba lagi."}), 500
    return jsonify(
        {
            "success": True,
            "message": f"Transaksi {result['order_code']} berhasil disimpan.",
            "transaction": {
                **result,
                "subtotal_display": format_currency(result["subtotal_amount"]),
                "discount_display": format_currency(result["discount_amount"]),
                "total_display": format_currency(result["total_amount"]),
                "received_amount": received,
                "received_display": format_currency(received),
                "change_amount": change,
                "change_display": format_currency(change),
                "success_url": url_for("pos.payment_success", order_code=result["order_code"]),
                "receipt_url": url_for("pos.pos_receipt", order_code=result["order_code"]),
            },
        }
    )


@bp.route("/api/pos/qris", methods=["POST"])
@cashier_required
def pos_qris_payload():
    data = request.get_json(silent=True) or {}
    try:
        total = parse_amount(data.get("total_amount"), "Total pembayaran")
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    if total <= 0:
        return jsonify({"success": False, "message": "Total pembayaran harus lebih dari Rp 0."}), 400
    timestamp = jakarta_now().replace(microsecond=0).isoformat(timespec="minutes")
    order_code = normalize_order_code(data.get("order_code")) or generate_invoice_code()
    return jsonify(
        {
            "success": True,
            "order_code": order_code,
            "timestamp": timestamp,
            "payload": build_qris_payload(order_code, total, timestamp),
            "qr_url": url_for("pos.pos_qris_code", order_code=order_code, total=total, timestamp=timestamp),
        }
    )


@bp.route("/pos/qris-code/<order_code>.png")
@cashier_required
def pos_qris_code(order_code):
    try:
        import qrcode
    except ImportError:
        return "Paket qrcode belum terpasang.", 503
    try:
        total = parse_amount(request.args.get("total"), "Total pembayaran")
    except ValueError as exc:
        return str(exc), 400
    timestamp = request.args.get("timestamp", jakarta_now().isoformat(timespec="minutes"))
    order_code = normalize_order_code(order_code) or generate_invoice_code()
    qr = qrcode.QRCode(version=None, box_size=12, border=2)
    qr.add_data(build_qris_payload(order_code, total, timestamp))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#3A1E1A", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", download_name=f"{order_code}.png")


@bp.route("/pos/payment/success/<order_code>")
@cashier_required
def payment_success(order_code):
    order_code = normalize_order_code(order_code)
    transaction = transaction_detail(order_code)
    if not transaction:
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("pos.pos"))
    payment = payment_details(order_code, transaction)
    return render_template(
        "payment_success.html",
        transaction=transaction,
        payment=payment,
        total_display=format_currency(transaction.get("total_amount")),
        received_display=format_currency(payment["received_amount"]),
        change_display=format_currency(payment["change_amount"]),
    )


@bp.route("/pos/receipt/<order_code>")
@cashier_required
def pos_receipt(order_code):
    order_code = normalize_order_code(order_code)
    transaction = transaction_detail(order_code)
    if not transaction:
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("pos.pos"))
    payment = payment_details(order_code, transaction)
    return render_template(
        "receipt.html",
        transaction=transaction,
        payment=payment,
        received_display=format_currency(payment["received_amount"]),
        change_display=format_currency(payment["change_amount"]),
    )
