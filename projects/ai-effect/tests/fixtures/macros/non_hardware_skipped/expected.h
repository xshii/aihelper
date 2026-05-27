extern int pa_dump_enabled;
typedef struct { unsigned opid; } commopheader;
#define MK_W0(x) ((x) & 0xFFFFu)
#define hac_3r(w0, w1, w2) do { (void)(w0); (void)(w1); (void)(w2); } while (0)
#define other_macro(a) (a)
static inline void pa_conv(commopheader* h, int ish) {
    int z = other_macro(ish);
    if (pa_dump_enabled) printf("{\"kind\":\"macro\",\"macro\":\"hac_3r\",\"words\":[%u,%u,%u]}\n", (unsigned)(MK_W0(h->opid)), (unsigned)(z), (unsigned)(0));
    hac_3r(MK_W0(h->opid), z, 0);
}
