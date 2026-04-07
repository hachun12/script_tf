"""
品牌解析器基底類別與通用解析器

- BrandParser: 所有品牌解析器的抽象介面
- GenericParser: 基於 YAML 定義檔的通用解析器（適用簡單品牌）
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from core.ir import (
    BlendMode,
    CartesianPose,
    CallAction,
    CommentAction,
    IOType,
    IRAction,
    IRProgram,
    JointPose,
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


class BrandParser(ABC):
    """品牌解析器抽象介面"""

    @abstractmethod
    def parse(self, script: str, program_name: str = "") -> IRProgram:
        """將原始劇本轉換為 IR 程式"""
        ...

    @abstractmethod
    def can_parse(self, script: str) -> bool:
        """判斷此解析器是否能處理給定的劇本"""
        ...


class GenericParser(BrandParser):
    """
    基於 YAML 定義檔的通用解析器。

    從 definition.yaml 的 commands 區段讀取 pattern，
    自動編譯為正則表達式進行匹配。
    適用於語法規律、一對一映射的品牌。
    """

    # IR 動作類型對應到的工廠方法
    ACTION_BUILDERS = {
        "move_joint": "_build_move_joint",
        "move_linear": "_build_move_linear",
        "move_circular": "_build_move_circular",
        "set_digital_output": "_build_set_do",
        "set_analog_output": "_build_set_ao",
        "wait_digital_input": "_build_wait_di",
        "wait_analog_input": "_build_wait_ai",
        "wait_time": "_build_wait_time",
        "set_tool": "_build_set_tool",
        "set_base": "_build_set_base",
        "set_speed": "_build_set_speed",
        "call_program": "_build_call",
        "comment": "_build_comment",
    }

    def __init__(self, definition: dict[str, Any]) -> None:
        self.brand = definition.get("brand", "Unknown")
        self.commands = definition.get("commands", {})
        self.units = definition.get("units", {})
        self.comment_prefix = definition.get("comment_prefix", "//")
        # 預編譯正則
        self._compiled_patterns: list[tuple[str, str, re.Pattern]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """將 YAML 中的 pattern 轉為正則表達式"""
        for cmd_name, cmd_def in self.commands.items():
            pattern_str = cmd_def.get("pattern", "")
            ir_action = cmd_def.get("ir_action", cmd_name)
            if not pattern_str:
                continue
            # 將 {var_name} 轉為具名捕獲群組
            regex_str = re.sub(
                r"\{(\w+)\}",
                r"(?P<\1>[^,\\s)]+)",
                re.escape(pattern_str).replace(r"\{", "{").replace(r"\}", "}")
            )
            # 重新處理：先 escape 整個 pattern，再還原 named groups
            regex_str = pattern_str
            # 轉義正則特殊字元（但保留 {var} 佔位符）
            parts = re.split(r"(\{[^}]+\})", regex_str)
            built = []
            for part in parts:
                if part.startswith("{") and part.endswith("}"):
                    var_name = part[1:-1]
                    built.append(f"(?P<{var_name}>[^,)\\s]+)")
                else:
                    built.append(re.escape(part))
            regex_str = "".join(built)
            try:
                compiled = re.compile(regex_str)
                self._compiled_patterns.append((cmd_name, ir_action, compiled))
            except re.error:
                pass  # 跳過無效的 pattern

    def can_parse(self, script: str) -> bool:
        """嘗試匹配前幾行來判斷是否為此品牌"""
        lines = script.strip().splitlines()[:20]
        matches = 0
        for line in lines:
            for _, _, pattern in self._compiled_patterns:
                if pattern.search(line.strip()):
                    matches += 1
                    break
        return matches >= 2  # 至少匹配 2 行才算

    def parse(self, script: str, program_name: str = "") -> IRProgram:
        program = IRProgram(name=program_name, source_brand=self.brand)
        for line_num, line in enumerate(script.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            # 檢查註解
            if stripped.startswith(self.comment_prefix):
                text = stripped[len(self.comment_prefix):].strip()
                program.add(CommentAction(
                    source_line=line_num, source_text=line, text=text
                ))
                continue
            # 嘗試匹配所有已知 pattern
            action = self._try_match(stripped, line_num, line)
            program.add(action)
        return program

    def _try_match(self, stripped: str, line_num: int, raw_line: str) -> IRAction:
        """嘗試用所有 pattern 匹配一行指令"""
        for cmd_name, ir_action, pattern in self._compiled_patterns:
            m = pattern.search(stripped)
            if m:
                builder = self.ACTION_BUILDERS.get(ir_action)
                if builder and hasattr(self, builder):
                    return getattr(self, builder)(
                        m.groupdict(), line_num, raw_line, cmd_name
                    )
        # 無法匹配 → 標記為 RawAction
        return RawAction(
            source_line=line_num,
            source_text=raw_line,
            raw_text=stripped,
        )

    # ── 動作建構方法 ──

    def _build_move_joint(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> MoveAction:
        return MoveAction(
            source_line=line_num,
            source_text=raw,
            motion_type=MotionType.JOINT,
            target=self._extract_position(groups),
            velocity=self._to_float(groups.get("v")),
            velocity_percent=self._to_float(groups.get("speed")),
            blend_mode=self._extract_blend(groups),
            blend_radius=self._to_float(groups.get("blend")),
        )

    def _build_move_linear(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> MoveAction:
        return MoveAction(
            source_line=line_num,
            source_text=raw,
            motion_type=MotionType.LINEAR,
            target=self._extract_position(groups),
            velocity=self._to_float(groups.get("v")),
            velocity_percent=self._to_float(groups.get("speed")),
            blend_mode=self._extract_blend(groups),
            blend_radius=self._to_float(groups.get("blend")),
        )

    def _build_move_circular(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> MoveAction:
        return MoveAction(
            source_line=line_num,
            source_text=raw,
            motion_type=MotionType.CIRCULAR,
            target=self._extract_position(groups),
            velocity=self._to_float(groups.get("v")),
        )

    def _build_set_do(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> SetIOAction:
        value_raw = groups.get("value", "0")
        # 處理品牌特有的值映射 (ON/OFF, TRUE/FALSE, 1/0)
        cmd_def = self.commands.get(cmd, {})
        value_map = cmd_def.get("value_map", {})
        if value_raw in value_map:
            value = bool(value_map[value_raw])
        else:
            value = value_raw.upper() in ("ON", "TRUE", "1")
        return SetIOAction(
            source_line=line_num,
            source_text=raw,
            io_type=IOType.DIGITAL,
            port=int(groups.get("port", 0)),
            value=value,
        )

    def _build_set_ao(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> SetIOAction:
        return SetIOAction(
            source_line=line_num,
            source_text=raw,
            io_type=IOType.ANALOG,
            port=int(groups.get("port", 0)),
            value=self._to_float(groups.get("value")) or 0.0,
        )

    def _build_wait_di(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> WaitIOAction:
        value_raw = groups.get("value", "1")
        value = value_raw.upper() in ("ON", "TRUE", "1")
        return WaitIOAction(
            source_line=line_num,
            source_text=raw,
            io_type=IOType.DIGITAL,
            port=int(groups.get("port", 0)),
            value=value,
            timeout=self._to_float(groups.get("timeout")),
        )

    def _build_wait_ai(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> WaitIOAction:
        return WaitIOAction(
            source_line=line_num,
            source_text=raw,
            io_type=IOType.ANALOG,
            port=int(groups.get("port", 0)),
            value=self._to_float(groups.get("value")) or 0.0,
            timeout=self._to_float(groups.get("timeout")),
        )

    def _build_wait_time(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> WaitTimeAction:
        duration = self._to_float(groups.get("time")) or 0.0
        # 統一為 ms
        time_unit = self.units.get("time", "ms")
        if time_unit == "s":
            duration *= 1000
        return WaitTimeAction(
            source_line=line_num, source_text=raw, duration=duration
        )

    def _build_set_tool(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> SetToolAction:
        return SetToolAction(
            source_line=line_num,
            source_text=raw,
            tool_id=int(groups.get("id", 0)),
            name=groups.get("name"),
        )

    def _build_set_base(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> SetBaseAction:
        return SetBaseAction(
            source_line=line_num,
            source_text=raw,
            base_id=int(groups.get("id", 0)),
            name=groups.get("name"),
        )

    def _build_set_speed(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> SetSpeedAction:
        return SetSpeedAction(
            source_line=line_num,
            source_text=raw,
            velocity=self._to_float(groups.get("v")),
            velocity_percent=self._to_float(groups.get("speed")),
        )

    def _build_call(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> CallAction:
        return CallAction(
            source_line=line_num,
            source_text=raw,
            program_name=groups.get("name", ""),
        )

    def _build_comment(
        self, groups: dict, line_num: int, raw: str, cmd: str
    ) -> CommentAction:
        return CommentAction(
            source_line=line_num,
            source_text=raw,
            text=groups.get("text", ""),
        )

    # ── 輔助方法 ──

    @staticmethod
    def _extract_position(groups: dict) -> Position:
        """從匹配群組中提取位置資訊"""
        name = groups.get("point") or groups.get("point_id")
        if name:
            return Position(name=str(name))
        x = GenericParser._to_float(groups.get("x"))
        y = GenericParser._to_float(groups.get("y"))
        z = GenericParser._to_float(groups.get("z"))
        if x is not None:
            return Position(cartesian=CartesianPose(
                x=x or 0, y=y or 0, z=z or 0,
                rx=GenericParser._to_float(groups.get("rx")) or 0,
                ry=GenericParser._to_float(groups.get("ry")) or 0,
                rz=GenericParser._to_float(groups.get("rz")) or 0,
            ))
        j_vals = [GenericParser._to_float(groups.get(f"j{i}")) for i in range(1, 7)]
        if any(v is not None for v in j_vals):
            return Position(joint=JointPose(joints=[v or 0 for v in j_vals]))
        return Position(name=groups.get("target", "unknown"))

    @staticmethod
    def _extract_blend(groups: dict) -> BlendMode:
        blend_str = groups.get("blend_mode", "").upper()
        if blend_str in ("FINE", "fine"):
            return BlendMode.FINE
        return BlendMode.CONTINUOUS if blend_str else BlendMode.FINE

    @staticmethod
    def _to_float(val: str | None) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
