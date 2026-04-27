# XML Test Fixtures

Legacy XML format fixtures for importer / exporter / round-trip tests.

## valid/

Each `<name>.xml` has a sibling `<name>.expected/` directory containing the
expected YAML import output, **one file per table** (filename = table name,
file content = list of rows; `meta` is a singleton table with 1 row).

| Fixture | Coverage |
|---------|----------|
| `minimal.xml` | Smallest valid input — root attributes + 1 wrapped table with 1 line |
| `multi_runmode.xml` | 2 capacities → 2 distinct runmodes; 2 `<RunModeTbl>` containers; tables referenced from multiple runmodes |
| `empty_table.xml` | `<ResTbl Foo="Foo" LineNum="0"/>` — zero rows; importer must not error |
| `hex_widths.xml` | Hex values with widths 2/4/8 and auto width — round-trip must preserve `0x` prefix and width |

## invalid/

These should fail validation with a clear error message (load-time check).

| File | Expected error |
|------|----------------|
| `dangling_ref.xml` | `RunModeItem` references `NonexistentTbl` which is not defined elsewhere — FK resolution fails |
| `linenum_mismatch.xml` | `<ResTbl LineNum="3">` declares 3 rows but contains only 2 `<Line>` — derived-field consistency check fails |

## Notes for adding new fixtures

- Keep each fixture < 30 lines so failure diagnosis is fast
- One fixture = one feature/bug. Don't bundle.
- Root attribute order must stay consistent across fixtures: `FileName Date XmlConvToolsVersion RatType Version RevisionHistory`
- `RatType=""` (empty string) intentionally retained — empty values are valid per spec
- Every valid fixture must include the `RatVersion` ResTbl (singleton, exactly 1 row) — it is mandatory in legacy XML and the importer should error if missing
