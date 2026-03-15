import logging
import random
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CustomMobileOtp(models.Model):
    _name = "custom.mobile.otp"
    _description = "Custom Mobile OTP"
    _order = "create_date desc"

    mobile = fields.Char(required=True, index=True)
    otp_code = fields.Char(required=True)
    expiry_time = fields.Datetime(required=True, index=True)
    attempts = fields.Integer(default=0)
    purpose = fields.Selection(
        [
            ("login", "Login"),
            ("signup", "Signup"),
            ("checkout", "Checkout"),
        ],
        required=True,
        default="login",
        index=True,
    )
    verified = fields.Boolean(default=False, index=True)
    user_id = fields.Many2one("res.users", string="User", ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="cascade")
    last_sent_at = fields.Datetime()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("custom_mobile_otp_mobile_check", "CHECK(mobile IS NOT NULL)", "Mobile is required."),
    ]

    @api.model
    def _generate_code(self, length=6):
        return "".join(random.choices("0123456789", k=length))

    @api.model
    def _expiry_minutes(self):
        icp = self.env["ir.config_parameter"].sudo()
        value = icp.get_param("custom_auth_hub.otp_expiry_minutes", default="5")
        try:
            return max(int(value), 1)
        except Exception:
            return 5

    @api.model
    def _max_attempts(self):
        icp = self.env["ir.config_parameter"].sudo()
        value = icp.get_param("custom_auth_hub.otp_max_attempts", default="5")
        try:
            return max(int(value), 1)
        except Exception:
            return 5

    @api.model
    def _resend_cooldown_seconds(self):
        icp = self.env["ir.config_parameter"].sudo()
        value = icp.get_param("custom_auth_hub.otp_resend_cooldown_seconds", default="60")
        try:
            return max(int(value), 0)
        except Exception:
            return 60

    @api.model
    def _normalize_mobile(self, mobile):
        if not mobile:
            return False
        normalized = "".join(ch for ch in mobile if ch.isdigit() or ch == "+")
        return normalized.strip()

    @api.model
    def _find_user_by_mobile(self, mobile):
        mobile = self._normalize_mobile(mobile)
        if not mobile:
            return self.env["res.users"]

        user = self.env["res.users"].sudo().search(
            ["|", ("partner_id.mobile", "=", mobile), ("partner_id.phone", "=", mobile)],
            limit=1,
        )
        return user

    @api.model
    def create_or_refresh_otp(self, mobile, purpose="login"):
        mobile = self._normalize_mobile(mobile)
        if not mobile:
            raise ValidationError(_("Please enter a valid mobile number."))

        user = self._find_user_by_mobile(mobile)
        if purpose == "login" and not user:
            raise ValidationError(_("No user is linked to this mobile number."))

        existing = self.sudo().search(
            [
                ("mobile", "=", mobile),
                ("purpose", "=", purpose),
                ("verified", "=", False),
                ("expiry_time", ">", fields.Datetime.now()),
            ],
            limit=1,
        )

        now = fields.Datetime.now()
        cooldown = self._resend_cooldown_seconds()

        if existing and existing.last_sent_at:
            delta = fields.Datetime.to_datetime(now) - fields.Datetime.to_datetime(existing.last_sent_at)
            if delta.total_seconds() < cooldown:
                remaining = int(cooldown - delta.total_seconds())
                raise ValidationError(
                    _("Please wait %s seconds before requesting another code.") % remaining
                )

        code = self._generate_code()
        expiry = fields.Datetime.to_string(
            fields.Datetime.to_datetime(now) + timedelta(minutes=self._expiry_minutes())
        )

        vals = {
            "mobile": mobile,
            "otp_code": code,
            "expiry_time": expiry,
            "attempts": 0,
            "verified": False,
            "purpose": purpose,
            "last_sent_at": now,
            "user_id": user.id if user else False,
            "partner_id": user.partner_id.id if user else False,
            "active": True,
        }

        if existing:
            existing.sudo().write(vals)
            otp = existing
        else:
            otp = self.sudo().create(vals)

        otp._send_otp_sms()
        return otp

    def _send_otp_sms(self):
        self.ensure_one()

        icp = self.env["ir.config_parameter"].sudo()
        disable_sms = icp.get_param("custom_auth_hub.otp_disable_sms", default="True") == "True"

        if disable_sms:
            _logger.info("OTP SMS disabled. Mobile=%s Code=%s", self.mobile, self.otp_code)
            return True

        # TODO: Replace this placeholder with your SMS provider integration.
        _logger.info("Send OTP SMS placeholder. Mobile=%s Code=%s", self.mobile, self.otp_code)
        return True

    def verify_code(self, code):
        self.ensure_one()

        if self.verified:
            raise ValidationError(_("This code has already been used."))

        if fields.Datetime.to_datetime(self.expiry_time) < fields.Datetime.now():
            raise ValidationError(_("This code has expired."))

        if self.attempts >= self._max_attempts():
            raise ValidationError(_("Maximum attempts reached."))

        self.sudo().write({"attempts": self.attempts + 1})

        if (code or "").strip() != (self.otp_code or "").strip():
            raise ValidationError(_("Invalid OTP code."))

        self.sudo().write({"verified": True})
        return True

    @api.model
    def verify_mobile_code(self, mobile, code, purpose="login"):
        mobile = self._normalize_mobile(mobile)
        otp = self.sudo().search(
            [
                ("mobile", "=", mobile),
                ("purpose", "=", purpose),
                ("verified", "=", False),
                ("expiry_time", ">", fields.Datetime.now()),
                ("active", "=", True),
            ],
            order="create_date desc",
            limit=1,
        )

        if not otp:
            raise ValidationError(_("No active OTP was found for this mobile number."))

        otp.verify_code(code)
        return otp

    @api.model
    def cron_cleanup_expired_otps(self):
        expired = self.sudo().search(
            [
                "|",
                ("expiry_time", "<", fields.Datetime.now()),
                ("active", "=", False),
            ]
        )
        expired.unlink()
        return True
