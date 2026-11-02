"""Guardrails for the prepared (not executed) Azure DEV deployment files."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(
    encoding="utf-8"
)
BICEP = (ROOT / "deploy" / "azure" / "main.bicep").read_text(encoding="utf-8")
STARTUP = (ROOT / "deploy" / "azure" / "startup.sh").read_text(encoding="utf-8")


def test_deploy_workflow_is_manual_fail_closed_and_secretless():
    triggers = WORKFLOW.split("jobs:")[0]
    assert "workflow_dispatch:" in triggers
    for automatic in ("push:", "pull_request:", "schedule:"):
        assert automatic not in triggers
    assert "vars.AZURE_DEV_DEPLOY_ENABLED == 'true'" in WORKFLOW
    assert "secrets." not in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "environment: dev" in WORKFLOW
    assert "--status success" in WORKFLOW  # requires a green Validation run for the SHA
    assert "self-hosted, linux, x64, vision-dev-deploy" in WORKFLOW
    assert "runs-on: ubuntu-latest" not in WORKFLOW.split("  deploy:")[1]


def test_bicep_denies_access_by_default_and_hardens_the_site():
    assert "param allowedCidrs array" in BICEP
    assert "allowedCidrs array =" not in BICEP  # no default: nothing public by accident
    for setting in (
        "ipSecurityRestrictionsDefaultAction: 'Deny'",
        "scmIpSecurityRestrictionsDefaultAction: 'Deny'",
        "scmIpSecurityRestrictionsUseMain: true",
        "httpsOnly: true",
        "ftpsState: 'Disabled'",
        "minTlsVersion: '1.2'",
        "webSocketsEnabled: true",
        "healthCheckPath: '/_stcore/health'",
    ):
        assert setting in BICEP
    assert "workspaceCapping" in BICEP
    assert "capacity: 1" in BICEP


def test_startup_uses_ephemeral_synthetic_data_only():
    assert "/tmp/co-vision-dev-data" in STARTUP
    assert "tests.e2e.seed" in STARTUP
    assert "unset CO_VISION_PROOF_DB CO_VISION_PROOF_REFERENCE_DB" in STARTUP
    assert "python -m uvicorn vision.asgi_app:app" in STARTUP
    assert "--workers 1" in STARTUP
    assert "streamlit run" not in STARTUP
    assert (
        "/home/" not in STARTUP
    )  # /home is network-backed; SQLite must not live there
    assert "\r" not in STARTUP


def test_seed_entrypoint_shipped_in_the_package_exists():
    for relative in ("tests/__init__.py", "tests/e2e/__init__.py", "tests/e2e/seed.py"):
        assert (ROOT / relative).is_file()
