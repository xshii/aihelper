/* PURPOSE: Factory implementation — registration table + create-by-name lookup
 * PATTERN: Static array registry, linear scan lookup — simple and predictable
 * FOR: Weak AI to copy when building any factory/registry system */

#include <string.h>

#include "arch_factory.h"
#include "arch_byte_addressed.h"
#include "arch_word_addressed.h"
#include "../core/dsc_errors.h"

/* --- Registry: fixed-size table of (name -> creator) pairs --- */
#define MAX_ARCH_BACKENDS 16

typedef struct {
    char name[32];
    DscArchCreatorFn creator;
} arch_registry_entry_t;

static arch_registry_entry_t registry[MAX_ARCH_BACKENDS];
static int registry_count = 0;

/* --- Register a backend --- */
int DscArchRegister(const char *name, DscArchCreatorFn creator)
{
    if (!name || !creator) {
        return DSC_ERR_INVALID_ARG;
    }
    if (registry_count >= MAX_ARCH_BACKENDS) {
        return DSC_ERR_NOMEM;
    }

    /* Check for duplicate name */
    for (int i = 0; i < registry_count; i++) {
        if (strcmp(registry[i].name, name) == 0) {
            return DSC_ERR_INVALID_ARG;
        }
    }

    UINT32 len = strlen(name);
    if (len >= sizeof(registry[0].name)) {
        return DSC_ERR_INVALID_ARG;
    }

    memcpy(registry[registry_count].name, name, len + 1);
    registry[registry_count].creator = creator;
    registry_count++;
    return DSC_OK;
}

/* --- Create by name --- */
DscArch *DscArchCreate(const char *name, const DscArchConfig *cfg)
{
    if (!name) {
        return NULL;
    }

    for (int i = 0; i < registry_count; i++) {
        if (strcmp(registry[i].name, name) == 0) {
            return registry[i].creator(cfg);
        }
    }
    return NULL;  /* not found */
}

/* --- Register all built-in backends --- */
void DscArchRegisterBuiltins(void)
{
    /* Byte-addressed backends */
    DscArchByteRegister();

    /* Word-addressed backends */
    DscArchWordRegister();
}
