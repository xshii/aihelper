#ifndef SUT_CASE_H
#define SUT_CASE_H

#include "sut_types.h"

typedef ERRNO_T (*SutCaseFn)(void);

typedef struct {
    UINT32       id;
    const char  *pName;
    SutCaseFn    pFn;
} SutCaseStru;

extern const SutCaseStru g_sutCaseTable[];
extern const UINT32      g_sutCaseCount;

const SutCaseStru *SUT_CaseFindById(UINT32 id);
const SutCaseStru *SUT_CaseFindByName(const char *pName);
ERRNO_T            SUT_CaseRun(const SutCaseStru *pCase);

#endif
