/* PURPOSE: Test runner — calls all test suites and reports totals */

#include <stdio.h>

/* Each test file exposes a main function returning 0 on success */
int test_util_main(void);
int test_arch_main(void);
int test_transport_factory_main(void);
int test_resolve_main(void);
int test_format_main(void);
int test_errors_main(void);
int test_integration_main(void);

int main(void)
{
    int failures = 0;

    printf("========================================\n");
    printf("  dsp-connect test suite\n");
    printf("========================================\n\n");

    failures += test_errors_main();
    printf("\n");
    failures += test_util_main();
    printf("\n");
    failures += test_arch_main();
    printf("\n");
    failures += test_transport_factory_main();
    printf("\n");
    failures += test_resolve_main();
    printf("\n");
    failures += test_format_main();
    printf("\n");
    failures += test_integration_main();

    printf("\n========================================\n");
    if (failures == 0) {
        printf("  ALL SUITES PASSED\n");
    } else {
        printf("  %d SUITE(S) HAD FAILURES\n", failures);
    }
    printf("========================================\n");

    return failures > 0 ? 1 : 0;
}
