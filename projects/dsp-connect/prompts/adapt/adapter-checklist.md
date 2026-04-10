# Adapter Checklist -- Standalone Reference

Use this checklist when adding a new architecture or transport adapter to dsp-connect.
It is self-contained -- you do not need to read the full prompt chain to use it.

---

## Architecture Adapter Checklist

### Files to Create

- [ ] `src/arch/arch_<name>.c` -- implementation
- [ ] `src/arch/arch_<name>.h` -- header with registration function

### Private Struct

- [ ] `dsc_arch_t base` is the FIRST member of the private struct
- [ ] Struct includes `is_big_endian` and `host_is_big_endian` fields
- [ ] Only fields actually used in vtable functions are present

### Vtable Functions (all six required)

- [ ] `logical_to_physical` -- converts DWARF address to transport address
- [ ] `physical_to_logical` -- exact inverse of `logical_to_physical`
- [ ] `swap_endian` -- no-op when host == target endianness; byte-reversal otherwise
- [ ] `min_access_size` -- returns smallest readable unit in bytes
- [ ] `word_size` -- returns word size in bytes
- [ ] `destroy` -- frees the struct with `free(self)`

### Ops Table

- [ ] All six function pointers assigned (zero NULLs)
- [ ] Ops table is `static const`

### Creator Function

- [ ] Allocates with `calloc(1, sizeof(*a))`
- [ ] Sets `a->base.ops` to the ops table
- [ ] Sets `a->base.name` to a descriptive string (max 31 chars)
- [ ] Handles `cfg == NULL` gracefully (uses defaults)
- [ ] Returns `&a->base` (pointer to the embedded base struct)

### Registration

- [ ] `dsc_arch_<name>_register()` function calls `dsc_arch_register()`
- [ ] `arch_factory.c` includes the new header
- [ ] `dsc_arch_register_builtins()` calls `dsc_arch_<name>_register()`
- [ ] New `.c` file added to Makefile

### Code Quality

- [ ] File starts with `/* PURPOSE: ... PATTERN: ... FOR: ... */` comment
- [ ] No modifications to `arch.h` or `arch_factory.h`
- [ ] All functions under 50 lines
- [ ] `DSC_OK` returned on success; `DSC_ERR_MEM_ALIGN` on alignment errors

---

## Transport Adapter Checklist

### Files to Create

- [ ] `src/transport/transport_<name>.c` -- implementation
- [ ] `src/transport/transport_<name>.h` -- header with constructor declaration

### Private Struct

- [ ] `dsc_transport_t base` is the FIRST member of the private struct
- [ ] Struct includes `timeout_ms` field
- [ ] Struct includes connection state (fd, handle, pointer)
- [ ] Inline cast helper: `to_<name>()` function defined

### Vtable Functions (all six required)

- [ ] `open` -- establishes connection; safe to call if already open (close first)
- [ ] `close` -- tears down connection; safe to call if not open (no crash)
- [ ] `mem_read` -- reads bytes from target; checks connection state first
- [ ] `mem_write` -- writes bytes to target; checks connection state first
- [ ] `exec_cmd` -- sends command string; returns `DSC_ERR_NOT_SUPPORTED` if N/A
- [ ] `destroy` -- calls close, then `free(self)`

### Ops Table

- [ ] All six function pointers assigned (zero NULLs)
- [ ] Ops table is `static const`

### Constructor

- [ ] Signature matches `dsc_transport_t *fn(const dsc_transport_config_t *cfg)`
- [ ] Allocates with `calloc(1, sizeof(*nt))`
- [ ] Sets `nt->base.ops` to the ops table
- [ ] Sets `nt->base.name` to a short identifier
- [ ] Handles `cfg == NULL` gracefully (defaults for all fields)
- [ ] Does NOT call `open` -- connection is a separate step
- [ ] Connection state initialized to "not connected" (e.g. `fd = -1`)

### Registration

- [ ] `DSC_TRANSPORT_REGISTER("<name>", <name>_transport_create)` at bottom of `.c`
- [ ] New `.c` file added to Makefile
- [ ] No changes needed to `transport_factory.c` (auto-registration handles it)

### Code Quality

- [ ] File starts with `/* PURPOSE: ... PATTERN: ... FOR: ... */` comment
- [ ] No modifications to `transport.h` or `transport_factory.h`
- [ ] All functions under 50 lines
- [ ] Error codes use `DSC_ERR_TRANSPORT_*` constants
- [ ] Logging uses `DSC_LOG_*` macros

---

## Test Checklist (applies to both types)

### Files

- [ ] `tests/test_<name>.c` created with 5+ test cases
- [ ] `tests/test_main.c` updated with extern + runner call
- [ ] (If transport) mock file created if needed for I/O tests
- [ ] Test `.c` file added to Makefile

### Required Test Cases

For arch adapters:
- [ ] Normal address conversion (logical -> physical)
- [ ] Reverse address conversion (physical -> logical)
- [ ] Roundtrip: `reverse(forward(x)) == x`
- [ ] Zero address converts correctly
- [ ] Alignment error for unaligned address (if applicable)
- [ ] `min_access_size` returns expected value
- [ ] `word_size` returns expected value

For transport adapters:
- [ ] Constructor returns non-NULL
- [ ] Constructor with NULL config uses defaults
- [ ] Factory create-by-name returns non-NULL
- [ ] Close when not open does not crash
- [ ] Destroy cleans up without leak

### Test Quality

- [ ] No test depends on real hardware or network
- [ ] Each test cleans up (destroy/free)
- [ ] All tests pass with `make test`
- [ ] All pre-existing tests still pass

---

## Final Verification

Run these commands and confirm zero failures:

```bash
make clean && make          # Build succeeds
make test                   # All tests pass
```

If any step fails, fix the issue before proceeding. Do NOT skip failing tests.
