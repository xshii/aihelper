/* PURPOSE: Transport factory implementation — static registry, no heap for registry itself
 * PATTERN: fixed-size array registry with linear search (simple, bounded, predictable)
 * FOR: 弱 AI 参考如何实现 name → constructor 的工厂注册表 */

#include <string.h>

#include "transport_factory.h"
#include "../util/log.h"

/* ---------- Registry storage ---------- */

#define DSC_MAX_TRANSPORTS 16

typedef struct {
    const char        *name;
    DscTransportCtor ctor;
} registry_entry_t;

static registry_entry_t s_registry[DSC_MAX_TRANSPORTS];
static int              s_registry_count = 0;

/* ---------- Registration ---------- */

int DscTransportRegister(const char *name, DscTransportCtor ctor)
{
    if (!name || !ctor) {
        return DSC_ERR_INVALID_ARG;
    }

    if (s_registry_count >= DSC_MAX_TRANSPORTS) {
        DSC_LOG_ERROR("transport registry full (max %d)", DSC_MAX_TRANSPORTS);
        return DSC_ERR_NOMEM;
    }

    /* Check for duplicate name */
    for (int i = 0; i < s_registry_count; i++) {
        if (strcmp(s_registry[i].name, name) == 0) {
            DSC_LOG_WARN("transport '%s' already registered, replacing", name);
            s_registry[i].ctor = ctor;
            return DSC_OK;
        }
    }

    s_registry[s_registry_count].name = name;
    s_registry[s_registry_count].ctor = ctor;
    s_registry_count++;

    DSC_LOG_DEBUG("registered transport '%s' (%d/%d)",
                  name, s_registry_count, DSC_MAX_TRANSPORTS);
    return DSC_OK;
}

/* ---------- Creation ---------- */

DscTransport *DscTransportCreate(const char *name,
                                      const DscTransportConfig *cfg)
{
    if (!name) {
        return NULL;
    }

    for (int i = 0; i < s_registry_count; i++) {
        if (strcmp(s_registry[i].name, name) == 0) {
            DscTransport *t = s_registry[i].ctor(cfg);
            if (t) {
                DSC_LOG_INFO("created transport '%s'", name);
            }
            return t;
        }
    }

    DSC_LOG_ERROR("transport '%s' not found in registry", name);
    return NULL;
}

/* ---------- Cleanup ---------- */

void dsc_transport_free(DscTransport *t)
{
    if (!t) {
        return;
    }
    t->ops->close(t);
    t->ops->destroy(t);
}

/* ---------- Listing ---------- */

int DscTransportList(const char **names, int max_names)
{
    int count = (s_registry_count < max_names) ? s_registry_count : max_names;
    for (int i = 0; i < count; i++) {
        names[i] = s_registry[i].name;
    }
    return count;
}
