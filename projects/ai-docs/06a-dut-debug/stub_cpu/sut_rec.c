#include "sut_rec.h"
#include "sut_platform.h"
#include "bug_check.h"

const char * const g_sutOpNames[SUT_OP_COUNT] = {
#define X_STR(n, s) [SUT_OP_##n] = s,
    SUT_OPS_LIST(X_STR)
#undef X_STR
};

#if SUT_RECORD

enum {
    SUT_HEX_CHARS_PER_BYTE = 2,
    SUT_HEX_SLACK_BYTES    = 4,
    SUT_NIBBLE_BITS        = 4,
    SUT_NIBBLE_MASK        = 0x0F,
    SUT_HEX_ALPHA_BASE     = 10,
};

static UINT32 g_sutRecSeq;

static char SutRecHexChar(UINT8 nibble)
{
    return (char)(nibble < SUT_HEX_ALPHA_BASE
                  ? '0' + nibble
                  : 'A' + (nibble - SUT_HEX_ALPHA_BASE));
}

static UINT32 SutRecHexEncode(const UINT8 *pIn, UINT32 inLen, char *pOut, UINT32 outCap)
{
    UINT32 limit = inLen;
    UINT32 maxBytes = (outCap - 1U) / SUT_HEX_CHARS_PER_BYTE;
    if (limit > maxBytes) {
        limit = maxBytes;
    }
    for (UINT32 i = 0; i < limit; i++) {
        UINT8 hi = (UINT8)((pIn[i] >> SUT_NIBBLE_BITS) & SUT_NIBBLE_MASK);
        UINT8 lo = (UINT8)(pIn[i] & SUT_NIBBLE_MASK);
        pOut[i * SUT_HEX_CHARS_PER_BYTE]      = SutRecHexChar(hi);
        pOut[i * SUT_HEX_CHARS_PER_BYTE + 1U] = SutRecHexChar(lo);
    }
    pOut[limit * SUT_HEX_CHARS_PER_BYTE] = '\0';
    return limit;
}

void SUT_RecEvent(SutOpEnum op, UINT32 key, const void *pData, UINT32 len)
{
    BUG_RET((UINT32)op >= SUT_OP_COUNT);

    const UINT8 *pBytes = (const UINT8 *)pData;
    UINT32 remaining = (pBytes == NULL) ? 0U : len;
    UINT32 offset = 0U;
    UINT32 pass = 0U;

    do {
        char hexBuf[SUT_REC_PAYLOAD_MAX * SUT_HEX_CHARS_PER_BYTE + SUT_HEX_SLACK_BYTES];
        UINT32 take = (remaining > SUT_REC_PAYLOAD_MAX) ? SUT_REC_PAYLOAD_MAX : remaining;
        UINT32 chunk = 0U;

        if (take > 0U) {
            chunk = SutRecHexEncode(pBytes + offset, take, hexBuf, (UINT32)sizeof(hexBuf));
        } else {
            hexBuf[0] = '\0';
        }

        g_sutRecSeq++;
        dbginfo("[REC] %06u %s%s %08X %04X %s\n",
                g_sutRecSeq,
                g_sutOpNames[op],
                (pass > 0U) ? "+" : "",
                key,
                len,
                hexBuf);

        offset    += chunk;
        remaining -= chunk;
        pass++;
    } while (remaining > 0U);
}

#endif
