import os
import logging
from flask import render_template, jsonify, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from app.billing import billing_bp
from app.extensions import db, csrf

logger = logging.getLogger(__name__)


def _get_balance(user_id):
    row = db.session.execute(
        db.text("SELECT available_credits FROM user_credit_balance WHERE user_id = :uid"),
        {'uid': user_id}
    ).fetchone()
    return int(row[0]) if row else 0


# ── Saldo ────────────────────────────────────────────────────────────────────

@billing_bp.route('/balance')
@login_required
def balance():
    available = _get_balance(current_user.id)
    return jsonify({'available': available, 'user_id': current_user.id})


# ── Planes ───────────────────────────────────────────────────────────────────

@billing_bp.route('/plans')
@login_required
def plans():
    from app.models import CreditPackage
    packages = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.price_mxn).all()
    available = _get_balance(current_user.id)
    return render_template('billing/plans.html', packages=packages, available=available)


# ── Checkout (crea preferencia MP y redirige) ────────────────────────────────

@billing_bp.route('/checkout/<int:package_id>', methods=['POST'])
@login_required
def checkout(package_id):
    from app.models import CreditPackage, CreditTransaction

    pkg = CreditPackage.query.get_or_404(package_id)
    if float(pkg.price_mxn) == 0:
        flash('El paquete trial es gratuito y ya fue acreditado al registrarte.', 'info')
        return redirect(url_for('billing.plans'))

    mp_token = os.getenv('MP_ACCESS_TOKEN')
    if not mp_token:
        flash('Pagos no configurados. Contacta al administrador.', 'danger')
        return redirect(url_for('billing.plans'))

    try:
        import mercadopago
        sdk = mercadopago.SDK(mp_token)

        # Guardar transacción pendiente antes de redirigir
        txn = CreditTransaction(
            user_id=current_user.id,
            package_id=pkg.id,
            credits=pkg.credits,
            amount_mxn=pkg.price_mxn,
            mp_status='pending',
        )
        db.session.add(txn)
        db.session.flush()  # obtener txn.id para external_reference

        proto = request.headers.get('X-Forwarded-Proto', 'https')
        host = request.headers.get('X-Forwarded-Host', request.host)
        base = f"{proto}://{host}"

        preference_data = {
            "items": [{
                "id": str(pkg.id),
                "title": f"Publicador Zap — {pkg.credits} créditos ({pkg.name})",
                "quantity": 1,
                "currency_id": "MXN",
                "unit_price": float(pkg.price_mxn),
            }],
            "payer": {"email": current_user.email},
            "external_reference": str(txn.id),
            "back_urls": {
                "success": f"{base}{url_for('billing.success')}",
                "failure": f"{base}{url_for('billing.failure')}",
                "pending": f"{base}{url_for('billing.pending')}",
            },
            "auto_return": "approved",
            "notification_url": f"{base}{url_for('billing.webhook')}",
            "statement_descriptor": "PUBLICADORZAP",
        }

        result = sdk.preference().create(preference_data)
        preference = result.get("response", {})

        if result.get("status") not in (200, 201) or "id" not in preference:
            logger.error("MP preference error: %s", result)
            db.session.rollback()
            flash('Error al crear el pago. Intenta de nuevo.', 'danger')
            return redirect(url_for('billing.plans'))

        txn.mp_payment_id = preference["id"]  # preference id (no payment id aún)
        db.session.commit()

        # En sandbox usar sandbox_init_point; en producción usar init_point
        checkout_url = preference.get("sandbox_init_point") if current_app.debug else preference.get("init_point")
        return redirect(checkout_url)

    except Exception as e:
        logger.exception("Checkout error: %s", e)
        db.session.rollback()
        flash('Error inesperado. Intenta de nuevo.', 'danger')
        return redirect(url_for('billing.plans'))


# ── Páginas de retorno ────────────────────────────────────────────────────────

