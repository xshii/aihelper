# Step 1: Identify How the New Target Differs from Existing Ones

## Role

You are a hardware abstraction analyst. Your job is to produce a structured comparison
between the new target and the closest existing adapter in dsp-connect.

## Task

Before writing any code, document exactly how the new target differs from existing
adapters. This comparison table becomes the specification for your implementation.

## Context

dsp-connect currently supports these architectures:
- `byte_le` / `byte_be` -- byte-addressed, 8-bit addressable unit (ARM, x86, etc.)
- `word16` -- 16-bit word-addressed DSP (logical / 2 = physical)
- `word24` -- 24-bit word-addressed DSP (logical / 3 = physical)
- `word32` -- 32-bit word-addressed DSP (logical / 4 = physical)

And these transports:
- `serial` -- UART/serial port, text command protocol ("md addr len" / "mw addr val")
- `telnet` -- TCP/telnet, same text command protocol
- `shm` -- shared memory, direct memory-mapped access

## Steps

1. **Pick the closest existing adapter** as your baseline.
   - If the new target is byte-addressed, baseline = `arch_byte_addressed.c`
   - If the new target is word-addressed, baseline = `arch_word_addressed.c`
   - If the new transport uses text commands, baseline = `transport_serial.c`
   - If the new transport uses direct memory, baseline = `transport_shm.c`

2. **Fill in the Architecture Comparison Table** (if adding an arch adapter):

   | Property | Baseline Adapter | New Target | Impact on Code |
   |----------|-----------------|------------|----------------|
   | Word size (bits) | e.g. 16 | ? | Changes `word_bytes` and shift logic |
   | Endianness | e.g. big | ? | Changes `swap_endian` behavior |
   | Address mapping | e.g. logical/2 = physical | ? | Changes `logical_to_physical` |
   | Min access size | e.g. 2 bytes | ? | Changes `min_access_size` return |
   | Alignment rules | e.g. must be word-aligned | ? | Changes alignment check |
   | Special quirks | none | ? | May need new private struct fields |

3. **Fill in the Transport Comparison Table** (if adding a transport):

   | Property | Baseline Transport | New Target | Impact on Code |
   |----------|-------------------|------------|----------------|
   | Connection type | e.g. TCP socket | ? | Changes `open`/`close` |
   | Connection params | e.g. host + port | ? | New fields in config struct |
   | Command format | e.g. "md 0xADDR LEN" | ? | Changes `mem_read` command |
   | Response format | e.g. "ADDR: HEXWORDS" | ? | Changes response parsing |
   | Write command | e.g. "mw 0xADDR 0xVAL" | ? | Changes `mem_write` command |
   | Timeout handling | e.g. select() with ms | ? | Changes wait logic |
   | Binary or text | text | ? | May change entire protocol layer |

4. **List any properties that do NOT map to existing vtable functions.**
   If the new target requires capabilities not in the current vtable, STOP and
   report this. Do NOT modify the vtable interfaces yourself.

## Output Format

```markdown
## Target Comparison: [New Target Name]

### Baseline: [chosen baseline adapter]

### Architecture Differences
| Property | Baseline | New Target | Code Impact |
|----------|----------|------------|-------------|
| ... | ... | ... | ... |

### Transport Differences
| Property | Baseline | New Target | Code Impact |
|----------|----------|------------|-------------|
| ... | ... | ... | ... |

### Unmapped Properties
[List any new-target properties that do not fit current vtable, or "None"]

### Decision
- Adapter type to create: arch / transport / both
- Closest template file: [filename]
- Estimated new private struct fields: [list]
- Estimated new helper functions: [list]
```

## Quality Checklist

- [ ] Every cell in the comparison table is filled (no "TBD" or "..." left)
- [ ] "Code Impact" column says which specific function is affected
- [ ] If "Unmapped Properties" is non-empty, you have flagged it clearly
- [ ] You picked the single closest baseline, not multiple

## Edge Cases

- If the new target has **banked memory** (multiple address spaces), note this under
  Special quirks. The current `logical_to_physical` takes one address; you may need a
  bank selector in the private struct.
- If the new transport is **binary** (not text commands), note that `exec_cmd` still
  takes a string. You can implement it as a no-op or use it for control commands only.
- If you are unsure about a property, write "UNKNOWN -- need datasheet" and continue.
  Do NOT guess hardware behavior.
