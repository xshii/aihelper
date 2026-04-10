/* PURPOSE: Mock arch adapters for testing — identity and word16 presets
 * PATTERN: Static vtable, no heap allocation, deterministic behavior
 * FOR: Unit tests that need arch without real DSP hardware */

#ifndef MOCK_ARCH_H
#define MOCK_ARCH_H

#include "../../src/arch/arch.h"

/* Identity arch: byte-addressed, little-endian, no address translation.
 * Returns a pointer to a static object — do NOT call DscArchDestroy(). */
DscArch *mock_arch_identity(void);

/* Word16 arch: 16-bit word-addressed, little-endian on LE host.
 * logical = physical * 2.
 * Returns a pointer to a static object — do NOT call DscArchDestroy(). */
DscArch *mock_arch_word16(void);

#endif /* MOCK_ARCH_H */
