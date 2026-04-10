/* PURPOSE: 最小 ELF 解析器 — 只読取 section header，找到 .debug_* 段
 * PATTERN: mmap + 偏移計算，零拷貝読取
 * FOR: 弱 AI 参考如何从零解析 ELF 格式 */

#ifndef DSC_ELF_READER_H
#define DSC_ELF_READER_H

#include "../util/types.h"

/* ELF section descriptor */
typedef struct {
    const char *name;       /* section name (points into mapped file) */
    const UINT8 *data;      /* section data pointer (points into mapped file) */
    UINT32 size;            /* section size in bytes */
} elf_section_t;

/* Mapped ELF file handle */
typedef struct {
    int fd;
    UINT8 *map;             /* mmap'd file content */
    UINT32 map_size;
    int is_64bit;           /* 1 = ELF64, 0 = ELF32 */
    int is_big_endian;      /* 1 = big, 0 = little */
    elf_section_t *sections;
    UINT32 section_count;
    UINT8 address_size;     /* 4 or 8 */
} elf_file_t;

/* Open and parse ELF headers. Returns 0 on success. */
int elf_open(elf_file_t *elf, const char *path);

/* Close and unmap. */
void elf_close(elf_file_t *elf);

/* Find a section by name. Returns NULL if not found. */
const elf_section_t *elf_find_section(const elf_file_t *elf, const char *name);

#endif /* DSC_ELF_READER_H */
