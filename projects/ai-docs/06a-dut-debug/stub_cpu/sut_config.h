#ifndef SUT_CONFIG_H
#define SUT_CONFIG_H

#ifndef SUT_RECORD
#define SUT_RECORD 1
#endif

#ifndef SUT_REC_PAYLOAD_MAX
#define SUT_REC_PAYLOAD_MAX 64U
#endif

#ifndef SUT_WAIT_POLL_US
#define SUT_WAIT_POLL_US 100U
#endif

#if defined(__GNUC__) || defined(__clang__) || defined(__ARMCC_VERSION) || defined(__IAR_SYSTEMS_ICC__)
#define SUT_WEAK __attribute__((weak))
#else
#define SUT_WEAK
#endif

#endif
