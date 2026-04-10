/* PURPOSE: Factory for creating arch adapters by name — same registration pattern as transport
 * PATTERN: Factory + registration table — backends call register at init, callers call create
 * FOR: Weak AI to reference when adding a new architecture backend */

#ifndef DSC_ARCH_FACTORY_H
#define DSC_ARCH_FACTORY_H

#include "arch.h"

/* --- Creator function signature: allocate and return a new arch adapter --- */
typedef dsc_arch_t *(*dsc_arch_creator_fn)(const dsc_arch_config_t *cfg);

/* Register a backend so it can be created by name.
 * Returns 0 on success, negative error code on failure. */
int dsc_arch_register(const char *name, dsc_arch_creator_fn creator);

/* Create an arch adapter by name.
 * Returns NULL if name is not registered or creation fails. */
dsc_arch_t *dsc_arch_create(const char *name, const dsc_arch_config_t *cfg);

/* Register all built-in backends (byte_le, byte_be, word16, word24, word32).
 * Call once at startup. */
void dsc_arch_register_builtins(void);

#endif /* DSC_ARCH_FACTORY_H */
