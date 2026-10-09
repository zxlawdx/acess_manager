// Synthetic fixture: structural evidence only, no vendor code copied.
function encodeForLogin(password, token) {
    var b64 = base64encode(password);
    return base64encode(sha256(b64 + __RequestVerificationToken + token));
}
