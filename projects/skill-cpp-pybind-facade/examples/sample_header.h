/**
 * libsigproc - Signal Processing Library
 *
 * Types: IQ16 (16-bit I/Q), IQ32 (32-bit I/Q), Float32, Float64, FixPoint (fixed-point)
 *
 * This header is intentionally ugly to simulate a real-world flat C API
 * with combinatorial type explosion.
 */

#ifndef LIBSIGPROC_H
#define LIBSIGPROC_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Type Definitions
 * ============================================================ */

typedef struct {
    int16_t i;  /* in-phase */
    int16_t q;  /* quadrature */
} IQ16;

typedef struct {
    int32_t i;
    int32_t q;
} IQ32;

typedef float Float32;
typedef double Float64;

typedef struct {
    int32_t value;
    int8_t  frac_bits;  /* number of fractional bits */
} FixPoint;

/* ============================================================
 * Conversion Functions (5 types → 20 functions)
 * ============================================================ */

int sp_convert_IQ16_to_IQ32(const IQ16* src, IQ32* dst, int count);
int sp_convert_IQ16_to_Float32(const IQ16* src, Float32* dst, int count);
int sp_convert_IQ16_to_Float64(const IQ16* src, Float64* dst, int count);
int sp_convert_IQ16_to_FixPoint(const IQ16* src, FixPoint* dst, int count);

int sp_convert_IQ32_to_IQ16(const IQ32* src, IQ16* dst, int count);
int sp_convert_IQ32_to_Float32(const IQ32* src, Float32* dst, int count);
int sp_convert_IQ32_to_Float64(const IQ32* src, Float64* dst, int count);
int sp_convert_IQ32_to_FixPoint(const IQ32* src, FixPoint* dst, int count);

int sp_convert_Float32_to_IQ16(const Float32* src, IQ16* dst, int count);
int sp_convert_Float32_to_IQ32(const Float32* src, IQ32* dst, int count);
int sp_convert_Float32_to_Float64(const Float32* src, Float64* dst, int count);
int sp_convert_Float32_to_FixPoint(const Float32* src, FixPoint* dst, int count);

int sp_convert_Float64_to_IQ16(const Float64* src, IQ16* dst, int count);
int sp_convert_Float64_to_IQ32(const Float64* src, IQ32* dst, int count);
int sp_convert_Float64_to_Float32(const Float64* src, Float32* dst, int count);
int sp_convert_Float64_to_FixPoint(const Float64* src, FixPoint* dst, int count);

int sp_convert_FixPoint_to_IQ16(const FixPoint* src, IQ16* dst, int count);
int sp_convert_FixPoint_to_IQ32(const FixPoint* src, IQ32* dst, int count);
int sp_convert_FixPoint_to_Float32(const FixPoint* src, Float32* dst, int count);
int sp_convert_FixPoint_to_Float64(const FixPoint* src, Float64* dst, int count);

/* ============================================================
 * Compute Functions: add (5*5 = 25 type combos)
 * ============================================================ */

int sp_compute_add_IQ16_IQ16(const IQ16* a, const IQ16* b, IQ16* out, int n);
int sp_compute_add_IQ16_IQ32(const IQ16* a, const IQ32* b, IQ32* out, int n);
int sp_compute_add_IQ16_Float32(const IQ16* a, const Float32* b, Float32* out, int n);
int sp_compute_add_IQ32_IQ32(const IQ32* a, const IQ32* b, IQ32* out, int n);
int sp_compute_add_IQ32_Float32(const IQ32* a, const Float32* b, Float32* out, int n);
int sp_compute_add_Float32_Float32(const Float32* a, const Float32* b, Float32* out, int n);
int sp_compute_add_Float64_Float64(const Float64* a, const Float64* b, Float64* out, int n);

/* ============================================================
 * Compute Functions: mul (selected combos)
 * ============================================================ */

int sp_compute_mul_IQ16_IQ16(const IQ16* a, const IQ16* b, IQ32* out, int n);
int sp_compute_mul_IQ16_Float32(const IQ16* a, const Float32* b, Float32* out, int n);
int sp_compute_mul_IQ32_IQ32(const IQ32* a, const IQ32* b, IQ32* out, int n);
int sp_compute_mul_Float32_Float32(const Float32* a, const Float32* b, Float32* out, int n);
int sp_compute_mul_Float64_Float64(const Float64* a, const Float64* b, Float64* out, int n);

/* ============================================================
 * Compute Functions: correlate (cross-correlation)
 * ============================================================ */

int sp_compute_correlate_IQ16_IQ16(const IQ16* a, const IQ16* b, IQ32* out, int n);
int sp_compute_correlate_IQ32_IQ32(const IQ32* a, const IQ32* b, IQ32* out, int n);
int sp_compute_correlate_Float32_Float32(const Float32* a, const Float32* b, Float32* out, int n);

/* ============================================================
 * Utility Functions
 * ============================================================ */

int sp_init(void);
void sp_cleanup(void);
const char* sp_version(void);
int sp_set_thread_count(int threads);

#ifdef __cplusplus
}
#endif

#endif /* LIBSIGPROC_H */
