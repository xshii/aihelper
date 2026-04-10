# Step 4: Register the New Adapter in the Factory

## Role

You are a C developer wiring a new adapter into the dsp-connect build and factory
system. This is a small but critical step -- miss one line and the adapter is invisible.

## Task

Update the factory registration so that users can create your new adapter by name
(e.g. `dsc_arch_create("word48", &cfg)` or `dsc_transport_create("jtag", &cfg)`).

## Context

dsp-connect has two factory systems:

**Architecture factory** (`src/arch/arch_factory.c`):
- Uses a manual registration function `dsc_arch_register_builtins()`
- Each backend's `.h` declares a `void dsc_arch_<name>_register(void)` function
- You must add a call to this function inside `dsc_arch_register_builtins()`

**Transport factory** (`src/transport/transport_factory.c`):
- Uses auto-registration via `DSC_TRANSPORT_REGISTER()` macro
- The macro uses `__attribute__((constructor))` -- no manual wiring needed
- You only need to ensure the `.c` file is compiled (added to Makefile)

## Steps

### For a New Arch Adapter

1. **Add the include** in `src/arch/arch_factory.c`:
   ```c
   #include "arch_<name>.h"
   ```

2. **Add the registration call** inside `dsc_arch_register_builtins()`:
   ```c
   void dsc_arch_register_builtins(void)
   {
       dsc_arch_byte_register();
       dsc_arch_word_register();
       dsc_arch_<name>_register();   /* <-- ADD THIS LINE */
   }
   ```

3. **Add the source file to the Makefile**. Find the `ARCH_SRCS` or equivalent
   variable and append your new `.c` file.

### For a New Transport Adapter

1. **Verify** that your `.c` file ends with the `DSC_TRANSPORT_REGISTER` macro call.
   If it does, no changes to `transport_factory.c` are needed.

2. **Add the source file to the Makefile**. Find the `TRANSPORT_SRCS` or equivalent
   variable and append your new `.c` file.

### Update the Makefile

Open the project `Makefile` and add your new source file(s) to the appropriate
source list. Look for patterns like:

```makefile
SRCS = src/arch/arch_byte_addressed.c \
       src/arch/arch_word_addressed.c \
       src/arch/arch_factory.c \
       ...
```

Add your file in the same section, maintaining alphabetical order within
each subsystem.

## Output Format

List the exact changes as a diff-like summary:

```
File: src/arch/arch_factory.c
  Line N: Added #include "arch_<name>.h"
  Line M: Added dsc_arch_<name>_register(); call

File: Makefile
  Line X: Added src/arch/arch_<name>.c to SRCS

(or for transport:)
File: Makefile
  Line X: Added src/transport/transport_<name>.c to SRCS
```

## Quality Checklist

- [ ] `make` compiles with zero errors after your changes
- [ ] `make test` passes with zero new failures
- [ ] For arch: the new backend appears when iterating the registry
- [ ] For transport: `dsc_transport_create("<name>", NULL)` returns non-NULL
- [ ] You did NOT modify `arch.h`, `transport.h`, `arch_factory.h`, or `transport_factory.h`
- [ ] The include path in `arch_factory.c` matches the actual header filename exactly

## Edge Cases

- If the Makefile uses **wildcard** patterns (e.g. `$(wildcard src/arch/*.c)`),
  you do not need to edit the Makefile -- just placing the file is enough.
  Verify by running `make` and confirming your file appears in the build log.
- If you are adding **multiple variants** of one arch (e.g. `word48_be` and
  `word48_le`), register them all in the same `dsc_arch_<name>_register()`
  function with separate names. See `arch_byte_addressed.c` which registers
  both `byte_le` and `byte_be` from one registration function.
- If `dsc_arch_register_builtins()` already has 14+ backends registered, check
  that `MAX_ARCH_BACKENDS` (currently 16) is large enough. If not, increase it
  in `arch_factory.c`.
