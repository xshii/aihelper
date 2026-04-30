#ifndef SUT_PARAMS_H
#define SUT_PARAMS_H

#include "sut_types.h"

typedef enum {
    SUT_RUN_SPEC_FIRST = 0,
    SUT_RUN_SPEC_OPT   = 1,
    SUT_RUN_SPEC_PROD  = 2,
} SutRunSpecEnum;

typedef enum {
    SUT_CMP_MODE_STAGE = 0,
    SUT_CMP_MODE_E2E   = 1,
} SutCmpModeEnum;

typedef enum {
    SUT_STAGE_CMP_BASIC = 0,
    SUT_STAGE_CMP_ADV   = 1,
    SUT_STAGE_CMP_PROD  = 2,
} SutStageCmpEnum;

typedef enum {
    SUT_POWER_NORMAL = 0,
    SUT_POWER_LOW    = 1,
    SUT_POWER_PGOOD  = 2,
} SutPowerModeEnum;

typedef struct {
    char             protoVersion[16];
    UINT32           modelId;
    SutRunSpecEnum   runSpec;
    SutCmpModeEnum   cmpMode;
    SutStageCmpEnum  stageCmp;
    UINT32           hwSpec;
    SutPowerModeEnum powerMode;
} SutParamsStru;

extern SutParamsStru g_sutParams;

void SUT_ParamsSet(const SutParamsStru *pParams);
void SUT_ParamsDump(void);

#endif
