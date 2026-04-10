# Step 3: Implement a New Transport Backend

## Role

You are a C developer implementing a new transport backend for dsp-connect.
You follow the existing vtable + auto-registration pattern exactly.

## Task

Create a new `transport_<name>.c` and `transport_<name>.h` file pair that implements
the `dsc_transport_ops` vtable for your target connection protocol.

## Context

Every transport backend in dsp-connect follows this structure:
1. A **private struct** that embeds `dsc_transport_t base` as its first member
2. **Six static functions** matching the `dsc_transport_ops` vtable
3. A **static const ops table**
4. A **public constructor** matching `dsc_transport_ctor` signature
5. An **auto-registration macro** call at the bottom of the file

Reference files:
- `src/transport/transport.h` -- vtable definition (DO NOT MODIFY)
- `src/transport/transport_factory.h` -- factory + `DSC_TRANSPORT_REGISTER` macro
- `src/transport/transport_serial.c` -- full example with OS-level I/O
- `src/transport/transport_shm.c` -- simpler example with memory-mapped I/O

## Steps

### Step 3.1: Copy the closest template

- If new transport uses **text command protocol** over a stream: copy `transport_serial.c`
- If new transport uses **direct memory access**: copy `transport_shm.c`
- If new transport uses **binary framed protocol**: copy `transport_serial.c` and plan
  to replace the text command helpers with binary framing

Rename the copy to `transport_<name>.c`. Create a matching `transport_<name>.h`.

### Step 3.2: Define the private struct

```c
typedef struct {
    dsc_transport_t base;       /* MUST be first member */
    /* Connection state */
    int             fd;         /* file descriptor, or -1 when closed */
    int             timeout_ms; /* I/O timeout */
    /* Protocol-specific fields */
    /* ... add what your protocol needs ... */
} <name>_transport_t;

static inline <name>_transport_t *to_<name>(dsc_transport_t *t)
{
    return (<name>_transport_t *)t;
}
```

Rules:
1. ALWAYS keep `dsc_transport_t base` as the very first member
2. ALWAYS include a timeout field
3. ALWAYS include connection state (fd, socket handle, pointer, etc.)

### Step 3.3: Write internal helper functions

Before implementing vtable functions, write the protocol-specific helpers:

For **text-based protocols** (like serial/telnet), you need:
- `send_all()` -- send a buffer, retrying on partial writes
- `recv_line()` -- receive until newline or timeout
- `send_cmd_recv()` -- send a command string, receive the response

For **binary protocols**, you need:
- `send_frame()` -- frame and send a binary message
- `recv_frame()` -- receive and deframe a binary response
- `build_read_cmd()` -- construct a read command in the wire format
- `build_write_cmd()` -- construct a write command in the wire format

For **memory-mapped protocols** (like shm), you typically need no helpers.

### Step 3.4: Implement all six vtable functions

| Function | Signature | What to Implement |
|----------|-----------|-------------------|
| `open` | `int fn(dsc_transport_t*)` | Establish connection (open fd, connect socket, map memory) |
| `close` | `void fn(dsc_transport_t*)` | Tear down connection (close fd, unmap, release resources) |
| `mem_read` | `int fn(dsc_transport_t*, uint64_t, void*, size_t)` | Read `len` bytes from target address into `buf` |
| `mem_write` | `int fn(dsc_transport_t*, uint64_t, const void*, size_t)` | Write `len` bytes from `buf` to target address |
| `exec_cmd` | `int fn(dsc_transport_t*, const char*, char*, size_t)` | Send arbitrary command string, receive response |
| `destroy` | `void fn(dsc_transport_t*)` | Call close, then free the struct |

For each function:
1. Cast to private type: `<name>_transport_t *nt = to_<name>(self);`
2. Check preconditions (e.g. `if (nt->fd < 0) return DSC_ERR_TRANSPORT_IO;`)
3. Implement using your protocol helpers from Step 3.3
4. Return `DSC_OK` on success, `DSC_ERR_TRANSPORT_*` on failure

### Step 3.5: Build the ops table

```c
static const dsc_transport_ops <name>_ops = {
    .open      = <name>_open,
    .close     = <name>_close,
    .mem_read  = <name>_mem_read,
    .mem_write = <name>_mem_write,
    .exec_cmd  = <name>_exec_cmd,
    .destroy   = <name>_destroy,
};
```

Every field must be assigned. No NULL function pointers.

### Step 3.6: Write the public constructor

```c
dsc_transport_t *<name>_transport_create(const dsc_transport_config_t *cfg)
{
    <name>_transport_t *nt = calloc(1, sizeof(*nt));
    if (!nt) return NULL;

    nt->base.ops = &<name>_ops;
    snprintf(nt->base.name, sizeof(nt->base.name), "<name>");

    /* Read config fields, with defaults for everything */
    nt->timeout_ms = (cfg && cfg->timeout_ms > 0) ? cfg->timeout_ms : 5000;
    /* ... read other fields from cfg ... */

    nt->fd = -1;  /* not yet connected */
    return &nt->base;
}
```

Rules for the constructor:
1. ALWAYS handle `cfg == NULL` -- use sensible defaults for every field
2. NEVER call `open` from the constructor -- connection is a separate step
3. Set `base.name` to a short identifier

### Step 3.7: Add auto-registration and header

At the bottom of the `.c` file, add:
```c
DSC_TRANSPORT_REGISTER("<name>", <name>_transport_create)
```

This macro uses `__attribute__((constructor))` to register before `main()`.

The `.h` file declares the constructor for use in tests:
```c
#ifndef DSC_TRANSPORT_<NAME>_H
#define DSC_TRANSPORT_<NAME>_H
#include "transport.h"
dsc_transport_t *<name>_transport_create(const dsc_transport_config_t *cfg);
#endif
```

## Output Format

Produce exactly two files:
1. `src/transport/transport_<name>.c` -- complete implementation, compilable
2. `src/transport/transport_<name>.h` -- header with constructor declaration

## Quality Checklist

- [ ] Private struct has `dsc_transport_t base` as its FIRST member
- [ ] All six vtable functions are implemented (zero NULL pointers)
- [ ] `open` can be called multiple times safely (close first if already open)
- [ ] `close` is safe to call when not open (no crash on fd == -1)
- [ ] `destroy` calls `close` before freeing memory
- [ ] `mem_read` and `mem_write` check that connection is open before I/O
- [ ] Constructor handles `cfg == NULL` without crashing
- [ ] `DSC_TRANSPORT_REGISTER` macro is at the bottom of the `.c` file
- [ ] Error codes use `DSC_ERR_TRANSPORT_*` constants from `dsc_errors.h`
- [ ] File has PURPOSE/PATTERN/FOR comment block at the top

## Edge Cases

- If the transport does **not support `exec_cmd`** (e.g. a pure memory-mapped
  interface), implement it as: `(void)self; (void)cmd; return DSC_ERR_NOT_SUPPORTED;`
  Do NOT leave it as NULL.
- If the protocol needs **fields not in `dsc_transport_config_t`**, use the
  existing fields creatively (e.g. reuse `shm_path` for a file path, `host` for
  a device identifier). Do NOT modify `transport.h`.
- If `mem_read` or `mem_write` must handle data in **chunks** (e.g. max 256 bytes
  per command), implement a loop inside the function. See `serial_mem_write` for an
  example of chunked writes.
- If the transport is **connectionless** (e.g. UDP), `open` should validate config
  and allocate the socket, `close` should release it. Reads/writes send per-request.
