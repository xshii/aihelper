# Step 2: Implement a New Architecture Adapter

## Role

You are a C developer implementing a new architecture backend for dsp-connect.
You follow the existing vtable pattern exactly. You do not invent new patterns.

## Task

Create a new `arch_<name>.c` and `arch_<name>.h` file pair that implements the
`dsc_arch_ops` vtable for your target architecture.

## Context

Every arch adapter in dsp-connect follows this structure:
1. A **private struct** that embeds `dsc_arch_t base` as its first member
2. **Six static functions** matching the `dsc_arch_ops` vtable signatures
3. A **static const ops table** wiring the functions together
4. One or more **creator functions** called by the factory
5. A **registration function** called from `dsc_arch_register_builtins()`

Reference files:
- `src/arch/arch.h` -- vtable definition (DO NOT MODIFY)
- `src/arch/arch_byte_addressed.c` -- simple baseline (identity mapping)
- `src/arch/arch_word_addressed.c` -- complex baseline (shift/divide mapping)
- `src/arch/arch_factory.h` -- factory API (DO NOT MODIFY)

## Steps

### Step 2.1: Copy the closest template

- If new target is byte-addressed: copy `arch_byte_addressed.c` as starting point
- If new target is word-addressed: copy `arch_word_addressed.c` as starting point

Rename the copy to `arch_<name>.c`. Create a matching `arch_<name>.h`.

### Step 2.2: Define the private struct

Replace the template's private struct with your target's fields:

```c
/* Example for a hypothetical 48-bit DSP */
typedef struct {
    dsc_arch_t base;            /* MUST be first member -- never move this */
    int word_bytes;             /* 6 for 48-bit */
    int is_big_endian;
    int host_is_big_endian;
    int addr_shift;             /* 0 if not power-of-2 word size */
    /* ADD any target-specific fields here */
} arch_<name>_t;
```

Rules for the private struct:
1. ALWAYS keep `dsc_arch_t base` as the very first member
2. ALWAYS include `is_big_endian` and `host_is_big_endian`
3. Only add fields you actually use in vtable functions

### Step 2.3: Implement all six vtable functions

You MUST implement every function. Here is what each one does:

| Function | Signature | What to Implement |
|----------|-----------|-------------------|
| `logical_to_physical` | `int fn(const dsc_arch_t*, uint64_t, uint64_t*)` | Convert DWARF logical addr to transport physical addr |
| `physical_to_logical` | `int fn(const dsc_arch_t*, uint64_t, uint64_t*)` | Reverse of above |
| `swap_endian` | `void fn(const dsc_arch_t*, void*, size_t)` | Byte-swap if host != target endianness |
| `min_access_size` | `size_t fn(const dsc_arch_t*)` | Return smallest readable unit in bytes |
| `word_size` | `size_t fn(const dsc_arch_t*)` | Return word size in bytes |
| `destroy` | `void fn(dsc_arch_t*)` | Free the struct (call `free(self)`) |

For each function:
1. Cast `self` to your private struct type: `const arch_<name>_t *a = (const arch_<name>_t *)self;`
2. Implement the logic based on your comparison table from Step 1
3. Return `DSC_OK` on success, `DSC_ERR_MEM_ALIGN` for alignment errors

### Step 2.4: Build the ops table

```c
static const struct dsc_arch_ops <name>_ops = {
    .logical_to_physical = <name>_logical_to_physical,
    .physical_to_logical = <name>_physical_to_logical,
    .swap_endian         = <name>_swap_endian,
    .min_access_size     = <name>_min_access_size,
    .word_size           = <name>_word_size,
    .destroy             = <name>_destroy,
};
```

Every field must be assigned. No NULL function pointers.

### Step 2.5: Write creator + registration functions

```c
/* Creator: allocate, set ops, set defaults, return base pointer */
static dsc_arch_t *<name>_create(const dsc_arch_config_t *cfg)
{
    arch_<name>_t *a = calloc(1, sizeof(*a));
    if (!a) return NULL;

    a->base.ops = &<name>_ops;
    /* Fill fields from cfg, with sensible defaults if cfg is NULL */
    /* Set a->base.name to a descriptive string */
    return &a->base;
}

/* Registration: called from dsc_arch_register_builtins() */
void dsc_arch_<name>_register(void)
{
    dsc_arch_register("<name>", <name>_create);
}
```

### Step 2.6: Write the header file

```c
#ifndef DSC_ARCH_<NAME>_H
#define DSC_ARCH_<NAME>_H

#include "arch.h"

/* Register this backend. Called by dsc_arch_register_builtins(). */
void dsc_arch_<name>_register(void);

#endif
```

## Output Format

Produce exactly two files:
1. `src/arch/arch_<name>.c` -- complete implementation, compilable
2. `src/arch/arch_<name>.h` -- header with registration function declaration

## Quality Checklist

- [ ] Private struct has `dsc_arch_t base` as its FIRST member
- [ ] All six vtable functions are implemented (zero NULL pointers in ops table)
- [ ] `logical_to_physical` and `physical_to_logical` are exact inverses of each other
- [ ] `swap_endian` is a no-op when host endianness matches target endianness
- [ ] `min_access_size` returns the correct minimum for the architecture
- [ ] Creator function handles `cfg == NULL` gracefully (uses defaults)
- [ ] `base.name` is set to a descriptive string (max 31 chars)
- [ ] No modifications to `arch.h` or `arch_factory.h`
- [ ] File has PURPOSE/PATTERN/FOR comment block at the top

## Edge Cases

- If the target has a **non-power-of-2 word size** (e.g. 24-bit = 3 bytes), use
  division/multiplication instead of bit shifts. See `arch_word_addressed.c` line 67-73.
- If the target has **multiple endianness modes**, create separate creator wrappers
  (one per mode) and register each with a distinct name. See `byte_le_create` / `byte_be_create`.
- If `cfg` is NULL, use the most common configuration for this target as the default.
  DSPs are often big-endian; byte-addressed targets are often little-endian.
