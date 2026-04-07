"""
轉換管線 (Conversion Pipeline)

負責串接 Parser → IR → Emitter 的完整流程，
並產生轉換報告。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.ir import (
    IRAction,
    IRProgram,
    MoveAction,
    MotionType,
    RawAction,
    SetIOAction,
    WaitIOAction,
    WaitTimeAction,
    CommentAction,
    CallAction,
)
from core.registry import BrandRegistry


@dataclass
class ConversionRecord:
    """單行轉換記錄"""
    source_line: int | None
    source_text: str
    target_text: str
    ir_action_type: str
    status: str = "ok"        # "ok", "warning", "error"
    explanation: str = ""


@dataclass
class ConversionResult:
    """完整的轉換結果"""
    source_brand: str
    target_brand: str
    source_script: str
    target_script: str
    ir_program: IRProgram
    records: list[ConversionRecord] = field(default_factory=list)

    @property
    def warnings(self) -> list[ConversionRecord]:
        return [r for r in self.records if r.status == "warning"]

    @property
    def errors(self) -> list[ConversionRecord]:
        return [r for r in self.records if r.status == "error"]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def report(self) -> str:
        """產生人類可讀的轉換報告"""
        lines = [
            f"轉換報告：{self.source_brand} → {self.target_brand}",
            "=" * 50,
            f"總動作數：{len(self.records)}",
            f"成功：{sum(1 for r in self.records if r.status == 'ok')}",
            f"警告：{len(self.warnings)}",
            f"錯誤：{len(self.errors)}",
            "=" * 50,
            "",
        ]
        for rec in self.records:
            status_icon = {"ok": "[OK]", "warning": "[WARN]", "error": "[ERR]"}
            icon = status_icon.get(rec.status, "[ ? ]")
            lines.append(f"{icon} 第 {rec.source_line} 行: {rec.source_text.strip()}")
            lines.append(f"     → {rec.target_text.strip()}")
            if rec.explanation:
                lines.append(f"     說明: {rec.explanation}")
            lines.append("")
        return "\n".join(lines)


class Converter:
    """轉換引擎：串接 Parser → IR → Emitter"""

    def __init__(self, registry: BrandRegistry) -> None:
        self.registry = registry

    def convert(
        self,
        script: str,
        source_brand: str,
        target_brand: str,
        program_name: str = "MAIN",
    ) -> ConversionResult:
        """執行完整的轉換流程"""
        # 取得品牌
        src = self.registry.get(source_brand)
        tgt = self.registry.get(target_brand)
        if src is None:
            raise ValueError(f"未知的來源品牌: {source_brand}")
        if tgt is None:
            raise ValueError(f"未知的目標品牌: {target_brand}")

        # Step 1: Parse → IR
        ir_program = src.parser.parse(script, program_name)
        ir_program.source_brand = source_brand.upper()

        # Step 2: 單位轉換
        self._convert_units(ir_program, src.definition, tgt.definition)

        # Step 3: IR → Emit
        target_script = tgt.emitter.emit(ir_program)

        # Step 4: 建立轉換記錄
        target_lines = target_script.splitlines()
        records = self._build_records(ir_program, target_lines, src, tgt)

        return ConversionResult(
            source_brand=source_brand.upper(),
            target_brand=target_brand.upper(),
            source_script=script,
            target_script=target_script,
            ir_program=ir_program,
            records=records,
        )

    def _convert_units(
        self, program: IRProgram, src_def: dict, tgt_def: dict
    ) -> None:
        """處理不同品牌之間的單位轉換"""
        src_conv = src_def.get("unit_conversion", {})
        tgt_conv = tgt_def.get("unit_conversion", {})

        for action in program.actions:
            if isinstance(action, MoveAction) and action.velocity is not None:
                # 先轉為 IR 標準單位 (mm/s)
                if "velocity_linear" in src_conv:
                    action.velocity *= src_conv["velocity_linear"].get("to_ir", 1)
                # 再從 IR 轉為目標單位
                if "velocity_linear" in tgt_conv:
                    action.velocity *= tgt_conv["velocity_linear"].get("from_ir", 1)

    def _build_records(
        self, ir_program: IRProgram, target_lines: list[str], src, tgt
    ) -> list[ConversionRecord]:
        """建立轉換記錄（逐行對照）"""
        records = []
        # 跳過 header 行數
        header_lines = len(tgt.definition.get("file_header", "").splitlines())

        for i, action in enumerate(ir_program.actions):
            target_idx = i + header_lines
            target_text = (
                target_lines[target_idx] if target_idx < len(target_lines) else ""
            )

            rec = ConversionRecord(
                source_line=action.source_line,
                source_text=action.source_text or "",
                target_text=target_text,
                ir_action_type=type(action).__name__,
                explanation=self._explain(action, src.name, tgt.name),
            )

            if isinstance(action, RawAction):
                rec.status = "warning"
                rec.explanation = action.warning

            records.append(rec)
        return records

    @staticmethod
    def _explain(action: IRAction, src_name: str, tgt_name: str) -> str:
        """為每個轉換動作產生簡要說明"""
        if isinstance(action, MoveAction):
            motion_names = {
                MotionType.JOINT: "關節運動",
                MotionType.LINEAR: "直線運動",
                MotionType.CIRCULAR: "圓弧運動",
            }
            name = motion_names.get(action.motion_type, "移動")
            parts = [name]
            if action.velocity is not None:
                parts.append(f"速度={action.velocity}")
            if action.velocity_percent is not None:
                parts.append(f"速度={action.velocity_percent}%")
            if action.target.name:
                parts.append(f"目標={action.target.name}")
            return "、".join(parts)

        if isinstance(action, SetIOAction):
            return f"設定 DO[{action.port}] = {'ON' if action.value else 'OFF'}"

        if isinstance(action, WaitIOAction):
            return f"等待 DI[{action.port}] = {'ON' if action.value else 'OFF'}"

        if isinstance(action, WaitTimeAction):
            return f"等待 {action.duration}ms"

        if isinstance(action, CommentAction):
            return "註解"

        if isinstance(action, CallAction):
            return f"呼叫子程式: {action.program_name}"

        if isinstance(action, RawAction):
            return action.warning

        return ""
