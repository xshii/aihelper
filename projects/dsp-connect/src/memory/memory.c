/* PURPOSE: Memory read/write implementation with address translation,
 *          endian swap, and chunked transfers.
 * PATTERN: Each public function follows the same 3-step flow:
 *          (1) translate address  (2) chunked transfer  (3) endian swap
 *          Chunking splits large transfers into MAX_CHUNK_SIZE pieces so
 *          transports with limited buffer sizes still work.
 * FOR: 弱 AI 参考如何做地址转换 + 分块传输 + 字节序处理 */

#include <string.h>

#include "memory.h"
#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"
#include "../util/log.h"

/* Maximum bytes per single transport read/write.
 * Keeps individual operations small for transports with limited buffers. */
#define MAX_CHUNK_SIZE 1024

/* ------------------------------------------------------------------ */
/* Public API: read                                                   */
/* ------------------------------------------------------------------ */
int DscMemRead(DscTransport *tp, const DscArch *arch,
                 UINT64 logical_addr, void *buf, UINT32 len)
{
    if (tp == NULL || buf == NULL) {
        return DSC_ERR_INVALID_ARG;
    }
    if (len == 0) {
        return DSC_OK;
    }

    /* Step 1: translate logical → physical address */
    UINT64 phys_addr = logical_addr;
    if (arch != NULL) {
        DSC_TRY(DscArchLogicalToPhysical(arch, logical_addr, &phys_addr));
    }

    DSC_LOG_DEBUG("mem_read: logical=0x%llx phys=0x%llx len=%zu",
                  (unsigned long long)logical_addr,
                  (unsigned long long)phys_addr,
                  len);

    /* Step 2: chunked read */
    UINT8 *dst = (UINT8 *)buf;
    UINT32 remaining = len;
    UINT64 addr = phys_addr;

    while (remaining > 0) {
        UINT32 chunk = (remaining > MAX_CHUNK_SIZE) ? MAX_CHUNK_SIZE : remaining;

        int rc = DscTransportMemRead(tp, addr, dst, chunk);
        if (rc < 0) {
            DSC_LOG_ERROR("mem_read: transport error at phys=0x%llx chunk=%zu",
                          (unsigned long long)addr, chunk);
            return DSC_ERR_MEM_READ;
        }

        dst       += chunk;
        addr      += chunk;
        remaining -= chunk;
    }

    /* Step 3: endian swap.
     * Only swap if arch is provided and the read is for a single value
     * (i.e., size is a power of two and <= 8 bytes — typical scalar).
     * Bulk reads of byte arrays should NOT be swapped. */
    if (arch != NULL && len <= 8 && (len & (len - 1)) == 0) {
        DscArchSwapEndian(arch, buf, len);
    }

    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Public API: write                                                  */
/* ------------------------------------------------------------------ */
int DscMemWrite(DscTransport *tp, const DscArch *arch,
                  UINT64 logical_addr, const void *buf, UINT32 len)
{
    if (tp == NULL || buf == NULL) {
        return DSC_ERR_INVALID_ARG;
    }
    if (len == 0) {
        return DSC_OK;
    }

    /* Step 1: translate logical → physical address */
    UINT64 phys_addr = logical_addr;
    if (arch != NULL) {
        DSC_TRY(DscArchLogicalToPhysical(arch, logical_addr, &phys_addr));
    }

    DSC_LOG_DEBUG("mem_write: logical=0x%llx phys=0x%llx len=%zu",
                  (unsigned long long)logical_addr,
                  (unsigned long long)phys_addr,
                  len);

    /* Step 2: endian swap for scalar writes.
     * We work on a local copy to avoid mutating the caller's buffer. */
    UINT8 swap_buf[8];
    const UINT8 *src = (const UINT8 *)buf;

    if (arch != NULL && len <= 8 && (len & (len - 1)) == 0) {
        memcpy(swap_buf, buf, len);
        DscArchSwapEndian(arch, swap_buf, len);
        src = swap_buf;
    }

    /* Step 3: chunked write */
    UINT32 remaining = len;
    UINT64 addr = phys_addr;

    while (remaining > 0) {
        UINT32 chunk = (remaining > MAX_CHUNK_SIZE) ? MAX_CHUNK_SIZE : remaining;

        int rc = DscTransportMemWrite(tp, addr, src, chunk);
        if (rc < 0) {
            DSC_LOG_ERROR("mem_write: transport error at phys=0x%llx chunk=%zu",
                          (unsigned long long)addr, chunk);
            return DSC_ERR_MEM_WRITE;
        }

        src       += chunk;
        addr      += chunk;
        remaining -= chunk;
    }

    return DSC_OK;
}
