"""ConvertMixin — 值转换能力。

调 golden.convert 做实际转换。golden 不可用时报错。
"""

from __future__ import annotations


class ConvertMixin:
    """值转换：float ↔ native 格式。"""

    def convert(self, target_dtype: str):
        """类型转换。返回 self（链式）。

        Args:
            target_dtype: 目标类型名（如 "iq16", "float32"）
        """
        if target_dtype == self._dtype_name:
            return self

        import numpy as np
        import torch
        from ..golden.call import convert as golden_convert, is_available

        if not is_available():
            from ..core.errors import GoldenNotAvailable
            raise GoldenNotAvailable(
                f"convert({self._dtype_name} → {target_dtype}) 需要 golden C。"
            )

        t = self._tensor
        src = self._dtype_name
        flat_np = t.detach().cpu().float().numpy().flatten().astype(np.float32)
        out_np = golden_convert(flat_np, src, target_dtype)
        self._tensor = torch.from_numpy(out_np.copy()).reshape(t.shape)

        self._dtype_name = target_dtype
        self._log(f"convert({src} → {target_dtype})")
        return self
