/** @odoo-module **/

async function callJsonRpc(route, params) {
    const response = await fetch(route, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: params || {},
            id: Date.now(),
        }),
        credentials: "same-origin",
    });

    const data = await response.json();
    if (data.error) {
        throw new Error(data.error.message || "RPC Error");
    }
    return data.result;
}

function setStatus(message, type) {
    const box = document.getElementById("otp_status");
    if (!box) return;
    box.className = `alert mt-3 alert-${type}`;
    box.classList.remove("d-none");
    box.textContent = message;
}

function getValue(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : "";
}

function bindOtpButtons() {
    const sendBtn = document.getElementById("btn_send_otp");
    const verifyBtn = document.getElementById("btn_verify_otp");

    if (sendBtn) {
        sendBtn.addEventListener("click", async function () {
            try {
                const mobile = getValue("otp_mobile");
                const result = await callJsonRpc("/otp/send", {
                    mobile: mobile,
                    purpose: "login",
                });

                if (result.ok) {
                    let msg = result.message;
                    if (result.debug_code) {
                        msg += ` Debug OTP: ${result.debug_code}`;
                    }
                    setStatus(msg, "success");
                } else {
                    setStatus(result.message || "Failed to send OTP.", "danger");
                }
            } catch (e) {
                setStatus(e.message || "Failed to send OTP.", "danger");
            }
        });
    }

    if (verifyBtn) {
        verifyBtn.addEventListener("click", async function () {
            try {
                const mobile = getValue("otp_mobile");
                const code = getValue("otp_code");

                const result = await callJsonRpc("/otp/verify", {
                    mobile: mobile,
                    code: code,
                    purpose: "login",
                });

                if (result.ok) {
                    setStatus(result.message || "OTP verified.", "success");
                    if (result.redirect_url) {
                        window.location.href = result.redirect_url;
                    }
                } else {
                    setStatus(result.message || "OTP verification failed.", "danger");
                }
            } catch (e) {
                setStatus(e.message || "OTP verification failed.", "danger");
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", bindOtpButtons);
