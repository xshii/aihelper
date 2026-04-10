/* PURPOSE: Telnet transport public header — TCP-based target access
 * PATTERN: Thin public header exposes only the constructor; internals stay in .c
 * FOR: Weak AI to reference how to expose a concrete transport backend */

#ifndef DSC_TRANSPORT_TELNET_H
#define DSC_TRANSPORT_TELNET_H

#include "transport.h"

/* Create a telnet transport.
 * Reads cfg->host, cfg->port (default 23), cfg->timeout_ms (default 5000).
 * The returned transport is allocated but NOT connected — call open() first. */
dsc_transport_t *telnet_transport_create(const dsc_transport_config_t *cfg);

#endif /* DSC_TRANSPORT_TELNET_H */
