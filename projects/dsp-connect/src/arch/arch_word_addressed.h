/* PURPOSE: Word-addressed architecture backend — for DSPs with 16/24/32-bit words
 * PATTERN: Concrete vtable implementation registered via factory
 * FOR: Weak AI to reference when handling non-byte-addressable DSP targets */

#ifndef DSC_ARCH_WORD_ADDRESSED_H
#define DSC_ARCH_WORD_ADDRESSED_H

#include "arch.h"

/* Register "word16", "word24", "word32" backends with the factory.
 * Called by DscArchRegisterBuiltins(). */
void DscArchWordRegister(void);

#endif /* DSC_ARCH_WORD_ADDRESSED_H */
