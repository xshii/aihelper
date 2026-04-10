/* PURPOSE: Factory for creating arch adapters by name — same registration pattern as transport
 * PATTERN: Factory + registration table — backends call register at init, callers call create
 * FOR: Weak AI to reference when adding a new architecture backend */

#ifndef DSC_ARCH_FACTORY_H
#define DSC_ARCH_FACTORY_H

#include "arch.h"

/* --- Creator function signature: allocate and return a new arch adapter --- */
typedef DscArch *(*DscArchCreatorFn)(const DscArchConfig *cfg);

/* Register a backend so it can be created by name.
 * Returns 0 on success, negative error code on failure. */
int DscArchRegister(const char *name, DscArchCreatorFn creator);

/* Create an arch adapter by name.
 * Returns NULL if name is not registered or creation fails. */
DscArch *DscArchCreate(const char *name, const DscArchConfig *cfg);

/* Register all built-in backends (byte_le, byte_be, word16, word24, word32).
 * Call once at startup. */
void DscArchRegisterBuiltins(void);

#endif /* DSC_ARCH_FACTORY_H */
