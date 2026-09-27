# F6600P DHCP + multi-provider TR-069 + technician configuration variants

## Problem confirmed in source (device capture needs follow-up)

The F6600P snapshot shows Base64-shaped AES strings where DHCP pool IPv4
addresses should be. The old `zte_network_management.dhcp_status()`
parsed the ThinkLua XML instances and directly returned `MinAddress` and
`MaxAddress` without inspecting the firmware's `<encode>` declarations
or using the authenticated `_sessionTmpToken`. **It was showing encrypted
wire values directly in address text boxes, not encrypted client IP
leases.** A successful menuData HTTP 200 does not assert XML semantics.

The fix decodes only fields that the firmware marks in `<encode>` or
whose Base64 block can be AES-decrypted to a *valid IPv4 address* with the
existing authenticated session token. The correct ZTE cipher is
AES-256-CBC, with key SHA256(sessionTmpToken) and IV derived from the
reversed token (existing `zte_security.aes_decrypt_value`).

Decoded fields are displayed; unconfirmed protected fields are replaced
with an empty string and a clear warning and **writing is disabled**,
instead of accidentally POSTing ciphertext or fake IPs. Confirmed
protected DHCP fields use fresh random AES key+IV with RSA key-wrap on
POST, following the existing ZTE WAN/TR-069 pattern; firmware
post-operation reread still decides verification. The `/network/dhcp`
legacy response keys (`basic`, `lan_dns`, `leases`,
`reservations`) remain unchanged; additional metadata is
`dhcp_encoded_fields`, `write_safe`, and `warnings`.

Separately, the legacy HTML had **duplicate DOM IDs** across WAN/DHCP
and Advanced: `dhcpEnabled`, `dhcpDns1`, `dhcpDns2`. Under
`document.getElementById`, the Advanced screen could read the hidden
other form's checkbox and DNS textboxes. Advanced now uses distinct
`advancedDhcpEnabled`, `advancedDhcpDns1`,
`advancedDhcpDns2`; the original DHCP module retains the old IDs.

## New "Gestão TR-069" page

- `tr069_profile_service.py` stores **only non-secret** ACS profile
  metadata in the user's local `data_dir()/tr069_providers.json`.
  The built-in *Brasil Digital* template includes the non-secret
  administrative and connection-request username defaults and 1200-second
  periodic inform; operator may choose legacy 300 seconds.
  **Its ACS URL must be configured locally by the operator**, avoiding
  publication of company-specific infrastructure in the source tree.
- Two password inputs are intentionally **session-only**, never stored
  in provider JSON or browser localStorage. Empty fields instruct the
  driver to preserve the current passwords, per its pre-existing
  `None` sentinel protocol. Fill both when first provisioning a new ONT.
- `GET /api/tr069/setup` returns a **safe allowlisted status** and
  eligible existing WANs with BOTH PPP and a TR069 service tag.
  If none is found, the Apply button is disabled and instructs the
  operator to configure the contract WAN via the existing management
  screen. This workflow will **never create a new WAN implicitly**.
- `POST /api/tr069/providers/apply` re-reads the actual WAN list under
  the `ZTEService` single-session lock, requires explicit confirm and
  reuses the existing audited `zte.set_tr069_management`. Existing
  `/management/tr069` and `/management/tr069/update` are untouched.

## Multiple standard configurations

The *Configuração padrão* page now has a small **Configurações salvas do
atendente** selector with Create, Save, Apply and Delete. The original
one-preset-per-technician route and `attendant_profiles.json` remain
the immutable **Configuração principal** alias; extra configurations
live separately in `named_attendant_profiles.json` via
`named_preset_service.py`. This supports variants per client segment
without conflating technician preferences or provider ACS secrets.
Named apply uses the same audited single ONT session and the existing
Wi-Fi/DNS composite command, and never invokes the generic batch on
the separately captured F6201B protocol.

Routes: `POST /profiles/named/{list,get,save,delete,apply}`, preserving
all legacy JSON envelopes. The frontend isolates its new named-preset
controller while keeping the classic radio/DNS form.

## Tests and physical verification

```shell
python -m unittest tests.test_f6600p_dhcp_encoded tests.test_tr069_named_presets -v
node tests/test_tr069_preset_ui.cjs
python -m unittest discover -s tests -v
```

**Tests are synthetic**. Before production merge, repeat the DHCP GET
on the real F6600P V9.0.10P6N34 and compare decoded `MinAddress`
and `MaxAddress` to the ONT's official page. Then test an authorized,
non-disruptive DHCP write in a maintenance window and ensure real POST
encryption/verification agrees with that firmware. Select an *existing*
PPPoE/TR069 contract WAN and confirm the ACS URL/periodic interval in
the ZTE web panel after Apply. Finally verify an ACS session from the
authorized ACS control panel. A router HTTP 200 alone does not prove
CWMP connectivity to the ACS.

Do not paste, commit, screenshot or post real ACS/router passwords,
session tokens or connection-request URLs to public issue reports.
