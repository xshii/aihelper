"""proto-test-env — FPGA 原型测试环境参考实现 (06b)."""
from __future__ import annotations

__version__ = "0.0.1"

from .block import (
    BitFieldMixin as BitFieldMixin,
    Block as Block,
    Composite as Composite,
    DEFAULT_MAX_PAYLOAD_PER_CHUNK as DEFAULT_MAX_PAYLOAD_PER_CHUNK,
    DdrBlockHeader as DdrBlockHeader,
    DdrChunk as DdrChunk,
    DdrConfig as DdrConfig,
    DdrSender as DdrSender,
    EndBlock as EndBlock,
    HeaderBlock as HeaderBlock,
    RawBlock as RawBlock,
    TensorBlock as TensorBlock,
    fragment_payload as fragment_payload,
    pack as pack,
)
from .memory import (
    CompareEntry as CompareEntry,
    Datatype as Datatype,
    MemAccessAPI as MemAccessAPI,
    MemPort as MemPort,
    StructDef as StructDef,
    SymbolMap as SymbolMap,
    register_struct as register_struct,
)
from .compare import (
    CompareBufOverflow as CompareBufOverflow,
    CompareResult as CompareResult,
    MemoryCompareDriver as MemoryCompareDriver,
    run_compare_round as run_compare_round,
    soft_compare as soft_compare,
)
from .errors import (
    AutotestError as AutotestError,
    AutotestTimeoutError as AutotestTimeoutError,
    CommError as CommError,
    DataIntegrityError as DataIntegrityError,
    ERR_BUFFER_REGISTRY_FULL as ERR_BUFFER_REGISTRY_FULL,
    ERR_COMPARE_BUF_OVERFLOW as ERR_COMPARE_BUF_OVERFLOW,
    ERR_DATA_CRC_MISMATCH as ERR_DATA_CRC_MISMATCH,
    ERR_ILLEGAL_TRANSITION as ERR_ILLEGAL_TRANSITION,
    ERR_OK as ERR_OK,
    ERR_SWITCH_COMPARE_DENIED as ERR_SWITCH_COMPARE_DENIED,
    ERR_SYMBOL_NOT_FOUND as ERR_SYMBOL_NOT_FOUND,
    ERR_TIMEOUT_TRANSIENT as ERR_TIMEOUT_TRANSIENT,
    HardwareFaultError as HardwareFaultError,
    IllegalStateError as IllegalStateError,
    StubCpuError as StubCpuError,
    SymbolNotFoundError as SymbolNotFoundError,
    TransientError as TransientError,
    code_to_exception as code_to_exception,
)
from .domain import (
    Baseline as Baseline,
    Case as Case,
    CompareMode as CompareMode,
    ComparePath as ComparePath,
    HpTrigger as HpTrigger,
    ResultOut as ResultOut,
    Stage as Stage,
    SwitchStrategy as SwitchStrategy,
    Verdict as Verdict,
    Via as Via,
)
from .retry import (
    retryable as retryable,
    total_backoff as total_backoff,
)
from .buffer_registry import (
    BufferEntry as BufferEntry,
    BufferKind as BufferKind,
    BufferRegistry as BufferRegistry,
    BufferRegistryFull as BufferRegistryFull,
)
from .lifecycle import (
    LifecycleEvent as LifecycleEvent,
    LifecycleFSM as LifecycleFSM,
    ModelState as ModelState,
)
from .adapters import (
    DummyAdapter as DummyAdapter,
    FpgaAdapter as FpgaAdapter,
    L6APort as L6APort,
    Mechanism as Mechanism,
    MemoryMechanism as MemoryMechanism,
    MemoryPort as MemoryPort,
    MessageMechanism as MessageMechanism,
    PlatformAdapter as PlatformAdapter,
)
