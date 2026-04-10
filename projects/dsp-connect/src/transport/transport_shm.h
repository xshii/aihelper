/* PURPOSE: Shared memory transport public header — mmap-based target access
 * PATTERN: Thin public header exposes only the constructor; internals stay in .c
 * FOR: Weak AI to reference how to expose a shared memory transport backend */

#ifndef DSC_TRANSPORT_SHM_H
#define DSC_TRANSPORT_SHM_H

#include "transport.h"

/* Create a shared memory transport.
 * Reads cfg->shm_path (file to mmap), cfg->shm_size (region size in bytes).
 * The returned transport is allocated but NOT mapped — call open() first. */
DscTransport *shm_transport_create(const DscTransportConfig *cfg);

#endif /* DSC_TRANSPORT_SHM_H */
