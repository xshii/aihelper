/* PURPOSE: Factory with static registry — create transports by name string
 * PATTERN: registry array + constructor function pointer, no dynamic allocation
 * FOR: Weak AI to reference how to build a plugin registry in pure C */

#ifndef DSC_TRANSPORT_FACTORY_H
#define DSC_TRANSPORT_FACTORY_H

#include "transport.h"

/* ---------- Constructor type ---------- */

/* Each backend provides a function matching this signature.
 * It allocates and returns a fully initialized (but not yet opened) transport. */
typedef dsc_transport_t *(*dsc_transport_ctor)(const dsc_transport_config_t *cfg);

/* ---------- Registry API ---------- */

/* Register a named transport backend.
 * Returns DSC_OK on success, DSC_ERR_NOMEM if registry is full,
 * DSC_ERR_INVALID_ARG if name or ctor is NULL. */
int dsc_transport_register(const char *name, dsc_transport_ctor ctor);

/* Create a transport by registered name.
 * Returns NULL if name is not found or constructor fails. */
dsc_transport_t *dsc_transport_create(const char *name,
                                      const dsc_transport_config_t *cfg);

/* Convenience: close + destroy in one call.
 * Safe to call with NULL. */
void dsc_transport_free(dsc_transport_t *t);

/* List registered transport names.
 * Fills names[] up to max_names entries.
 * Returns the number of entries written. */
int dsc_transport_list(const char **names, int max_names);

/* ---------- Auto-registration helper ---------- */

/* Use this macro in a .c file to auto-register a backend at load time.
 * Example:  DSC_TRANSPORT_REGISTER("telnet", telnet_transport_create)
 * The constructor attribute runs before main(). */
#define DSC_TRANSPORT_REGISTER(name_str, ctor_fn)                       \
    __attribute__((constructor))                                        \
    static void _dsc_register_##ctor_fn(void) {                         \
        dsc_transport_register(name_str, ctor_fn);                      \
    }

#endif /* DSC_TRANSPORT_FACTORY_H */
