/* PURPOSE: 最小 ELF section reader — mmap 方式零拷贝解析 ELF section header
 * PATTERN: open → mmap → parse header → build section table → lookup by name
 * FOR: 弱 AI 参考如何从零实现 ELF 解析，替代 libdwarf 依赖 */

#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include "elf_reader.h"
#include "../core/dsc_errors.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* ELF constants (inline, no <elf.h> dependency)                      */
/* ------------------------------------------------------------------ */

#define ELF_MAG0      0x7f
#define ELF_MAG1      'E'
#define ELF_MAG2      'L'
#define ELF_MAG3      'F'

#define EI_CLASS      4       /* offset in e_ident: 1=32bit, 2=64bit */
#define EI_DATA       5       /* offset in e_ident: 1=LE, 2=BE */

#define ELFCLASS32    1
#define ELFCLASS64    2
#define ELFDATA2LSB   1
#define ELFDATA2MSB   2

/* Minimum ELF header size (ELF32 is 52 bytes, ELF64 is 64 bytes) */
#define ELF32_EHDR_SIZE   52
#define ELF64_EHDR_SIZE   64

/* Section header entry sizes */
#define ELF32_SHDR_SIZE   40
#define ELF64_SHDR_SIZE   64

/* ------------------------------------------------------------------ */
/* Endian-aware integer readers                                       */
/* ------------------------------------------------------------------ */

static UINT16 read_u16(const UINT8 *p, int big_endian)
{
    if (big_endian) {
        return (UINT16)((p[0] << 8) | p[1]);
    }
    return (UINT16)(p[0] | (p[1] << 8));
}

static UINT32 read_u32(const UINT8 *p, int big_endian)
{
    if (big_endian) {
        return ((UINT32)p[0] << 24) | ((UINT32)p[1] << 16)
             | ((UINT32)p[2] << 8)  | (UINT32)p[3];
    }
    return (UINT32)p[0] | ((UINT32)p[1] << 8)
         | ((UINT32)p[2] << 16) | ((UINT32)p[3] << 24);
}

static UINT64 read_u64(const UINT8 *p, int big_endian)
{
    if (big_endian) {
        return ((UINT64)read_u32(p, 1) << 32) | read_u32(p + 4, 1);
    }
    return (UINT64)read_u32(p, 0) | ((UINT64)read_u32(p + 4, 0) << 32);
}

/* ------------------------------------------------------------------ */
/* Internal: validate ELF magic bytes                                 */
/* ------------------------------------------------------------------ */

