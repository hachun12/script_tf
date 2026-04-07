"""
品牌生成器基底類別與通用生成器

- BrandEmitter: 所有品牌生成器的抽象介面
- GenericEmitter: 基於 YAML emit_template 的通用生成器
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from core.ir import (
    BlendMode,
    CallAction,
    CommentAction,
    IOType,
    IRAction,
    IRProgram,
    MoveAction,
    MotionType,
    Position,
    RawAction,
    SetBaseAction,
    SetIOAction,
    SetSpeedAction,
    SetToolAction,
    WaitIOAction,
    WaitTimeAction,
)


class BrandEmitter(ABC):
    """品牌生成器抽象介面"""

    @abstractmethod
    def emit(self, program: IRProgram) -> str:
        """將 IR 程式轉換為目標品牌的劇本文字"""
        ...


class GenericEmitter(BrandEmitter):
    """
    基於 YAML 定義檔的通用生成器。

    從 definition.yaml 的 commands 區段讀取 emit_template，
    用 IR 動作的欄位值填入模板來產生目標劇本。
    """

    def __init__(self, definition: dict[str, Any]) -> None:
        self.brand = definition.get("brand", "Unknown")
        self.commands = definition.get("commands", {})
        self.units = definition.get("units", {})
        self.comment_prefix = definition.get("comment_prefix", "//")
        self.file_header = definition.get("file_header", "")
        self.file_footer = definition.get("file_footer", "")
        # 建立 ir_action → template 的反向映射
        self._templates: dict[str, dict] = {}
        for cmd_name, cmd_def in self.commands.items():
            ir_action = cmd_def.get("ir_action", cmd_name)
            if "emit_template" in cmd_def:
                self._templates[ir_action] = cmd_def

    def emit(self, program: IRProgram) -> str:
        lines: list[str] = []
        if self.file_header:
            lines.append(self._render_header(program))
        for action in program.actions:
            line = self._emit_action(action)
            lines.append(line)
        if self.file_footer:
            lines.append(self.file_footer)
        return "\n".join(lines)

    def _emit_action(self, action: IRAction) -> str:
        """將單一 IR 動作轉換為目標品牌的一行指令"""
        if isinstance(action, CommentAction):
            return f"{self.comment_prefix} {action.text}"

        if isinstance(action, RawAction):
            return f"{self.comment_prefix} [WARNING] {action.raw_text} -- {action.warning}"

        if isinstance(action, MoveAction):
            return self._emit_move(action)

        if isinstance(action, SetIOAction):
            return self._emit_set_io(action)

        if isinstance(action, WaitIOAction):
            return self._emit_wait_io(action)

        if isinstance(action, WaitTimeAction):
            return self._emit_wait_time(action)

        if isinstance(action, SetToolAction):
            return self._emit_set_tool(action)

        if isinstance(action, SetBaseAction):
            return self._emit_set_base(action)

        if isinstance(action, SetSpeedAction):
            return self._emit_set_speed(action)

        if isinstance(action, CallAction):
            return self._emit_call(action)

        # 未知動作類型
        return f"{self.comment_prefix} [UNKNOWN ACTION] {action}"

    def _emit_move(self, action: MoveAction) -> str:
        # 根據運動類型找對應的 template
        type_map = {
            MotionType.JOINT: "move_joint",
            MotionType.LINEAR: "move_linear",
            MotionType.CIRCULAR: "move_circular",
        }
        ir_action_name = type_map.get(action.motion_type, "move_linear")
        template_def = self._templates.get(ir_action_name)
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] {ir_action_name}"

        template = template_def["emit_template"]
        return self._fill_template(template, self._move_vars(action, template_def))

    def _emit_set_io(self, action: SetIOAction) -> str:
        ir_name = (
            "set_digital_output" if action.io_type == IOType.DIGITAL
            else "set_analog_output"
        )
        template_def = self._templates.get(ir_name)
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] {ir_name}"

        # 處理值映射（反向：bool → 品牌格式）
        value_map = template_def.get("value_map", {})
        if value_map:
            inv_map = {v: k for k, v in value_map.items()}
            if action.io_type == IOType.DIGITAL:
                val_str = inv_map.get(1 if action.value else 0, str(action.value))
            else:
                val_str = str(action.value)
        else:
            val_str = "ON" if action.value else "OFF"

        template = template_def["emit_template"]
        return self._fill_template(template, {
            "port": str(action.port),
            "value": val_str,
        })

    def _emit_wait_io(self, action: WaitIOAction) -> str:
        ir_name = (
            "wait_digital_input" if action.io_type == IOType.DIGITAL
            else "wait_analog_input"
        )
        template_def = self._templates.get(ir_name)
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] {ir_name}"

        value_str = "ON" if action.value else "OFF"
        template = template_def["emit_template"]
        return self._fill_template(template, {
            "port": str(action.port),
            "value": value_str,
            "timeout": str(action.timeout or 0),
        })

    def _emit_wait_time(self, action: WaitTimeAction) -> str:
        template_def = self._templates.get("wait_time")
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] wait_time"

        duration = action.duration
        time_unit = self.units.get("time", "ms")
        if time_unit == "s":
            duration /= 1000

        template = template_def["emit_template"]
        return self._fill_template(template, {"time": str(duration)})

    def _emit_set_tool(self, action: SetToolAction) -> str:
        template_def = self._templates.get("set_tool")
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] set_tool"
        template = template_def["emit_template"]
        return self._fill_template(template, {"id": str(action.tool_id)})

    def _emit_set_base(self, action: SetBaseAction) -> str:
        template_def = self._templates.get("set_base")
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] set_base"
        template = template_def["emit_template"]
        return self._fill_template(template, {"id": str(action.base_id)})

    def _emit_set_speed(self, action: SetSpeedAction) -> str:
        template_def = self._templates.get("set_speed")
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] set_speed"
        template = template_def["emit_template"]
        return self._fill_template(template, {
            "v": str(action.velocity or 0),
            "speed": str(action.velocity_percent or 0),
        })

    def _emit_call(self, action: CallAction) -> str:
        template_def = self._templates.get("call_program")
        if not template_def:
            return f"{self.comment_prefix} [NO TEMPLATE] call_program"
        template = template_def["emit_template"]
        return self._fill_template(template, {"name": action.program_name})

    def _render_header(self, program: IRProgram) -> str:
        return self.file_header.replace("{name}", program.name)

    # ── 輔助方法 ──

    def _move_vars(self, action: MoveAction, template_def: dict) -> dict[str, str]:
        """從 MoveAction 提取模板變數"""
        pos = action.target
        variables: dict[str, str] = {}

        # 位置
        if pos.name:
            variables["point"] = pos.name
            variables["point_id"] = pos.name
        if pos.cartesian:
            c = pos.cartesian
            variables.update({
                "x": f"{c.x:.2f}", "y": f"{c.y:.2f}", "z": f"{c.z:.2f}",
                "rx": f"{c.rx:.2f}", "ry": f"{c.ry:.2f}", "rz": f"{c.rz:.2f}",
            })
        if pos.joint:
            for i, val in enumerate(pos.joint.joints, start=1):
                variables[f"j{i}"] = f"{val:.2f}"

        # 速度
        if action.velocity is not None:
            variables["v"] = str(int(action.velocity))
        if action.velocity_percent is not None:
            variables["speed"] = str(int(action.velocity_percent))

        # 過渡
        blend_map = template_def.get("blend_map", {})
        if action.blend_mode == BlendMode.FINE:
            variables["blend_mode"] = blend_map.get("fine", "FINE")
        else:
            variables["blend_mode"] = blend_map.get("continuous", "CNT")
        if action.blend_radius is not None:
            variables["blend"] = str(int(action.blend_radius))

        return variables

    @staticmethod
    def _fill_template(template: str, variables: dict[str, str]) -> str:
        """將模板中的 {var} 替換為實際值"""
        result = template
        for key, val in variables.items():
            result = result.replace(f"{{{key}}}", val)
        # 移除未填入的佔位符（設為空）
        result = re.sub(r"\{[^}]+\}", "", result)
        return result
