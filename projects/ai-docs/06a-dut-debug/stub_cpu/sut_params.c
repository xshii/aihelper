#include "sut_params.h"
#include "sut_platform.h"
#include "bug_check.h"

SutParamsStru g_sutParams;

void SUT_ParamsSet(const SutParamsStru *pParams)
{
    BUG_RET(pParams == NULL);
    g_sutParams = *pParams;
    SUT_ParamsDump();
}

void SUT_ParamsDump(void)
{
    dbginfo("[PARAM] protoVersion=%s modelId=%u runSpec=%u cmpMode=%u stageCmp=%u hwSpec=%u powerMode=%u\n",
            g_sutParams.protoVersion,
            g_sutParams.modelId,
            (UINT32)g_sutParams.runSpec,
            (UINT32)g_sutParams.cmpMode,
            (UINT32)g_sutParams.stageCmp,
            g_sutParams.hwSpec,
            (UINT32)g_sutParams.powerMode);
}
