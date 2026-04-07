"""
Ruby (PMC 自研控制器) 自訂生成器

將 IR 動作轉換為 Ruby Script 格式。

Ruby 語法特點：
- MOVE_POINT P<n> VEL=<v> ACC=<a> CONT=<c> BASE=<b> TOOL=<t>
- MOVE_LINE P<n> VEL=<v> ACC=<a> CONT=<c> BASE=<b>
- MOVE_CIRCLE P<via> P<end> VEL=<v> THETA=<deg>
- IO OUT<module>[<bit>]=ON|OFF
- WAITFOR IN<module>[<bit>]==ON|OFF
- DELAY <ms>
- CALL <name>
"""

from __future__ import annotations

from core.emitter_base import BrandEmitter
from core.ir import (
    BlendMode,
    CallAction,
    CommentAction,
    IOType,
    IRAction,
    IRProgram,
    MoveAction,
    MotionType,
    RawAction,
    SetBaseAction,
    SetIOAction,
    SetSpeedAction,
    SetToolAction,
    WaitIOAction,
    WaitTimeAction,
)


class RubyEmitter(BrandEmitter):
    """Ruby 控制器劇本生成器"""

    def emit(self, program: IRProgram) -> str:
        lines: list[str] = []
        for action in program.actions:
            line = self._emit_action(action)
            lines.append(line)
        return "\n".join(lines)

    def _emit_action(self, action: IRAction) -> str:
        if isinstance(action, CommentAction):
            return f"// {action.text}"

        if isinstance(action, RawAction):
            return f"// [WARNING] {action.raw_text} -- {action.warning}"

        if isinstance(action, MoveAction):
            return self._emit_move(action)

        if isinstance(action, SetIOAction):
            return self._emit_io(action)

        if isinstance(action, WaitIOAction):
            return self._emit_wait_io(action)

        if isinstance(action, WaitTimeAction):
            return self._emit_delay(action)

        if isinstance(action, SetToolAction):
            # Ruby 中 TOOL 是運動指令的次要參數，獨立出現時用註解說明
            return f"// Set TOOL={action.tool_id} (apply to next MOVE command)"

        if isinstance(action, SetBaseAction):
            return f"// Set BASE={action.base_id} (apply to next MOVE command)"

        if isinstance(action, SetSpeedAction):
            return f"// Set VEL={action.velocity or action.velocity_percent} (apply to next MOVE command)"

        if isinstance(action, CallAction):
            return f"CALL  {action.program_name}"

        return f"// [UNKNOWN] {action}"

    def _emit_move(self, action: MoveAction) -> str:
        """生成運動指令"""
        parts: list[str] = []

        # 標頭
        is_relative = action.comment and "[RELATIVE]" in (action.comment or "")
        if action.motion_type == MotionType.JOINT:
            header = "MOVE_POINT_REL" if is_relative else "MOVE_POINT"
        elif action.motion_type == MotionType.LINEAR:
            header = "MOVE_LINE_REL" if is_relative else "MOVE_LINE"
        else:
            header = "MOVE_CIRCLE"
        parts.append(header)

        # 主要參數：圓弧需要 via_point
        if action.motion_type == MotionType.CIRCULAR and action.via_point:
            via_name = action.via_point.name or "P0"
            parts.append(f" {via_name}")

        # 目標位置
        pos = action.target
        if pos.name:
            parts.append(f" {pos.name}")
        elif pos.cartesian:
            c = pos.cartesian
            tcp_parts = []
            if c.x != 0: tcp_parts.append(f"TX={c.x:.2f}")
            if c.y != 0: tcp_parts.append(f"TY={c.y:.2f}")
            if c.z != 0: tcp_parts.append(f"TZ={c.z:.2f}")
            if c.rz != 0: tcp_parts.append(f"TA={c.rz:.2f}")
            if c.ry != 0: tcp_parts.append(f"TB={c.ry:.2f}")
            if c.rx != 0: tcp_parts.append(f"TC={c.rx:.2f}")
            if tcp_parts:
                parts.append("  " + "  ".join(tcp_parts))
        elif pos.joint:
            for i, val in enumerate(pos.joint.joints, start=1):
                if val != 0:
                    parts.append(f" A{i}={val:.1f}")

        # 次要參數
        if action.velocity is not None:
            parts.append(f"  VEL={action.velocity:.0f}")
        if action.acceleration is not None:
            parts.append(f"  ACC={action.acceleration:.0f}")
        if action.blend_mode == BlendMode.CONTINUOUS:
            cont_val = action.blend_radius if action.blend_radius is not None else 10
            parts.append(f"  CONT={cont_val:.0f}")

        return "".join(parts)

    def _emit_io(self, action: SetIOAction) -> str:
        """生成 IO 指令"""
        if action.io_type == IOType.DIGITAL:
            # 從 port 反推 module 和 bit
            module = action.port // 100 if action.port >= 100 else 1
            bit = action.port % 100 if action.port >= 100 else action.port
            value_str = "ON" if action.value else "OFF"
            return f"IO  OUT{module}[{bit}]={value_str}"
        return f"// [ANALOG IO] port={action.port} value={action.value}"

    def _emit_wait_io(self, action: WaitIOAction) -> str:
        """生成 WAITFOR 指令"""
        if action.io_type == IOType.DIGITAL:
            module = action.port // 100 if action.port >= 100 else 1
            bit = action.port % 100 if action.port >= 100 else action.port
            value_str = "ON" if action.value else "OFF"
            return f"WAITFOR  IN{module}[{bit}]=={value_str}"
        return f"// [ANALOG WAITFOR] port={action.port} value={action.value}"

    def _emit_delay(self, action: WaitTimeAction) -> str:
        """生成 DELAY 指令（毫秒）"""
        return f"DELAY  {action.duration:.0f}"
