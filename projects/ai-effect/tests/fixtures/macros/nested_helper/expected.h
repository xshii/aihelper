extern int pa_dump_enabled;
typedef struct { unsigned opid; } commopheader;
#define MK_W0(x) (0x5A0000u | ((x) & 0xFFFFu))
#define hac_3r(w0, w1, w2) do { (void)(w0); (void)(w1); (void)(w2); } while (0)
static inline void _emit(commopheader* h, int ish) {
    if (pa_dump_enabled) printf("{\"kind\":\"macro\",\"macro\":\"hac_3r\",\"words\":[%u,%u,%u]}\n", (unsigned)(MK_W0(h->opid)), (unsigned)(ish), (unsigned)(0));
    hac_3r(MK_W0(h->opid), ish, 0);
}
static inline void pa_conv(commopheader* h, int ish) {
    _emit(h, ish);
}
