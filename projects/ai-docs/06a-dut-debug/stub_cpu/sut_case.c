#include "sut_case.h"
#include "sut_platform.h"
#include "bug_check.h"
#include <string.h>

const SutCaseStru *SUT_CaseFindById(UINT32 id)
{
    UINT32 count = g_sutCaseCount;
    for (UINT32 i = 0; i < count; i++) {
        if (g_sutCaseTable[i].id == id) {
            return &g_sutCaseTable[i];
        }
    }
    return NULL;
}

const SutCaseStru *SUT_CaseFindByName(const char *pName)
{
    BUG_RET_VAL(pName == NULL, NULL);
    UINT32 count = g_sutCaseCount;
    for (UINT32 i = 0; i < count; i++) {
        if (strcmp(g_sutCaseTable[i].pName, pName) == 0) {
            return &g_sutCaseTable[i];
        }
    }
    return NULL;
}

ERRNO_T SUT_CaseRun(const SutCaseStru *pCase)
{
    BUG_RET_VAL(pCase == NULL, ERROR);
    BUG_RET_VAL(pCase->pFn == NULL, ERROR);
    dbginfo("[CASE] start id=%u name=%s\n", pCase->id, pCase->pName);
    ERRNO_T rc = pCase->pFn();
    dbginfo("[CASE] end   id=%u name=%s rc=%d\n", pCase->id, pCase->pName, rc);
    return rc;
}
