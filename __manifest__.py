{
    "name": "Custom Auth Hub",
    "version": "19.0.1.0.0",
    "summary": "OTP login hub for website and portal",
    "category": "Authentication",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": [
        "base",
        "website",
        "auth_signup",
        "portal",
        "sms",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/auth_login_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "custom_auth_hub/static/src/js/otp.js",
        ],
    },
    "installable": True,
    "application": False,
}
