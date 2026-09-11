# Acceptance Evidence

This directory contains reproducible, non-secret acceptance evidence for the local PostgreSQL database.

## Evidence index

| File | Script | Acceptance coverage | Verified result |
|---|---|---|---|
| [`04_validate.txt`](04_validate.txt) | `sql/04_validate.sql` | Database identity, current-table totals, snapshot consistency, workshop transformation, metadata and ownership | 120 orders, 360 production rows, 11 workshop-category rows and 223 unique snapshot states; every current order state is present |
| [`05_admin_permission_test.txt`](05_admin_permission_test.txt) | `sql/05_admin_permission_test.sql` | Administrator privileges and reversible CRUD probe | Schema access and table CRUD permissions succeeded for all seven project tables; the disposable probe was rolled back |
| [`06_readonly_permission_test.txt`](06_readonly_permission_test.txt) | `sql/06_readonly_permission_test.sql` | Agent read-only boundary | All four `app` tables are readable; seven explicit denial tests passed; final row counts were unchanged |

These outputs were generated on 10 September 2026 from the current local database after migration to the four-column `app.snapshot` structure. All three `psql` processes returned exit code `0`. The stored files were checked for password variable names and exposed credentials; none were found.

## Acceptance-criterion mapping

1. **Current business data:** `04_validate.txt` confirms 120 `orders`, 360 `production_log` rows and 11 transformed `workshops` rows representing eight physical workshops.
2. **Order-state history:** `04_validate.txt` confirms 223 snapshot rows, 223 distinct (`order_id`, `status`, `stage`, `date`) states, 137 `IN_PROGRESS` states, 86 `COMPLETE` states and zero current order states missing from `snapshot`.
3. **Metadata and ownership:** `04_validate.txt` confirms that the three uploadable data-source counts match their current tables and that all seven project tables are owned by `factory_admin`.
4. **Administrator capabilities:** `05_admin_permission_test.txt` verifies access to both schemas, full table privileges and a reversible create/read/update/delete/truncate/drop probe.
5. **Agent read-only boundary:** `06_readonly_permission_test.txt` verifies `SELECT` on all four `app` tables, denial of `admin_meta` access, denial of write and structural operations, and unchanged final counts.

Field definitions and mappings are documented in [`../docs/field_mapping.md`](../docs/field_mapping.md). Role and operational guidance is documented in [`../docs/database_guide.md`](../docs/database_guide.md).

## Interpreting the permission tests

The administrator test performs CRUD and structural operations on a disposable table inside a transaction and then rolls the transaction back. Its successful command results prove the permissions; the final absence of the probe table confirms that the test left no persistent object.

The read-only test catches only the expected PostgreSQL `insufficient_privilege` exceptions and converts them into explicit `TEST PASSED` notices. If a prohibited operation unexpectedly succeeds, or if another error occurs, the script stops with a non-zero exit status. The final row counts are supporting integrity evidence, not the sole proof of the permission boundary.

## Regenerating the evidence

Run these commands from `postgresql_database` in Windows PowerShell. Enter passwords only at the local prompts; never place them in a command or evidence file.

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

All three exit codes must be `0`. The read-only evidence must contain seven `TEST PASSED` notices, no `TEST FAILED` notice, and final counts consistent with `04_validate.txt`.

The baseline import script `sql/03_import.sql` is not part of routine evidence regeneration. It deliberately clears all four `app` tables and restores the tracked baseline, including the 223-row initial snapshot seed.