@billing_bp.route('/success')
@login_required
def success():
    payment_id = request.args.get('payment_id')
    status = request.args.get('status')
    external_ref = request.args.get('external_reference')

    # Intentar confirmar inmediatamente si MP pasó el payment_id
    if payment_id and status == 'approved':
        _process_payment(payment_id, external_ref)

    available = _get_balance(current_user.id)
    return render_template('billing/success.html', available=available,
                           payment_id=payment_id, status=status)


@billing_bp.route('/failure')
@login_required
def failure():
    return render_template('billing/failure.html')


@billing_bp.route('/pending')
@login_required
def pending():
    return render_template('billing/pending.html')


# ── Webhook IPN ───────────────────────────────────────────────────────────────

@billing_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    """Recibe notificaciones IPN de Mercado Pago."""
    topic = request.args.get('topic') or request.args.get('type')
    resource_id = request.args.get('id') or request.args.get('data.id')

    # MP envía también JSON body en algunos formatos
    if not resource_id and request.is_json:
        body = request.get_json(silent=True) or {}
        resource_id = (body.get('data') or {}).get('id')
        topic = body.get('type', topic)

    if topic not in ('payment', 'merchant_order') or not resource_id:
        return '', 200  # ignorar notificaciones que no son de pago

    try:
        _process_payment(str(resource_id), external_ref=None)
    except Exception as e:
        logger.exception("Webhook processing error: %s", e)
        return '', 500

    return '', 200


# ── Helper interno de procesamiento de pago ───────────────────────────────────

def _process_payment(payment_id: str, external_ref: str | None):
    """Valida el pago con MP API y acredita créditos si está aprobado."""
    from app.models import CreditTransaction, CreditPackage

    mp_token = os.getenv('MP_ACCESS_TOKEN')
    if not mp_token:
        return

    import mercadopago
    sdk = mercadopago.SDK(mp_token)
    result = sdk.payment().get(payment_id)

    if result.get("status") != 200:
        logger.warning("MP payment fetch failed: %s", result)
        return

    payment = result["response"]
    status = payment.get("status")
    ext_ref = external_ref or str(payment.get("external_reference", ""))

    # Buscar transacción existente por external_reference (txn.id)
    txn = None
    if ext_ref and ext_ref.isdigit():
        txn = CreditTransaction.query.get(int(ext_ref))

    # Fallback: buscar por mp_payment_id
    if txn is None:
        txn = CreditTransaction.query.filter_by(mp_payment_id=payment_id).first()

    if status == 'approved':
        if txn:
            if txn.mp_status == 'approved':
                return  # ya procesado — idempotente
            txn.mp_status = 'approved'
            txn.mp_payment_id = payment_id
        else:
            # Pago aprobado sin transacción previa (edge case): crear una
            payer_email = (payment.get("payer") or {}).get("email")
            from app.models import User
            user = User.query.filter_by(email=payer_email).first() if payer_email else None
            if not user:
                logger.warning("MP approved payment but no user found: %s", payment_id)
                return

            # Intentar identificar el paquete por monto
            amount = float(payment.get("transaction_amount", 0))
            pkg = CreditPackage.query.filter(
                db.cast(CreditPackage.price_mxn, db.Float) == amount,
                CreditPackage.is_active == True
            ).first()
            if not pkg:
                logger.warning("No package matched amount %.2f for payment %s", amount, payment_id)
                return

            txn = CreditTransaction(
                user_id=user.id,
                package_id=pkg.id,
                credits=pkg.credits,
                amount_mxn=amount,
                mp_payment_id=payment_id,
                mp_status='approved',
            )
            db.session.add(txn)

        db.session.commit()
        logger.info("Credits approved: txn=%s payment=%s", txn.id if txn else '?', payment_id)

    elif status in ('rejected', 'cancelled'):
        if txn and txn.mp_status == 'pending':
            txn.mp_status = status
            db.session.commit()
