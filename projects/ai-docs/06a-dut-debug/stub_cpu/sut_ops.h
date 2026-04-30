#ifndef SUT_OPS_H
#define SUT_OPS_H

/* X(enum_suffix, "tag_string") */
#define SUT_OPS_LIST(X)   \
    X(MW,    "MW")        \
    X(MT,    "MT")        \
    X(MR,    "MR")        \
    X(SND,   "SND")       \
    X(RCV,   "RCV")       \
    X(WAIT,  "WAIT")      \
    X(DONE,  "DONE")      \
    X(TMOUT, "TMOUT")

typedef enum {
#define X_ENUM(n, s) SUT_OP_##n,
    SUT_OPS_LIST(X_ENUM)
#undef X_ENUM
    SUT_OP_COUNT
} SutOpEnum;

extern const char * const g_sutOpNames[SUT_OP_COUNT];

#endif
