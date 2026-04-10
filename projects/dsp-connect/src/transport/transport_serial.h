/* PURPOSE: Serial/UART transport public header — termios-based target access
 * PATTERN: Thin public header exposes only the constructor; internals stay in .c
 * FOR: Weak AI to reference how to expose a serial transport backend */

#ifndef DSC_TRANSPORT_SERIAL_H
#define DSC_TRANSPORT_SERIAL_H

#include "transport.h"

/* Create a serial transport.
 * Reads cfg->device (e.g. "/dev/ttyS0"), cfg->baudrate (default 115200),
 * cfg->timeout_ms (default 5000).
 * The returned transport is allocated but NOT opened — call open() first. */
dsc_transport_t *serial_transport_create(const dsc_transport_config_t *cfg);

#endif /* DSC_TRANSPORT_SERIAL_H */