static int validate_magic(const UINT8 *map, UINT32 map_size)
{
    if (map_size < 16) {
        return DSC_ERR_ELF_FORMAT;
    }
    if (map[0] != ELF_MAG0 || map[1] != ELF_MAG1
        || map[2] != ELF_MAG2 || map[3] != ELF_MAG3) {
        DSC_LOG_ERROR("not an ELF file (bad magic)");
        return DSC_ERR_ELF_FORMAT;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: parse ELF class and endianness                           */
/* ------------------------------------------------------------------ */

static int parse_ident(elf_file_t *elf)
{
    UINT8 ei_class = elf->map[EI_CLASS];
    UINT8 ei_data  = elf->map[EI_DATA];

    if (ei_class == ELFCLASS64) {
        elf->is_64bit = 1;
        elf->address_size = 8;
    } else if (ei_class == ELFCLASS32) {
        elf->is_64bit = 0;
        elf->address_size = 4;
    } else {
        DSC_LOG_ERROR("unsupported ELF class: %u", (unsigned)ei_class);
        return DSC_ERR_ELF_FORMAT;
    }

    if (ei_data == ELFDATA2MSB) {
        elf->is_big_endian = 1;
    } else if (ei_data == ELFDATA2LSB) {
        elf->is_big_endian = 0;
    } else {
        DSC_LOG_ERROR("unsupported ELF data encoding: %u", (unsigned)ei_data);
        return DSC_ERR_ELF_FORMAT;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: read section header table parameters from ELF header     */
/* ------------------------------------------------------------------ */

static int read_sh_params(const elf_file_t *elf, UINT64 *sh_off,
                          UINT16 *sh_entsize, UINT16 *sh_num,
                          UINT16 *sh_strndx)
{
    int be = elf->is_big_endian;
    const UINT8 *h = elf->map;

    if (elf->is_64bit) {
        if (elf->map_size < ELF64_EHDR_SIZE) {
            return DSC_ERR_ELF_FORMAT;
        }
        *sh_off     = read_u64(h + 40, be);
        *sh_entsize = read_u16(h + 58, be);
        *sh_num     = read_u16(h + 60, be);
        *sh_strndx  = read_u16(h + 62, be);
    } else {
        if (elf->map_size < ELF32_EHDR_SIZE) {
            return DSC_ERR_ELF_FORMAT;
        }
        *sh_off     = read_u32(h + 32, be);
        *sh_entsize = read_u16(h + 46, be);
        *sh_num     = read_u16(h + 48, be);
        *sh_strndx  = read_u16(h + 50, be);
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: read one section header entry fields                     */
/* ------------------------------------------------------------------ */

static void read_shdr_entry(const UINT8 *entry, int is_64, int be,
                            UINT32 *sh_name, UINT64 *sh_offset,
                            UINT64 *sh_size)
{
    *sh_name = read_u32(entry + 0, be);

    if (is_64) {
        *sh_offset = read_u64(entry + 24, be);
        *sh_size   = read_u64(entry + 32, be);
    } else {
        *sh_offset = read_u32(entry + 16, be);
        *sh_size   = read_u32(entry + 20, be);
    }
}

/* ------------------------------------------------------------------ */
/* Internal: populate elf->sections array                             */
/* ------------------------------------------------------------------ */

static int populate_sections(elf_file_t *elf, UINT64 sh_off,
                             UINT16 sh_entsize, UINT16 sh_num,
                             const char *strtab, UINT64 strtab_size)
{
    elf->sections = calloc(sh_num, sizeof(elf_section_t));
    if (!elf->sections) {
        DSC_LOG_ERROR("failed to allocate section array");
        return DSC_ERR_NOMEM;
    }
    elf->section_count = sh_num;

    for (UINT32 i = 0; i < sh_num; i++) {
        const UINT8 *entry = elf->map + sh_off + (UINT64)sh_entsize * i;
        UINT32 name_off;
        UINT64 sec_offset, sec_size;
        read_shdr_entry(entry, elf->is_64bit, elf->is_big_endian,
                        &name_off, &sec_offset, &sec_size);

        if (name_off < strtab_size) {
            elf->sections[i].name = strtab + name_off;
        } else {
            elf->sections[i].name = "";
        }

        if (sec_offset + sec_size <= elf->map_size) {
            elf->sections[i].data = elf->map + sec_offset;
            elf->sections[i].size = (UINT32)sec_size;
        } else {
            elf->sections[i].data = NULL;
            elf->sections[i].size = 0;
        }
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: locate .shstrtab and build section descriptors           */
/* ------------------------------------------------------------------ */

static int build_section_table(elf_file_t *elf, UINT64 sh_off,
                               UINT16 sh_entsize, UINT16 sh_num,
                               UINT16 sh_strndx)
{
    UINT64 table_end = sh_off + (UINT64)sh_entsize * sh_num;
    if (table_end > elf->map_size) {
        DSC_LOG_ERROR("section header table extends past EOF");
        return DSC_ERR_ELF_FORMAT;
    }

    /* Read .shstrtab entry to get name string table */
    if (sh_strndx >= sh_num) {
        DSC_LOG_ERROR("shstrndx %u >= shnum %u", sh_strndx, sh_num);
        return DSC_ERR_ELF_FORMAT;
    }

    const UINT8 *strtab_entry = elf->map + sh_off + (UINT64)sh_entsize * sh_strndx;
    UINT32 strtab_name_off;
    UINT64 strtab_offset, strtab_size;
    read_shdr_entry(strtab_entry, elf->is_64bit, elf->is_big_endian,
                    &strtab_name_off, &strtab_offset, &strtab_size);

    if (strtab_offset + strtab_size > elf->map_size) {
        DSC_LOG_ERROR(".shstrtab extends past EOF");
        return DSC_ERR_ELF_FORMAT;
    }
    const char *strtab = (const char *)(elf->map + strtab_offset);

    return populate_sections(elf, sh_off, sh_entsize, sh_num,
                             strtab, strtab_size);
}

/* ------------------------------------------------------------------ */
/* Internal: open file and mmap it                                    */
/* ------------------------------------------------------------------ */

static int mmap_file(elf_file_t *elf, const char *path)
{
    elf->fd = open(path, O_RDONLY);
    if (elf->fd < 0) {
        DSC_LOG_ERROR("cannot open '%s'", path);
        return DSC_ERR_ELF_OPEN;
    }

    struct stat st;
    if (fstat(elf->fd, &st) != 0 || st.st_size <= 0) {
        DSC_LOG_ERROR("cannot stat '%s'", path);
        close(elf->fd);
        elf->fd = -1;
        return DSC_ERR_ELF_OPEN;
    }
    elf->map_size = (UINT32)st.st_size;

    elf->map = mmap(NULL, elf->map_size, PROT_READ, MAP_PRIVATE, elf->fd, 0);
    if (elf->map == MAP_FAILED) {
        DSC_LOG_ERROR("mmap failed for '%s'", path);
        elf->map = NULL;
        close(elf->fd);
        elf->fd = -1;
        return DSC_ERR_ELF_OPEN;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

int elf_open(elf_file_t *elf, const char *path)
{
    memset(elf, 0, sizeof(*elf));
    elf->fd = -1;

    int rc = mmap_file(elf, path);
    if (rc != DSC_OK) {
        return rc;
    }

    rc = validate_magic(elf->map, elf->map_size);
    if (rc != DSC_OK) {
        elf_close(elf);
        return rc;
    }

    rc = parse_ident(elf);
    if (rc != DSC_OK) {
        elf_close(elf);
        return rc;
    }

    UINT64 sh_off;
    UINT16 sh_entsize, sh_num, sh_strndx;
    rc = read_sh_params(elf, &sh_off, &sh_entsize, &sh_num, &sh_strndx);
    if (rc != DSC_OK) {
        elf_close(elf);
        return rc;
    }

    rc = build_section_table(elf, sh_off, sh_entsize, sh_num, sh_strndx);
    if (rc != DSC_OK) {
        elf_close(elf);
        return rc;
    }

    DSC_LOG_DEBUG("ELF opened: %s (%s, %s-endian, %u sections)",
                  path, elf->is_64bit ? "64-bit" : "32-bit",
                  elf->is_big_endian ? "big" : "little",
                  elf->section_count);
    return DSC_OK;
}

void elf_close(elf_file_t *elf)
{
    if (elf->sections) {
        free(elf->sections);
        elf->sections = NULL;
    }
    if (elf->map) {
        munmap(elf->map, elf->map_size);
        elf->map = NULL;
    }
    if (elf->fd >= 0) {
        close(elf->fd);
        elf->fd = -1;
    }
    elf->section_count = 0;
}

const elf_section_t *elf_find_section(const elf_file_t *elf, const char *name)
{
    for (UINT32 i = 0; i < elf->section_count; i++) {
        if (elf->sections[i].name && strcmp(elf->sections[i].name, name) == 0) {
            return &elf->sections[i];
        }
    }
    return NULL;
}
