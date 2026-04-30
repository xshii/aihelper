/*
 * securec.h — 安全 C 库 mock 实现（参考 Huawei securec / SafeC 接口）.
 *
 * 嵌入工程已有真 securec 库则替换本头；mock 仅给 DUT/stub_cpu demo 编译用。
 *
 * 真 securec 接口约定：
 *   - 返回 0 (EOK) 表示成功；非零 errno 表示参数错（NULL / 越界 / 重叠）
 *   - 越界由 destSize 校验，比标准 memcpy/memset 多一层防御
 *
 * mock 实现借用标准 <string.h> 提供功能；嵌入工程 link 真 securec 后
 * 这些 inline 会被覆盖（或本头被工程版替换）。
 */

#ifndef SECUREC_H
#define SECUREC_H

#include <stdint.h>
#include <stddef.h>

/* mock 借用标准库；真 securec 实现自带，无此 include */
#include <string.h>

#ifndef EOK
#  define EOK 0
#endif

static inline int memset_sp(void *dest, size_t destSize, int c, size_t count)
{
    if (dest == NULL || count > destSize) {
        return -1;
    }
    (void)memset(dest, c, count);
    return EOK;
}

static inline int memcpy_sp(void *dest, size_t destSize, const void *src, size_t count)
{
    if (dest == NULL || src == NULL || count > destSize) {
        return -1;
    }
    (void)memcpy(dest, src, count);
    return EOK;
}

static inline int strcpy_sp(char *dest, size_t destSize, const char *src)
{
    if (dest == NULL || src == NULL || destSize == 0u) {
        return -1;
    }
    size_t n = 0u;
    while (n + 1u < destSize && src[n] != '\0') {
        dest[n] = src[n];
        n++;
    }
    dest[n] = '\0';
    return (src[n] == '\0') ? EOK : -1;
}

/* 清零宏 — codestyle § 6.1：带类型大小校验，比裸 memset 安全 */
#define CLEAR_STRU(stru)    (void)memset_sp(&(stru), sizeof(stru), 0, sizeof(stru))
#define CLEAR_ARRAY(arr)    (void)memset_sp((arr), sizeof(arr), 0, sizeof(arr))

#endif /* SECUREC_H */
