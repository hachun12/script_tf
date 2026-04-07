"""
轉換驗證器

驗證品牌定義檔的完整性，以及轉換結果的正確性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.ir import IRProgram, RawAction


# 所有已知的 IR 動作類型
VALID_IR_ACTIONS = {
    "move_joint",
    "move_linear",
    "move_circular",
    "set_digital_output",
    "set_analog_output",
    "wait_digital_input",
    "wait_analog_input",
    "wait_time",
    "set_tool",
    "set_base",
    "set_speed",
    "call_program",
    "comment",
}


@dataclass
class ValidationIssue:
    level: str   # "error", "warning", "info"
    message: str


@dataclass
class ValidationResult:
    brand: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    def report(self) -> str:
        lines = [f"驗證報告：{self.brand}", "=" * 40]
        for issue in self.issues:
            icon = {"error": "[ERR]", "warning": "[WARN]", "info": "[OK]"}
            lines.append(f"  {icon.get(issue.level, '[ ? ]')} {issue.message}")
        status = "通過" if self.passed else "失敗"
        lines.append(f"\n結果：{status}")
        return "\n".join(lines)


def validate_brand_definition(brand_dir: str | Path) -> ValidationResult:
    """驗證品牌定義檔的完整性"""
    brand_dir = Path(brand_dir)
    result = ValidationResult(brand=brand_dir.name)

    # 檢查 definition.yaml 存在
    def_file = brand_dir / "definition.yaml"
    if not def_file.exists():
        result.issues.append(ValidationIssue("error", "缺少 definition.yaml"))
        return result

    # 載入 YAML
    try:
        with open(def_file, "r", encoding="utf-8") as f:
            definition = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.issues.append(ValidationIssue("error", f"YAML 語法錯誤: {e}"))
        return result

    result.brand = definition.get("brand", brand_dir.name)

    # 檢查必要欄位
    for field_name in ("brand", "file_extensions", "commands"):
        if field_name not in definition:
            result.issues.append(
                ValidationIssue("error", f"缺少必要欄位: {field_name}")
            )

    # 檢查 commands
    commands = definition.get("commands", {})
    if not commands:
        result.issues.append(ValidationIssue("error", "commands 為空"))
        return result

    result.issues.append(
        ValidationIssue("info", f"已定義 {len(commands)} 個命令映射")
    )

    # 檢查每個命令的 ir_action 是否合法
    for cmd_name, cmd_def in commands.items():
        ir_action = cmd_def.get("ir_action", cmd_name)
        if ir_action not in VALID_IR_ACTIONS:
            result.issues.append(
                ValidationIssue(
                    "error",
                    f"命令 '{cmd_name}' 的 ir_action '{ir_action}' 不是合法的 IR 動作",
                )
            )

        # 檢查 pattern 和 emit_template
        if "pattern" not in cmd_def:
            result.issues.append(
                ValidationIssue("warning", f"命令 '{cmd_name}' 缺少 pattern")
            )
        if "emit_template" not in cmd_def:
            result.issues.append(
                ValidationIssue("warning", f"命令 '{cmd_name}' 缺少 emit_template")
            )

    # 檢查是否覆蓋基本運動指令
    defined_actions = {
        cmd_def.get("ir_action", name) for name, cmd_def in commands.items()
    }
    essential = {"move_joint", "move_linear"}
    missing = essential - defined_actions
    for m in missing:
        result.issues.append(
            ValidationIssue("warning", f"缺少基本運動指令的映射: {m}")
        )

    optional = {"move_circular", "set_speed", "set_base"}
    missing_opt = optional - defined_actions
    for m in missing_opt:
        result.issues.append(
            ValidationIssue("info", f"缺少選用指令的映射: {m}（轉換時會標記警告）")
        )

    return result


def validate_conversion(ir_program: IRProgram) -> ValidationResult:
    """驗證轉換後的 IR 程式"""
    result = ValidationResult(brand=ir_program.source_brand)

    raw_actions = [a for a in ir_program.actions if isinstance(a, RawAction)]
    total = len(ir_program.actions)
    converted = total - len(raw_actions)

    result.issues.append(
        ValidationIssue("info", f"總指令數: {total}, 成功轉換: {converted}")
    )

    if raw_actions:
        result.issues.append(
            ValidationIssue(
                "warning",
                f"{len(raw_actions)} 個指令無法自動轉換，需人工確認",
            )
        )
        for raw in raw_actions[:5]:  # 最多顯示 5 個
            result.issues.append(
                ValidationIssue(
                    "warning",
                    f"  第 {raw.source_line} 行: {raw.raw_text}",
                )
            )

    return result
