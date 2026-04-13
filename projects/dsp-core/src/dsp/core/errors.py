"""自定义异常体系 — 弱 AI 看类名就知道问题在哪。

每个异常类的 docstring 包含修复提示。

用法:
    from dsp.core.errors import GoldenNotAvailable, ManifestNotFound

    try:
        dsp.ops.linear(x, w, b)
    except GoldenNotAvailable:
        # 知道要 make build-golden
    except ManifestNotFound:
        # 知道要在 @register_op 的 golden_c 里加 ComputeKey
"""


class DSPError(Exception):
    """dsp 框架基础异常。"""


class GoldenNotAvailable(DSPError):
    """Golden C 未接入或未编译。

    修复:
        1. make build-golden（编译 C++ 绑定）
        2. 或确认 golden_c/ 下有 .h 文件
    """


class ManifestNotFound(DSPError):
    """manifest 中未找到匹配的 ComputeKey。

    修复:
        1. 在 @register_op 的 golden_c 参数中添加对应的 ComputeKey
        2. 或在 golden/manifest.py 的 COMPUTE 表中添加条目
        3. 确认 type_a/type_b 和 tensor 的 dsp_dtype 一致
    """


class ConventionNotFound(DSPError):
    """算子没有注册 OpConvention（不知道怎么调 C 函数）。

    修复:
        1. 在 ops/<op_name>/__init__.py 添加:
           class MyConvention(OpConvention, op="my_op"):
               def call_c_func(self, func, *inputs_np, **params): ...
        2. 或复用已有 convention（matmul/linear/layernorm）
    """


class OpNotRegistered(DSPError):
    """算子未注册。

    修复:
        1. 确认算子文件有 @register_op 装饰器
        2. 确认 ops/__init__.py 中 import 了该模块
    """


class ComputeConfigMismatch(DSPError):
    """compute config 指定的精度组合在 manifest 中不存在。

    修复:
        1. 检查 dsp.context.set_compute_config() 的参数
        2. 或在 manifest COMPUTE 表中添加对应精度的条目
    """
