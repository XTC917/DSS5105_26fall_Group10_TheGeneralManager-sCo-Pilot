# Acceptance Evidence

This folder is reserved for non-secret acceptance evidence prepared by the team.

## Evidence index

| File | Script | Acceptance coverage | Verified result |
|---|---|---|---|
| [`04_validate.txt`](04_validate.txt) | `sql/04_validate.sql` | Database identity, imported-data validation, field identifiers, totals and ownership | 120 orders, 360 production rows, 8 workshops; all tables owned by `factory_admin` |
| [`05_admin_permission_test.txt`](05_admin_permission_test.txt) | `sql/05_admin_permission_test.sql` | Administrator account and privileges | Connect, schema use/create, table CRUD, truncate and disposable-table create/drop all succeeded |
| [`06_readonly_permission_test.txt`](06_readonly_permission_test.txt) | `sql/06_readonly_permission_test.sql` | Agent read-only role | SELECT succeeded; six dangerous operations produced explicit permission-denial PASS results; final row counts were unchanged |

These outputs were generated on 4 September 2026 from the current locally reproduced database. Password prompts did not echo passwords, and the stored files have been checked for exposed credentials.

## Acceptance-criterion mapping

1. **Database, import and mapping:** `04_validate.txt` confirms the database identity, imported row counts, uniqueness, totals and table ownership. Field and PostgreSQL type mappings are documented in [`../docs/field_mapping.md`](../docs/field_mapping.md).
2. **Administrator and Agent roles:** `05_admin_permission_test.txt` proves administrator capabilities. `06_readonly_permission_test.txt` proves that `factory_agent` can read but cannot perform dangerous write or structure operations.
3. **Administrator and ordinary-user boundary:** [`../docs/database_guide.md`](../docs/database_guide.md) records the agreed boundary. `factory_admin` has full maintenance permissions, while `factory_user` inherits the shared read-only `factory_reader` role.

## Interpreting the read-only permission test

`06_readonly_permission_test.sql` catches the expected PostgreSQL `insufficient_privilege` exceptions and converts them into explicit `TEST PASSED` messages.

If a dangerous operation unexpectedly succeeds, the script raises `TEST FAILED` and stops with a non-zero exit status. Other errors, such as syntax errors, missing tables or invalid test data, are not treated as successful permission results.

The final integrity query confirms that the test left no persistent changes. Unchanged row counts are supporting safety evidence, not the sole proof of read-only permissions.

## Regenerating the evidence

Run the following commands from the PostgreSQL prototype directory (`postgresql_database/`), not from the team repository root, in Windows PowerShell. Each command captures the complete `psql` output, records the exit status immediately and writes reviewable UTF-8 text. Enter passwords only at the local password prompts; never place them in a command or evidence file.

### Database and import validation

```powershell
$validateOutput = cmd /d /c 'psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/04_validate.sql" 2>&1'
$validateExitCode = $LASTEXITCODE
$validateText = (($validateOutput | ForEach-Object { $_.TrimEnd() }) -join [Environment]::NewLine).TrimEnd()
$validateText | Set-Content -Path "evidence/04_validate.txt" -Encoding UTF8
$validateOutput
Write-Host "04_validate exit code: $validateExitCode"
```

### Administrator permission validation

```powershell
$adminOutput = cmd /d /c 'psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/05_admin_permission_test.sql" 2>&1'
$adminExitCode = $LASTEXITCODE
$adminText = (($adminOutput | ForEach-Object { $_.TrimEnd() }) -join [Environment]::NewLine).TrimEnd()
$adminText | Set-Content -Path "evidence/05_admin_permission_test.txt" -Encoding UTF8
$adminOutput
Write-Host "05_admin_permission_test exit code: $adminExitCode"
```

### Read-only Agent validation

```powershell
$readonlyOutput = cmd /d /c 'psql -X -h localhost -p 5432 -U factory_agent -d factory_copilot_db -W -f "sql/06_readonly_permission_test.sql" 2>&1'
$readonlyExitCode = $LASTEXITCODE
$readonlyText = (($readonlyOutput | ForEach-Object { $_.TrimEnd() }) -join [Environment]::NewLine).TrimEnd()
$readonlyText | Set-Content -Path "evidence/06_readonly_permission_test.txt" -Encoding UTF8
$readonlyOutput
Write-Host "06_readonly_permission_test exit code: $readonlyExitCode"
```

All three exit codes must be `0`. The read-only evidence must contain six `TEST PASSED` messages, no `TEST FAILED` message, and final row counts matching `04_validate.txt`.

## Additional evidence guidance

Suggested evidence:

- database, schema and table creation results;
- CSV import and validation results from `04_validate.sql`;
- administrator permission results from `05_admin_permission_test.sql`;
- Agent read-only permission results from `06_readonly_permission_test.sql`;
- an evidence index that maps each file to the corresponding acceptance criterion.

Terminal outputs may be stored as text files, and screenshots may be included when useful. Do not include passwords, connection secrets or private environment files.
