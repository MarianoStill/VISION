param(
    [string]$BaselineReport
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Project interpreter missing. Run: uv sync --locked --all-extras"
}

Push-Location $root
try {
    $ruffTargets = @(
        "apps\vision\src\vision\auth.py",
        "apps\vision\src\vision\authorization.py",
        "apps\vision\src\vision\asgi_app.py",
        "apps\vision\src\vision\development_app.py",
        "apps\vision\src\vision\o2c_workspace.py",
        "apps\vision\src\vision\role_selection.py",
        "apps\vision\src\vision\data_admin.py",
        "scripts\hash_auth_password.py",
        "scripts\regression_compare.py",
        "scripts\check.py",
        "tests\auth\asgi_client.py",
        "tests\auth\test_authorization.py",
        "tests\auth\test_temporary_auth.py",
        "tests\integration\test_asgi_auth.py",
        "tests\integration\test_check_script.py",
        "tests\integration\test_regression_compare.py",
        "tests\vision\test_development_app.py",
        "tests\vision\test_folder_sync.py",
        "tests\e2e\seed.py",
        "tests\e2e\conftest.py",
        "tests\e2e\test_ui_roles.py"
    )
    & $python -m ruff check --select E4,E7,E9,F --extend-ignore E402,E701,E702 @ruffTargets
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed." }
    $requirements = Join-Path $env:TEMP ("vision-audit-" + [guid]::NewGuid().ToString("N") + ".txt")
    & $env:ComSpec /d /c "uv export --locked --all-extras --format requirements-txt --no-emit-project --output-file `"$requirements`" >NUL 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "Could not export locked dependencies for audit." }
    $auditLog = Join-Path $env:TEMP ("vision-audit-" + [guid]::NewGuid().ToString("N") + ".log")
    $auditExe = Join-Path $root ".venv\Scripts\pip-audit.exe"
    & $env:ComSpec /d /c "`"$auditExe`" --strict --requirement `"$requirements`" >`"$auditLog`" 2>&1"
    $auditExitCode = $LASTEXITCODE
    Get-Content $auditLog -Tail 3
    Remove-Item -LiteralPath $requirements,$auditLog -ErrorAction SilentlyContinue
    if ($auditExitCode -ne 0) { throw "Dependency audit failed." }

    & $python scripts\check.py
    if ($LASTEXITCODE -ne 0) { throw "Canonical check failed." }

    & $python -m coverage run --data-file=.coverage -m pytest -q -p no:cacheprovider --junitxml=validation-junit.xml
    if ($LASTEXITCODE -ne 0) { throw "Coverage test run failed." }
    & $python -m coverage report
    if ($LASTEXITCODE -ne 0) { throw "Coverage report failed." }
    & $python -m coverage xml -o coverage.xml
    if ($LASTEXITCODE -ne 0) { throw "Coverage XML generation failed." }

    & $python -m pytest -q -p no:cacheprovider tests\e2e
    if ($LASTEXITCODE -ne 0) { throw "Playwright tests failed." }

    if ($BaselineReport) {
        & $python scripts\regression_compare.py $BaselineReport validation-junit.xml
        if ($LASTEXITCODE -ne 0) { throw "Differential regression comparison failed." }
    }
}
finally {
    Pop-Location
}
