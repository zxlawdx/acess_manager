import base64
import hashlib
import re
from urllib.parse import quote

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)


# =========================================================
# CONTEXTO DA PÁGINA
# =========================================================


def update_page_security(zte, html, source=None):
    """
    Atualiza o contexto de segurança extraído da menuView.

    Fluxo usado pelo firmware:

        menuView
            -> _sessionTmpToken
            -> menuData GET
            -> POST + _sessionTOKEN
            -> Check = RSA(SHA256(body))

    A chave RSA é procurada no próprio HTML/JS da ONT. Isso é importante
    porque a mesma família F6600P já apareceu com chaves diferentes entre
    versões de firmware.
    """

    token = extract_session_tmp_token(
        html
    )

    if token:
        zte.session_tmp_token = token

    public_key = extract_public_key(
        html
    )

    if public_key:
        zte.public_key_pem = public_key

    integrity_check = extract_integrity_check(
        html
    )

    if integrity_check is not None:
        zte.integrity_check = integrity_check

    if (
        token
        or public_key
        or integrity_check is not None
    ):
        zte.security_source = source or getattr(
            zte,
            "security_source",
            None
        )

    return {
        "session_tmp_token": getattr(
            zte,
            "session_tmp_token",
            None
        ),
        "public_key_found": bool(
            getattr(
                zte,
                "public_key_pem",
                None
            )
        ),
        "integrity_check": getattr(
            zte,
            "integrity_check",
            None
        ),
        "source": getattr(
            zte,
            "security_source",
            None
        ),
    }


def extract_session_tmp_token(html):
    padrao_hex = re.search(
        r"_sessionTmpToken\s*=\s*['\"]((?:\\x[0-9a-fA-F]{2})+)['\"]",
        html
    )

    if padrao_hex:
        valores = re.findall(
            r'\\x([0-9a-fA-F]{2})',
            padrao_hex.group(1)
        )

        return bytes(
            int(valor, 16)
            for valor in valores
        ).decode(
            "ascii",
            errors="ignore"
        )

    padrao_normal = re.search(
        r"_sessionTmpToken\s*=\s*['\"]([^'\"]+)['\"]",
        html
    )

    if padrao_normal:
        return padrao_normal.group(1)

    return None


def extract_public_key(html):
    normalizado = (
        html
        .replace("\\r", "")
        .replace("\\n", "\n")
    )

    # Preferimos a chave declarada perto de asyEncode(), que é exatamente a
    # usada no header Check. Não inferimos a chave a partir do certificado
    # HTTPS porque firmwares F6600P já foram observados com chaves diferentes.
    bloco_asy = re.search(
        r'function\s+asyEncode\s*\([^)]*\).*?(?=function\s+|$)',
        normalizado,
        flags=re.DOTALL
    )

    origem = (
        bloco_asy.group(0)
        if bloco_asy
        else normalizado
    )

    padrao = re.search(
        r'-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----',
        origem,
        flags=re.DOTALL
    )

    if not padrao:
        return None

    chave = padrao.group(0).replace(
        '\\"',
        '"'
    )

    linhas = []

    for linha in chave.splitlines():
        linha = linha.strip()

        if linha:
            linhas.append(
                linha
            )

    return "\n".join(
        linhas
    )


def extract_integrity_check(html):
    padroes = [
        r'IntegCheck\s*[:=]\s*(true|false|1|0)',
        r'"IntegCheck"\s*:\s*(true|false|1|0)',
    ]

    for padrao in padroes:
        match = re.search(
            padrao,
            html,
            flags=re.IGNORECASE
        )

        if match:
            return match.group(1).lower() in (
                "true",
                "1"
            )

    return None


# =========================================================
# FORM / CHECK
# =========================================================


def encode_component(valor):
    """
    Equivalente ao encodeURIComponent() usado pelo JavaScript da interface.
    """

    if valor is None:
        valor = ""

    return quote(
        str(valor),
        safe="-_.!~*'()"
    )


def build_form_body(campos):
    partes = []

    for nome, valor in campos:
        partes.append(
            f"{nome}={encode_component(valor)}"
        )

    return "&".join(
        partes
    )


def compute_check_header(
    post_body,
    public_key_pem
):
    digest = hashlib.sha256(
        post_body.encode("utf-8")
    ).hexdigest()

    public_key = (
        serialization
        .load_pem_public_key(
            public_key_pem.encode("utf-8")
        )
    )

    encrypted = public_key.encrypt(
        digest.encode("utf-8"),
        padding.PKCS1v15()
    )

    return base64.b64encode(
        encrypted
    ).decode("ascii")


# =========================================================
# AES DO ZTE
# =========================================================


def aes_decrypt_value(
    ciphertext_b64,
    key_str,
    iv_str
):
    """
    Decodifica campos marcados em <encode> no XML da ONT.

    A interface oficial usa:
        key = SHA256(_sessionTmpToken)
        iv  = SHA256(reverse(_sessionTmpToken))
        AES-CBC + ZeroPadding
    """

    if not ciphertext_b64:
        return ""

    key = hashlib.sha256(
        key_str.encode("utf-8")
    ).digest()

    iv = hashlib.sha256(
        iv_str.encode("utf-8")
    ).digest()[:16]

    try:
        ciphertext = base64.b64decode(
            ciphertext_b64
        )
    except Exception:
        return ciphertext_b64

    try:
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv)
        )

        decryptor = cipher.decryptor()

        plaintext = (
            decryptor.update(ciphertext)
            + decryptor.finalize()
        )

        return (
            plaintext
            .rstrip(b"\x00")
            .decode("utf-8")
        )

    except Exception:
        return ciphertext_b64

# =========================================================
# CRIPTOGRAFIA DE CAMPOS DE CONFIGURAÇÃO
# =========================================================


def rsa_encrypt_text(
    texto,
    public_key_pem
):
    """
    Criptografa um texto curto com a mesma RSA PKCS#1 v1.5 usada por
    asyEncode() no JavaScript da ONT.

    É usada tanto pelo header Check quanto pelo parâmetro encode, que carrega
    a chave/IV temporários dos campos AES.
    """

    if not public_key_pem:
        raise RuntimeError(
            "A chave RSA da ONT ainda não foi carregada."
        )

    public_key = (
        serialization
        .load_pem_public_key(
            public_key_pem.encode("utf-8")
        )
    )

    encrypted = public_key.encrypt(
        str(texto).encode("utf-8"),
        padding.PKCS1v15()
    )

    return base64.b64encode(
        encrypted
    ).decode("ascii")


def aes_encrypt_value(
    plaintext,
    key_str,
    iv_str
):
    """
    Replica encodeParaValue() do firmware:

        key = SHA256(key_str)
        iv  = primeiros 16 bytes de SHA256(iv_str)
        AES-256-CBC + ZeroPadding
        saída em Base64
    """

    if plaintext is None:
        plaintext = ""

    plaintext = str(
        plaintext
    )

    if not plaintext:
        return ""

    key = hashlib.sha256(
        key_str.encode("utf-8")
    ).digest()

    iv = hashlib.sha256(
        iv_str.encode("utf-8")
    ).digest()[:16]

    data = plaintext.encode(
        "utf-8"
    )

    padding_size = (
        16 - (len(data) % 16)
    ) % 16

    data += b"\x00" * padding_size

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv)
    )

    encryptor = cipher.encryptor()

    ciphertext = (
        encryptor.update(data)
        + encryptor.finalize()
    )

    return base64.b64encode(
        ciphertext
    ).decode("ascii")
