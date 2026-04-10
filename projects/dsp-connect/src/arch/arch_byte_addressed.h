/* PURPOSE: Byte-addressed architecture backend — for ARM, x86, RISC-V, etc.
 * PATTERN: Concrete vtable implementation registered via factory
 * FOR: Weak AI to reference as the simplest arch backend (identity mapping) */

#ifndef DSC_ARCH_BYTE_ADDRESSED_H
#define DSC_ARCH_BYTE_ADDRESSED_H

#include "arch.h"

/* Register "byte_le" and "byte_be" backends with the factory.
 * Called by dsc_arch_register_builtins(). */
void dsc_arch_byte_register(void);

#endif /* DSC_ARCH_BYTE_ADDRESSED_H */
