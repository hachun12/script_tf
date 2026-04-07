"""
中間表示層 (Intermediate Representation)

所有品牌的劇本都會先轉換為這個統一格式，
再從 IR 生成目標品牌的劇本。類似編譯器的 IR 概念。

座標單位統一：
  - 線性: mm
  - 角度: deg
  - 線性速度: mm/s
  - 角速度: deg/s
  - 加速度: mm/s²
  - 時間: ms
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MotionType(Enum):
    """運動類型"""
    JOINT = "joint"          # 關節運動 (PTP)
    LINEAR = "linear"        # 直線運動 (LIN)
    CIRCULAR = "circular"    # 圓弧運動 (CIRC)


class BlendMode(Enum):
    """過渡模式"""
    FINE = "fine"            # 精確定位（到點停止）
    CONTINUOUS = "continuous" # 連續過渡（不停頓）


class IOType(Enum):
    """I/O 類型"""
    DIGITAL = "digital"
    ANALOG = "analog"


class SignalEdge(Enum):
    """信號邊緣"""
    HIGH = True
    LOW = False


# ──────────────────────────────────────────────
# 座標與位置
# ──────────────────────────────────────────────

@dataclass
class CartesianPose:
    """笛卡爾座標位置"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0   # 繞 X 軸旋轉 (deg)
    ry: float = 0.0   # 繞 Y 軸旋轉 (deg)
    rz: float = 0.0   # 繞 Z 軸旋轉 (deg)


@dataclass
class JointPose:
    """關節角度位置"""
    joints: list[float] = field(default_factory=list)  # 各軸角度 (deg)


@dataclass
class Position:
    """通用位置：可以是笛卡爾或關節座標，或具名點位"""
    cartesian: Optional[CartesianPose] = None
    joint: Optional[JointPose] = None
    name: Optional[str] = None  # 具名點位 (如 P[1], p1 等)


# ──────────────────────────────────────────────
# IR 動作節點
# ──────────────────────────────────────────────

@dataclass
class IRAction:
    """所有 IR 動作的基底類別"""
    source_line: Optional[int] = None     # 原始劇本行號（用於報告）
    source_text: Optional[str] = None     # 原始劇本文字
    comment: Optional[str] = None         # 註解


@dataclass
class MoveAction(IRAction):
    """移動動作"""
    motion_type: MotionType = MotionType.LINEAR
    target: Position = field(default_factory=Position)
    velocity: Optional[float] = None         # mm/s 或 deg/s
    velocity_percent: Optional[float] = None # 百分比速度 (0-100)
    acceleration: Optional[float] = None     # mm/s²
    blend_mode: BlendMode = BlendMode.FINE
    blend_radius: Optional[float] = None     # mm (連續過渡時的圓角半徑)
    # 圓弧運動的中間點
    via_point: Optional[Position] = None


@dataclass
class SetIOAction(IRAction):
    """設定 I/O 輸出"""
    io_type: IOType = IOType.DIGITAL
    port: int = 0
    value: bool | float = False  # digital: bool, analog: float


@dataclass
class WaitIOAction(IRAction):
    """等待 I/O 輸入"""
    io_type: IOType = IOType.DIGITAL
    port: int = 0
    value: bool | float = True
    timeout: Optional[float] = None  # ms, None = 無限等待


@dataclass
class WaitTimeAction(IRAction):
    """等待指定時間"""
    duration: float = 0.0  # ms


@dataclass
class SetToolAction(IRAction):
    """設定工具座標"""
    tool_id: int = 0
    name: Optional[str] = None


@dataclass
class SetBaseAction(IRAction):
    """設定基座標"""
    base_id: int = 0
    name: Optional[str] = None


@dataclass
class SetSpeedAction(IRAction):
    """設定全域速度覆寫"""
    velocity: Optional[float] = None         # mm/s
    velocity_percent: Optional[float] = None # %


@dataclass
class CommentAction(IRAction):
    """純註解行"""
    text: str = ""


@dataclass
class CallAction(IRAction):
    """呼叫子程式 / 巨集"""
    program_name: str = ""
    arguments: list[str] = field(default_factory=list)


@dataclass
class RawAction(IRAction):
    """無法解析的原始指令（保留原文，標記警告）"""
    raw_text: str = ""
    warning: str = "此指令無法自動轉換，需人工確認"


# ──────────────────────────────────────────────
# IR 劇本（完整的動作序列）
# ──────────────────────────────────────────────

@dataclass
class IRProgram:
    """完整的 IR 劇本"""
    name: str = ""
    source_brand: str = ""
    actions: list[IRAction] = field(default_factory=list)
    # 點位表：具名點位的實際座標
    positions: dict[str, Position] = field(default_factory=dict)
    # 元資料
    metadata: dict[str, str] = field(default_factory=dict)

    def add(self, action: IRAction) -> None:
        self.actions.append(action)

    @property
    def warnings(self) -> list[RawAction]:
        """取得所有無法轉換的動作"""
        return [a for a in self.actions if isinstance(a, RawAction)]

    @property
    def action_count(self) -> int:
        return len(self.actions)
