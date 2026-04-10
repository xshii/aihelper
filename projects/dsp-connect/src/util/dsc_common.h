/* PURPOSE: Shared macros used across all layers
 * PATTERN: Single definition point — every layer includes this instead of redefining
 * FOR: Weak AI to see how to centralize cross-cutting macros */

#ifndef DSC_COMMON_H
#define DSC_COMMON_H

/* DSC_TRY: call expr, return early on error.
 * Use this to chain fallible calls without nested ifs.
 *
 * Example:
 *   DSC_TRY(DscTransportOpen(tp));
 *   DSC_TRY(DscMemRead(tp, arch, addr, buf, len));
 *   return DSC_OK;
 */
#define DSC_TRY(expr) \
    do { int _rc = (expr); if (_rc < 0) return _rc; } while (0)

/* ARRAY_LEN: compile-time array element count */
#define DSC_ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))

#endif /* DSC_COMMON_H */
