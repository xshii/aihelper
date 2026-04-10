/* PURPOSE: 基于文本命令协议的传输层共享逻辑
 * PATTERN: Template Method — 提供协议框架，具体 IO 由子类通过函数指针注入
 * FOR: 弱 AI 参考如何消除 telnet/serial 的协议重复代码 */

#ifndef DSC_TRANSPORT_CMDLINE_H
#define DSC_TRANSPORT_CMDLINE_H

#include "transport.h"
#include <stddef.h>
#include <sys/types.h>

/* ---------- 底层 IO 回调 ---------- */

/* 子类实现这两个函数，注入到 cmdline 层：
 *   io_send: 发送 len 字节到 fd，返回实际发送字节数（<0 = 错误）
 *   io_recv: 从 fd 接收 1 字节到 *out_char，返回 1 成功、0 EOF、<0 错误 */
typedef INT32 (*DscCmdlineSendFn)(int fd, const void *buf, UINT32 len);
typedef INT32 (*DscCmdlineRecvFn)(int fd, char *out_char);

/* ---------- 命令行传输基类 ---------- */

/* 嵌入到 telnet/serial 的私有 struct 中（不是第一个成员，
 * 而是放在 DscTransport base 之后） */
typedef struct {
    int                   fd;         /* 活跃的文件描述符，-1 = 未连接 */
    int                   timeout_ms;
    DscCmdlineSendFn   io_send;
    DscCmdlineRecvFn   io_recv;
} DscCmdlineCtx;

/* ---------- 共享 IO 函数 ---------- */

/* 重试发送直到全部写出 */
int DscCmdlineSendAll(DscCmdlineCtx *ctx, const void *buf, UINT32 len);

/* 读一行（到 \n 为止），去除 \r\n */
int DscCmdlineRecvLine(DscCmdlineCtx *ctx, char *buf, UINT32 buf_len);

/* 发命令 + 收一行响应 */
int DscCmdlineExec(DscCmdlineCtx *ctx, const char *cmd,
                     char *resp, UINT32 resp_len);

/* 标准 "md" 协议读内存 */
int DscCmdlineMemRead(DscCmdlineCtx *ctx, UINT64 addr,
                         void *buf, UINT32 len);

/* 标准 "mw" 协议写内存 */
int DscCmdlineMemWrite(DscCmdlineCtx *ctx, UINT64 addr,
                          const void *buf, UINT32 len);

#endif /* DSC_TRANSPORT_CMDLINE_H */
