/* PURPOSE: 交互式命令解释器 — 解析用户输入，分派到变量查询/函数调用/转发
 * PATTERN: Command dispatcher with pluggable command table
 * FOR: 弱 AI 参考如何构建软调的交互式 Shell */

#ifndef DSC_SHELL_H
#define DSC_SHELL_H

#include "../core/dsc.h"

/* 命令执行结果 */
typedef enum {
    DSC_SHELL_OK = 0,       /* 命令执行成功 */
    DSC_SHELL_ERROR,        /* 命令执行失败 */
    DSC_SHELL_QUIT,         /* 用户请求退出 */
    DSC_SHELL_UNKNOWN,      /* 未识别的命令 */
} DscShellResult;

/* Shell 上下文 */
typedef struct DscShell DscShell;

/* 创建 shell，绑定到一个已打开的 dsc 会话 */
DscShell *DscShellCreate(DscContext *ctx);

/* 销毁 shell */
void DscShellDestroy(DscShell *sh);

/* 执行一条命令字符串，结果输出到 out（caller 提供 buffer）
 * 返回 DscShellResult */
DscShellResult DscShellExec(DscShell *sh, const char *input,
                            char *out, UINT32 out_len);

/* 交互式循环：从 stdin 读命令，打印结果到 stdout
 * 阻塞直到用户输入 quit 或 EOF */
void DscShellLoop(DscShell *sh);

/* 通过 socket 提供交互式服务：监听 port，接受连接后进入命令循环
 * 阻塞直到连接关闭 */
int DscShellServe(DscShell *sh, int port);

#endif /* DSC_SHELL_H */
