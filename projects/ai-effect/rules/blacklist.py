"""黑名单:不插桩的文件 / 函数。项目专属配置,不是框架代码。

- SKIP_FILES:按文件 basename 整文件跳过(如第三方 / 生成代码)。
- SKIP_FUNCTIONS:按函数名跳过其中的宏(如已知不需要对照的初始化函数)。
默认空——全部插桩。
"""

SKIP_FILES: list[str] = []
SKIP_FUNCTIONS: list[str] = []
