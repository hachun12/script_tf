"""
Ruby (PMC 自研控制器) 自訂解析器

Ruby 語法特點：
- 指令格式: 標頭 + 主要參數 + 次要參數（空白/Tab 分隔）
- 運動指令支援多種主要參數格式: P<int>, A<int>=<double>, T<X|Y|Z|A|B|C>=<double>
- I/O 格式: IO OUT<module>[<bit>]=ON|OFF
- 等待格式: WAITFOR IN<module>[<bit>]==ON|OFF
- 延遲單位: ms
- 流程控制: LOOP/END, IF/ELSEIF/ELSE/END, BREAK
- 通訊: COMM_<n>_SEND/WAIT/GET/COUNT/CLEAR/RESET
"""

from __future__ import annotations

import re
from typing import Optional

from core.ir import (
    BlendMode,
    CallAction,
    CartesianPose,
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
    SetToolAction,
    WaitIOAction,
    WaitTimeAction,
)
from core.parser_base import BrandParser


# ── 正則表達式 ──

# 點位: P0, P12
RE_POINT = re.compile(r"P(\d+)")
# 軸角度: A1=30.5, A3=-90.5
RE_AXIS = re.compile(r"A(\d+)=([+-]?\d+(?:\.\d+)?|V\d+)")
# 工具末端座標: TX=600, TZ=1000, TA=0
RE_TCP = re.compile(r"T([XYZABC])=([+-]?\d+(?:\.\d+)?|V\d+)")
# 速度: VEL=40
RE_VEL = re.compile(r"VEL=([+-]?\d+(?:\.\d+)?|V\d+)")
# 加速度: ACC=30
RE_ACC = re.compile(r"ACC=([+-]?\d+(?:\.\d+)?|V\d+)")
# Base: BASE=1
RE_BASE = re.compile(r"BASE=(\d+)")
# Tool: TOOL=1
RE_TOOL = re.compile(r"TOOL=(\d+)")
# 融合: CONT=10
RE_CONT = re.compile(r"CONT=([+-]?\d+(?:\.\d+)?|V\d+)")
# 圓弧角度: THETA=720
RE_THETA = re.compile(r"THETA=([+-]?\d+(?:\.\d+)?|V\d+)")
# IO 輸出: OUT2[7]=ON, OUT1[0]=OFF
RE_IO_OUT = re.compile(r"OUT(\d+)\[(\d+)\]=(ON|OFF)")
# IO 輸入條件: IN1[2]==ON
RE_IO_IN = re.compile(r"IN(\d+)\[(\d+)\]==(ON|OFF)")
# DELAY 毫秒
RE_DELAY = re.compile(r"DELAY\s+(\d+(?:\.\d+)?|V\d+)")
# CALL
RE_CALL = re.compile(r"CALL\s+(\S+)")
# SET 變數
RE_SET_VAR = re.compile(r"SET\s+V(\d+)\s*([=+\-*/])\s*([+-]?\d+(?:\.\d+)?|V\d+)")
# COMM 通訊指令
RE_COMM = re.compile(r"COMM_(\d+)_(SEND|WAIT|GET|COUNT|CLEAR|RESET)")
# SYNC
RE_SYNC = re.compile(r"SYNC\s+(\d+)")


