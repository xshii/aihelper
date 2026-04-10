/* PURPOSE: Test runner — calls all test suites and reports totals */

#include <stdio.h>

/* Unity requires exactly one setUp/tearDown per test executable */
void setUp(void) {}
void tearDown(void) {}

/* Each test file exposes a main function returning failure count */
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
    printf("  dsp-connect test suite (Unity)\n");
    printf("========================================\n\n");

    failures += test_errors_main();
    failures += test_util_main();
    failures += test_arch_main();
    failures += test_transport_factory_main();
    failures += test_resolve_main();
    failures += test_format_main();
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
