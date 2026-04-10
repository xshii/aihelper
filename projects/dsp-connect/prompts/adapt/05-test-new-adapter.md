# Step 5: Test the New Adapter

## Role

You are a C developer writing unit tests for a new dsp-connect adapter.
You use the project's existing test framework (macro-based, in `tests/test_helper.h`)
and mock infrastructure (in `tests/mocks/`).

## Task

Write a test file that verifies every vtable function of your new adapter works
correctly. Minimum 5 test cases. The tests must run without real hardware.

## Context

dsp-connect tests use a minimal assert-based framework:
- `TEST(name)` -- declares a test function
- `RUN_TEST(name)` -- runs it and prints PASS/FAIL
- `ASSERT_EQ(a, b)`, `ASSERT_NOT_NULL(p)`, `ASSERT_NULL(p)` -- assertions
- `TEST_SUMMARY()` -- prints totals and returns exit code

Existing test files to study:
- `tests/test_arch.c` -- tests for arch adapters using mock arch objects
- `tests/test_transport_factory.c` -- tests for transport factory using a dummy transport

Existing mocks:
- `tests/mocks/mock_arch.c` / `.h` -- provides `mock_arch_identity()` and `mock_arch_word16()`
- `tests/mocks/mock_transport.c` / `.h` -- provides mock transport for testing

## Steps

### Step 5.1: Decide test strategy

**For arch adapters**, test by creating the real adapter (not a mock) and calling
vtable functions directly. No hardware needed because arch adapters are pure math.

**For transport adapters**, create a mock or use the loopback approach:
- Option A: Write a `mock_<name>_transport` that simulates responses in memory
- Option B: If the transport supports `shm`-like local testing, use that

### Step 5.2: Create the test file

Create `tests/test_<name>.c` with this structure:

```c
/* PURPOSE: Tests for <name> adapter */

#include "test_helper.h"
#include "../src/arch/arch_<name>.h"      /* or transport header */
#include "../src/core/dsc_errors.h"

/* === Test cases === */

TEST(test_case_name)
{
    /* Setup */
    /* Action */
    /* Assert */
}

/* === Runner === */

int test_<name>_main(void)
{
    printf("=== test_<name> ===\n");
    RUN_TEST(test_case_name);
    /* ... */
    TEST_SUMMARY();
}
```

### Step 5.3: Write required test cases for arch adapters

You MUST write at least these tests:

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `<name>_logical_to_physical_basic` | Normal address conversion works |
| 2 | `<name>_physical_to_logical_basic` | Reverse conversion works |
| 3 | `<name>_roundtrip` | `physical_to_logical(logical_to_physical(x)) == x` |
| 4 | `<name>_zero_address` | Address 0 converts correctly |
| 5 | `<name>_alignment_error` | Unaligned address returns `DSC_ERR_MEM_ALIGN` (if applicable) |
| 6 | `<name>_min_access_size` | Returns expected value |
| 7 | `<name>_word_size` | Returns expected value |

Example test body:
```c
TEST(word48_logical_to_physical_basic)
{
    dsc_arch_config_t cfg = { .word_bits = 48, .is_big_endian = 1, .addr_shift = 0 };
    dsc_arch_t *a = dsc_arch_create("word48", &cfg);
    ASSERT_NOT_NULL(a);

    uint64_t phys = 0;
    int rc = dsc_arch_logical_to_physical(a, 0x180, &phys);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(phys, (uint64_t)0x40);  /* 0x180 / 6 = 0x40 */

    dsc_arch_destroy(a);
}
```

### Step 5.4: Write required test cases for transport adapters

You MUST write at least these tests:

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `<name>_create_not_null` | Constructor returns non-NULL |
| 2 | `<name>_create_default_config` | Constructor with NULL cfg uses defaults |
| 3 | `<name>_factory_roundtrip` | Register + create-by-name works |
| 4 | `<name>_close_when_not_open` | Close on un-opened transport does not crash |
| 5 | `<name>_destroy_cleans_up` | Destroy calls close and frees without leak |

If you can test I/O without hardware (e.g. loopback, mock):
| 6 | `<name>_read_basic` | `mem_read` returns expected data |
| 7 | `<name>_write_basic` | `mem_write` succeeds |

### Step 5.5: Register the test runner

Add your test runner to `tests/test_main.c`:

```c
extern int test_<name>_main(void);

/* Inside main(): */
failures += test_<name>_main();
```

Also add the new test `.c` file to the test build in the Makefile.

## Output Format

Produce these files:
1. `tests/test_<name>.c` -- complete test file with 5+ test cases
2. (If needed) `tests/mocks/mock_<name>.c` / `.h` -- mock for transport testing
3. Updated lines in `tests/test_main.c` -- extern declaration + runner call

## Quality Checklist

- [ ] At least 5 test cases per adapter
- [ ] Tests compile and pass with `make test`
- [ ] No test depends on real hardware or network
- [ ] Each test cleans up after itself (destroy/free allocated objects)
- [ ] Test names clearly describe what they verify
- [ ] Roundtrip test exists: `reverse(forward(x)) == x`
- [ ] Edge case test exists: zero address, alignment error, or NULL config
- [ ] New test runner is called from `test_main.c`

## Edge Cases

- If the adapter has **no alignment restriction**, skip the alignment error test
  but add a comment explaining why: `/* No alignment test: <name> accepts any address */`
- If you cannot test transport I/O without hardware, write at least the constructor
  and factory tests. Add a comment: `/* I/O tests require hardware -- skipped */`
- If the adapter registers **multiple names** (e.g. `word48_be` and `word48_le`),
  write tests for each registered name.
- If your test needs **setup/teardown** across tests, use file-scope static variables
  initialized in the first test. The test framework does not have setUp/tearDown hooks.
