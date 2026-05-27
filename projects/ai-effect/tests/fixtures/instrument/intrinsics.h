/* fixture 用的「系统自带」intrinsic 头:inline 函数,被用户 .c 调用。 */
typedef struct {
    unsigned opid;
    unsigned aopid;
} commopheader;

static inline void pa_conv(commopheader* h, void* in, void* out, int n) {}
static inline void pa_load(commopheader* h, void* dst, int n) {}
static inline int pa_query(commopheader* h) { return 0; }
static inline void _emit(commopheader* h) {}
