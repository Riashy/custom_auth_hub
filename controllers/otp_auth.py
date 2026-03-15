from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request


class CustomOtpAuthController(http.Controller):

    @http.route("/otp/send", type="jsonrpc", auth="public", website=True)
    def otp_send(self, mobile=None, purpose="login", **kwargs):
        try:
            if not mobile:
                return {"ok": False, "message": _("Mobile number is required.")}

            otp = request.env["custom.mobile.otp"].sudo().create_or_refresh_otp(
                mobile=mobile,
                purpose=purpose,
            )

            return {
                "ok": True,
                "message": _("OTP sent successfully."),
                "mobile": otp.mobile,
                "purpose": otp.purpose,
                "debug_code": otp.otp_code if request.env["ir.config_parameter"].sudo().get_param(
                    "custom_auth_hub.otp_disable_sms", default="True"
                ) == "True" else False,
            }
        except ValidationError as e:
            return {"ok": False, "message": e.name}
        except Exception:
            return {"ok": False, "message": _("Unexpected error while sending OTP.")}

    @http.route("/otp/verify", type="jsonrpc", auth="public", website=True)
    def otp_verify(self, mobile=None, code=None, purpose="login", **kwargs):
        try:
            if not mobile or not code:
                return {"ok": False, "message": _("Mobile and code are required.")}

            otp = request.env["custom.mobile.otp"].sudo().verify_mobile_code(
                mobile=mobile,
                code=code,
                purpose=purpose,
            )

            request.session["otp_verified"] = True
            request.session["otp_verified_mobile"] = otp.mobile
            request.session["otp_verified_user_id"] = otp.user_id.id if otp.user_id else False

            return {
                "ok": True,
                "message": _("OTP verified successfully."),
                "redirect_url": "/otp/login/success",
            }
        except ValidationError as e:
            return {"ok": False, "message": e.name}
        except Exception:
            return {"ok": False, "message": _("Unexpected error while verifying OTP.")}

    @http.route("/otp/login/success", type="http", auth="public", website=True)
    def otp_login_success(self, **kwargs):
        verified = request.session.get("otp_verified")
        user_id = request.session.get("otp_verified_user_id")

        if not verified or not user_id:
            return request.redirect("/web/login?otp_error=1")

        values = {
            "otp_mobile": request.session.get("otp_verified_mobile"),
            "otp_user_id": user_id,
        }
        return request.render("custom_auth_hub.otp_login_success_page", values)

    @http.route("/otp/logout-temp", type="http", auth="public", website=True)
    def otp_logout_temp(self, **kwargs):
        request.session.pop("otp_verified", None)
        request.session.pop("otp_verified_mobile", None)
        request.session.pop("otp_verified_user_id", None)
        return request.redirect("/web/login")
