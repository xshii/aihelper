# Adapt Chain -- Add New Architecture or Transport to dsp-connect

## When to Use This Chain

Use this chain when you need to:
- Add support for a **new chip/DSP architecture** (e.g. a 48-bit word DSP, a new endianness mode)
- Add a **new transport protocol** (e.g. JTAG, SPI, TCP socket, USB)
- Add a **new address space mapping** (e.g. banked memory, dual-address-space DSP)

You do NOT need this chain if you are:
- Modifying an existing adapter (just edit the file directly)
- Changing the core library API (that is a different task entirely)
- Adding a new output format (see the `format/` module instead)

## Prerequisites

Before starting, confirm all of these:

1. You have a **working dsp-connect build** -- run `make` and `make test` with zero failures
2. You know the **new target's characteristics**:
   - For arch: word size, endianness, address mapping rules
   - For transport: connection parameters, command protocol, read/write format
3. You have read at least ONE existing adapter of the same type:
   - Arch: `src/arch/arch_byte_addressed.c` or `src/arch/arch_word_addressed.c`
   - Transport: `src/transport/transport_serial.c` or `src/transport/transport_telnet.c`

## What NOT to Change

**NEVER modify these core files:**
- `src/arch/arch.h` -- the vtable interface is stable
- `src/transport/transport.h` -- the vtable interface is stable
- `src/arch/arch_factory.h` -- the factory API is stable
- `src/transport/transport_factory.h` -- the factory API is stable

**You only ADD new files and add registration calls.** The vtable + factory pattern
is designed so that new backends plug in without touching core code.

## Chain Structure

| Step | File | What It Does |
|------|------|--------------|
| 1 | 01-identify-differences.md | Document how new target differs from existing ones |
| 2 | 02-implement-arch-adapter.md | Create new arch_*.c/.h following existing template |
| 3 | 03-implement-transport.md | Create new transport_*.c/.h following existing template |
| 4 | 04-register-in-factory.md | Wire new adapter into the factory system |
| 5 | 05-test-new-adapter.md | Write targeted tests using mock infrastructure |

**Not every step applies every time:**
- Adding only a new arch? Do steps 1, 2, 4, 5. Skip step 3.
- Adding only a new transport? Do steps 1, 3, 4, 5. Skip step 2.
- Adding both? Do all steps in order.

## Standalone Reference

See `adapter-checklist.md` for a complete checklist usable without reading the full chain.

## Expected Output

At the end of this chain you will have:
- One or more new `.c` / `.h` file pairs in `src/arch/` or `src/transport/`
- Updated registration in `arch_factory.c` or auto-registration via macro
- New test file(s) in `tests/` with at least 5 test cases per adapter
- All existing tests still passing (`make test` = zero failures)