class RubyParser(BrandParser):
    """Ruby 控制器劇本解析器"""

    def can_parse(self, script: str) -> bool:
        """檢查是否為 Ruby 劇本"""
        keywords = [
            "MOVE_POINT", "MOVE_LINE", "MOVE_CIRCLE",
            "DELAY", "WAITFOR", "IO ", "CALL ",
            "POLISH_LINE", "POLISH_CIRCLE",
        ]
        lines = script.strip().splitlines()[:30]
        matches = sum(
            1 for line in lines
            if any(kw in line.upper() for kw in keywords)
        )
        return matches >= 2

    def parse(self, script: str, program_name: str = "") -> IRProgram:
        program = IRProgram(name=program_name, source_brand="RUBY")

        for line_num, line in enumerate(script.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue

            # 處理行內註解（取 // 之前的部分）
            code_part = stripped
            comment_part = ""
            comment_idx = stripped.find("//")
            if comment_idx >= 0:
                code_part = stripped[:comment_idx].strip()
                comment_part = stripped[comment_idx + 2:].strip()

            # 純註解行
            if not code_part:
                program.add(CommentAction(
                    source_line=line_num, source_text=line, text=comment_part
                ))
                continue

            action = self._parse_line(code_part, line_num, line)
            if comment_part and action:
                action.comment = comment_part
            program.add(action)

        return program

    def _parse_line(self, code: str, line_num: int, raw: str) -> IRAction:
        """解析單行指令"""
        upper = code.upper()

        # ── 運動指令 ──
        if upper.startswith("MOVE_POINT_REL"):
            return self._parse_move(code, line_num, raw, MotionType.JOINT, relative=True)
        if upper.startswith("MOVE_POINT"):
            return self._parse_move(code, line_num, raw, MotionType.JOINT, relative=False)
        if upper.startswith("MOVE_LINE_REL"):
            return self._parse_move(code, line_num, raw, MotionType.LINEAR, relative=True)
        if upper.startswith("MOVE_LINE"):
            return self._parse_move(code, line_num, raw, MotionType.LINEAR, relative=False)
        if upper.startswith("MOVE_CIRCLE"):
            return self._parse_move_circle(code, line_num, raw)

        # ── POLISH 指令（特殊，標記為 RawAction）──
        if upper.startswith("POLISH_LINE") or upper.startswith("POLISH_CIRCLE"):
            return RawAction(
                source_line=line_num, source_text=raw, raw_text=code,
                warning="拋光指令為 Ruby 特有功能，需人工轉換或確認"
            )

        # ── I/O ──
        if upper.startswith("IO ") or upper.startswith("IO\t"):
            return self._parse_io(code, line_num, raw)

        # ── 等待 ──
        if upper.startswith("WAITFOR"):
            return self._parse_waitfor(code, line_num, raw)

        # ── 延遲 ──
        if upper.startswith("DELAY"):
            return self._parse_delay(code, line_num, raw)

        # ── 呼叫副函式 ──
        if upper.startswith("CALL ") or upper.startswith("CALL\t"):
            m = RE_CALL.match(code)
            if m:
                return CallAction(
                    source_line=line_num, source_text=raw,
                    program_name=m.group(1)
                )

        # ── SET 變數 ──
        if upper.startswith("SET ") or upper.startswith("SET\t"):
            return RawAction(
                source_line=line_num, source_text=raw, raw_text=code,
                warning="SET 變數操作為 Ruby 特有功能，需人工確認"
            )

        # ── 流程控制 ──
        if upper.startswith(("LOOP", "END", "BREAK", "IF ", "IF\t", "ELSEIF", "ELSE")):
            return RawAction(
                source_line=line_num, source_text=raw, raw_text=code,
                warning="流程控制指令需人工轉換"
            )

        # ── 同步 ──
        if upper.startswith("SYNC"):
            return RawAction(
                source_line=line_num, source_text=raw, raw_text=code,
                warning="SYNC 多劇本同步為 Ruby 特有功能，無直接對應"
            )

        # ── 通訊 ──
        if RE_COMM.match(upper):
            return RawAction(
                source_line=line_num, source_text=raw, raw_text=code,
                warning="通訊指令為 Ruby 特有功能，需人工轉換"
            )

        # ── VISION ──
        if upper.startswith("VISION"):
            return RawAction(
                source_line=line_num, source_text=raw, raw_text=code,
                warning="視覺辨識指令為 Ruby 特有功能，無直接對應"
            )

        # ── 無法識別 ──
        return RawAction(
            source_line=line_num, source_text=raw, raw_text=code,
        )

    def _parse_move(
        self, code: str, line_num: int, raw: str,
        motion_type: MotionType, relative: bool
    ) -> MoveAction:
        """解析 MOVE_POINT / MOVE_LINE 及其 _REL 變體"""
        target = self._extract_target(code)
        vel = self._extract_float(RE_VEL, code)
        acc = self._extract_float(RE_ACC, code)
        cont = self._extract_float(RE_CONT, code)

        blend_mode = BlendMode.FINE
        blend_radius = None
        if cont is not None:
            blend_mode = BlendMode.CONTINUOUS
            blend_radius = cont

        # 提取 TOOL/BASE（嵌在運動指令中作為次要參數）
        action = MoveAction(
            source_line=line_num,
            source_text=raw,
            motion_type=motion_type,
            target=target,
            velocity=vel,
            acceleration=acc,
            blend_mode=blend_mode,
            blend_radius=blend_radius,
        )

        # 在 comment 中記錄 relative 資訊（供 emitter 使用）
        if relative:
            action.comment = (action.comment or "") + " [RELATIVE]"

        return action

    def _parse_move_circle(self, code: str, line_num: int, raw: str) -> MoveAction:
        """解析 MOVE_CIRCLE（需要兩個 P 點）"""
        points = RE_POINT.findall(code)
        via_point = None
        target = Position()

        if len(points) >= 2:
            via_point = Position(name=f"P{points[0]}")
            target = Position(name=f"P{points[1]}")
        elif len(points) == 1:
            target = Position(name=f"P{points[0]}")

        vel = self._extract_float(RE_VEL, code)
        acc = self._extract_float(RE_ACC, code)
        cont = self._extract_float(RE_CONT, code)

        blend_mode = BlendMode.FINE
        blend_radius = None
        if cont is not None:
            blend_mode = BlendMode.CONTINUOUS
            blend_radius = cont

        return MoveAction(
            source_line=line_num,
            source_text=raw,
            motion_type=MotionType.CIRCULAR,
            target=target,
            via_point=via_point,
            velocity=vel,
            acceleration=acc,
            blend_mode=blend_mode,
            blend_radius=blend_radius,
        )

    def _parse_io(self, code: str, line_num: int, raw: str) -> IRAction:
        """解析 IO OUT<m>[<b>]=ON|OFF"""
        m = RE_IO_OUT.search(code)
        if m:
            module = int(m.group(1))
            bit = int(m.group(2))
            value = m.group(3) == "ON"
            # Ruby 的 port 用 module*100+bit 編碼以保留完整資訊
            port = module * 100 + bit
            return SetIOAction(
                source_line=line_num, source_text=raw,
                io_type=IOType.DIGITAL, port=port, value=value,
            )
        return RawAction(
            source_line=line_num, source_text=raw, raw_text=code,
            warning="無法解析 IO 指令格式"
        )

    def _parse_waitfor(self, code: str, line_num: int, raw: str) -> IRAction:
        """解析 WAITFOR IN<m>[<b>]==ON|OFF"""
        m = RE_IO_IN.search(code)
        if m:
            module = int(m.group(1))
            bit = int(m.group(2))
            value = m.group(3) == "ON"
            port = module * 100 + bit
            return WaitIOAction(
                source_line=line_num, source_text=raw,
                io_type=IOType.DIGITAL, port=port, value=value,
            )
        return RawAction(
            source_line=line_num, source_text=raw, raw_text=code,
            warning="無法解析 WAITFOR 條件格式"
        )

    def _parse_delay(self, code: str, line_num: int, raw: str) -> WaitTimeAction:
        """解析 DELAY <ms>"""
        m = RE_DELAY.match(code)
        duration = 0.0
        if m:
            try:
                duration = float(m.group(1))
            except ValueError:
                pass
        # Ruby DELAY 單位已經是 ms，與 IR 一致
        return WaitTimeAction(
            source_line=line_num, source_text=raw, duration=duration
        )

    def _extract_target(self, code: str) -> Position:
        """從指令中提取目標位置（P點、軸角度或工具末端座標）"""
        # 優先檢查 P<int>
        p_match = RE_POINT.search(code)
        if p_match:
            return Position(name=f"P{p_match.group(1)}")

        # 檢查軸角度 A<int>=<double>
        axis_matches = RE_AXIS.findall(code)
        if axis_matches:
            joints = [0.0] * 7  # Ruby 最多 7 軸
            for axis_num, val in axis_matches:
                idx = int(axis_num) - 1
                if 0 <= idx < len(joints):
                    try:
                        joints[idx] = float(val)
                    except ValueError:
                        pass  # 可能是 V<int> 變數
            return Position(joint=JointPose(joints=joints))

        # 檢查工具末端座標 T<X|Y|Z|A|B|C>=<double>
        tcp_matches = RE_TCP.findall(code)
        if tcp_matches:
            pose = CartesianPose()
            for axis_letter, val in tcp_matches:
                try:
                    fval = float(val)
                except ValueError:
                    continue
                mapping = {
                    "X": "x", "Y": "y", "Z": "z",
                    "A": "rz", "B": "ry", "C": "rx",  # A=Rz, B=Ry, C=Rx
                }
                attr = mapping.get(axis_letter.upper())
                if attr:
                    setattr(pose, attr, fval)
            return Position(cartesian=pose)

        return Position(name="unknown")

    @staticmethod
    def _extract_float(pattern: re.Pattern, code: str) -> Optional[float]:
        """從指令中提取浮點數值"""
        m = pattern.search(code)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None  # 可能是 V<int> 變數引用
        return None
