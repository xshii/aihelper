extern int pa_dump_enabled;
typedef struct { unsigned opid; } commopheader;
#define hac_3r(w0, w1, w2) do { (void)(w0); (void)(w1); (void)(w2); } while (0)
#define hac_2r(w0, w1) do { (void)(w0); (void)(w1); } while (0)
static inline void pa_conv(commopheader* h, int ish) {
    if (pa_dump_enabled) printf("{\"kind\":\"macro\",\"macro\":\"hac_3r\",\"words\":[%u,%u,%u]}\n", (unsigned)(1), (unsigned)(2), (unsigned)(3));
    hac_3r(1, 2, 3);
    if (pa_dump_enabled) printf("{\"kind\":\"macro\",\"macro\":\"hac_2r\",\"words\":[%u,%u]}\n", (unsigned)(ish), (unsigned)(0));
    hac_2r(ish, 0);
}
