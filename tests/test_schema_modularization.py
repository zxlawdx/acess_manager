import importlib
import inspect
import unittest
from pathlib import Path

from pydantic import BaseModel, ValidationError

import apps.zte_manager.schemas as legacy_schemas
import apps.zte_manager.presentation.schemas as schemas


EXPECTED_CONTRACTS = {
    "ACSConfigRequest", "ACSParameterRequest", "AdminPasswordRequest",
    "AgentRequest", "AttendanceReportRequest", "AttendantRequest",
    "AutomaticDiagnosticRequest", "BackupCompareRequest",
    "BandSteeringConfigRequest", "BandSteeringRequest",
    "BatchManagementRequest", "BridgeModeRequest", "BufferbloatRequest",
    "CapabilityProbeRequest", "ConnectRequest", "DhcpBasicRequest",
    "DhcpReservationRequest", "DiagnosticRemediationRequest", "DmzRequest",
    "DnsRequest", "DriftRequest", "FilterGlobalManagementRequest",
    "FirewallManagementRequest", "FirewallRuleManagementRequest",
    "FirmwareRegisterRequest", "FirmwareUpgradeRequest",
    "GatewayCommandRequest", "HuaweiCliRequest", "HuaweiFeatureUpdateRequest",
    "HuaweiIPv4FilterDeleteRequest", "HuaweiIPv4FilterRuleRequest",
    "InventorySyncRequest", "InventoryUpdateRequest", "ManagementBackupRequest",
    "ManagementProfileRequest", "MeshConfigRequest", "MeshPairRequest",
    "MonitorStartRequest", "NamedPresetRequest", "NamedPresetSaveRequest",
    "NumericIdRequest", "PingRequest", "PortForwardRequest", "ProfileRequest",
    "QoSManagementRequest", "RadioPowerRequest", "RemoteAccessRequest",
    "ResourceIdRequest", "RestoreBackupRequest", "SNTPManagementRequest",
    "SpeedTestRequest", "SupportDiagnosticRequest", "TR069ManagementRequest",
    "TR069ProviderApplyRequest", "TR069ProviderDeleteRequest",
    "TR069ProviderSaveRequest", "TracerouteRequest", "UpnpRequest",
    "WANActionRequest", "WANCreateRequest", "WANDeleteRequest",
    "WANManagementRequest", "WifiRadioRequest", "WifiSSIDRequest",
    "WifiScheduleRequest", "WpsRequest", "ZeroTouchRequest",
}

DOMAIN_MODULES = (
    "connection",
    "device",
    "wifi",
    "network",
    "diagnostics",
    "profiles",
    "huawei",
    "management",
)


class SchemaModularizationTests(unittest.TestCase):
    def test_legacy_facade_preserves_public_contracts(self):
        self.assertEqual(set(legacy_schemas.__all__), EXPECTED_CONTRACTS)
        self.assertEqual(set(schemas.__all__), EXPECTED_CONTRACTS)

        for name in EXPECTED_CONTRACTS:
            with self.subTest(name=name):
                self.assertIs(getattr(legacy_schemas, name), getattr(schemas, name))
                self.assertTrue(issubclass(getattr(schemas, name), BaseModel))

    def test_legacy_file_is_only_a_compatibility_facade(self):
        source = Path("apps/zte_manager/schemas.py").read_text(encoding="utf-8")
        self.assertNotIn("class ", source)
        self.assertLess(len(source.splitlines()), 20)

    def test_contracts_are_owned_by_domain_modules(self):
        owners = set()
        for short_name in DOMAIN_MODULES:
            module_name = f"apps.zte_manager.presentation.schemas.{short_name}"
            module = importlib.import_module(module_name)
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), 260, short_name)

            for _, value in inspect.getmembers(module, inspect.isclass):
                if value is BaseModel or not issubclass(value, BaseModel):
                    continue
                if value.__module__ == module_name:
                    owners.add(value.__name__)

        self.assertEqual(owners, EXPECTED_CONTRACTS)

    def test_representative_constraints_and_defaults_are_preserved(self):
        with self.assertRaises(ValidationError):
            schemas.WifiScheduleRequest(enabled=True, start_hour=24)
        with self.assertRaises(ValidationError):
            schemas.PortForwardRequest(
                external_port=0,
                internal_client="192.0.2.2",
                internal_port=80,
            )
        with self.assertRaises(ValidationError):
            schemas.AgentRequest(
                name="edge",
                host="192.0.2.10",
                ssh_port=70000,
                ssh_user="tech",
            )
        with self.assertRaises(ValidationError):
            schemas.NamedPresetRequest(attendant="tech", name="")

        self.assertEqual(schemas.PingRequest().count, 4)
        self.assertEqual(schemas.PingRequest().timeout, 5000)
        self.assertEqual(schemas.WifiScheduleRequest(enabled=True).start_hour, 2)
        self.assertEqual(schemas.ACSConfigRequest(base_url="http://acs").timeout, 20)


if __name__ == "__main__":
    unittest.main()
