typedef struct { unsigned opid; } commopheader;
#define hac_3r(w0, w1, w2) do { (void)(w0); (void)(w1); (void)(w2); } while (0)
#define hac_2r(w0, w1) do { (void)(w0); (void)(w1); } while (0)
static inline void pa_conv(commopheader* h, int ish) {
    hac_3r(1, 2, 3);
    hac_2r(ish, 0);
}
