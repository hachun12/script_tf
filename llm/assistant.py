"""
LLM 對話助手

負責：
1. 理解使用者的自然語言意圖
2. 將意圖轉為對 IR 的結構化操作（由規則引擎執行）
3. 解釋劇本邏輯
4. 協助處理無法自動轉換的邊界案例

使用 Ollama 作為本地 LLM 後端。
無 LLM 時提供規則式降級模式（關鍵字解析）。
"""

from __future__ import annotations

import json
import os
import re
import copy
from typing import Any, Optional

from core.converter import ConversionResult, Converter
from core.ir import (
    BlendMode,
    CommentAction,
    IOType,
    IRAction,
    IRProgram,
    MoveAction,
    MotionType,
    Position,
    RawAction,
    SetIOAction,
    WaitIOAction,
    WaitTimeAction,
)
from core.registry import BrandRegistry
from llm.prompts import (
    SYSTEM_PROMPT,
    MODIFY_INTENT_PROMPT,
    EXPLAIN_PROMPT,
    DIFF_EXPLAIN_PROMPT,
    EDGE_CASE_PROMPT,
)


# Ollama API 預設設定（可用環境變數覆寫，容器內需指向 host 上的 Ollama）
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


class ScriptEditor:
    """
    劇本結構化編輯器

    所有修改都是在 IR 層面進行，再由 Emitter 重新生成目標劇本。
    確保修改結果 100% 符合語法規範。
    """

    def __init__(self, converter: Converter) -> None:
        self.converter = converter

    def modify_speed(
        self, result: ConversionResult, lines: list[int], factor: float
    ) -> tuple[ConversionResult, str]:
        """修改指定行的速度"""
        ir = result.ir_program
        modified = []
        for action in ir.actions:
            if action.source_line in lines and isinstance(action, MoveAction):
                if action.velocity is not None:
                    old_v = action.velocity
                    action.velocity = round(action.velocity * factor, 2)
                    modified.append(
                        f"第 {action.source_line} 行: 速度 {old_v} -> {action.velocity}"
                    )
                if action.velocity_percent is not None:
                    old_v = action.velocity_percent
                    action.velocity_percent = round(
                        min(action.velocity_percent * factor, 100), 2
                    )
                    modified.append(
                        f"第 {action.source_line} 行: 速度 {old_v}% -> {action.velocity_percent}%"
                    )

        if not modified:
            return result, "未找到指定行的運動指令，無法修改速度。"

        new_result = self._re_emit(result)
        summary = "已修改速度:\n" + "\n".join(modified)
        return new_result, summary

    def modify_all_speeds(
        self, result: ConversionResult, factor: float
    ) -> tuple[ConversionResult, str]:
        """修改所有運動指令的速度"""
        all_lines = [
            a.source_line for a in result.ir_program.actions
            if isinstance(a, MoveAction) and a.source_line is not None
        ]
        return self.modify_speed(result, all_lines, factor)

    def delete_lines(
        self, result: ConversionResult, lines: list[int]
    ) -> tuple[ConversionResult, str]:
        """刪除指定行"""
        ir = result.ir_program
        removed = []
        new_actions = []
        for action in ir.actions:
            if action.source_line in lines:
                removed.append(f"第 {action.source_line} 行: {action.source_text}")
            else:
                new_actions.append(action)
        ir.actions = new_actions

        if not removed:
            return result, "未找到指定行，無法刪除。"

        new_result = self._re_emit(result)
        summary = f"已刪除 {len(removed)} 行:\n" + "\n".join(removed)
        return new_result, summary

    def add_wait_time(
        self, result: ConversionResult, after_line: int, duration_ms: float
    ) -> tuple[ConversionResult, str]:
        """在指定行之後插入等待時間"""
        ir = result.ir_program
        new_actions = []
        inserted = False
        for action in ir.actions:
            new_actions.append(action)
            if action.source_line == after_line:
                wait = WaitTimeAction(
                    source_line=None,
                    source_text=f"[插入] 等待 {duration_ms}ms",
                    duration=duration_ms,
                )
                new_actions.append(wait)
                inserted = True
        ir.actions = new_actions

        if not inserted:
            return result, f"未找到第 {after_line} 行，無法插入。"

        new_result = self._re_emit(result)
        return new_result, f"已在第 {after_line} 行後插入等待 {duration_ms}ms"

    def add_wait_io(
        self, result: ConversionResult, after_line: int,
        port: int, value: bool = True
    ) -> tuple[ConversionResult, str]:
        """在指定行之後插入等待 DI"""
        ir = result.ir_program
        new_actions = []
        inserted = False
        for action in ir.actions:
            new_actions.append(action)
            if action.source_line == after_line:
                wait = WaitIOAction(
                    source_line=None,
                    source_text=f"[插入] 等待 DI[{port}]={'ON' if value else 'OFF'}",
                    io_type=IOType.DIGITAL,
                    port=port,
                    value=value,
                )
                new_actions.append(wait)
                inserted = True
        ir.actions = new_actions

        if not inserted:
            return result, f"未找到第 {after_line} 行，無法插入。"

        new_result = self._re_emit(result)
        val_str = "ON" if value else "OFF"
        return new_result, f"已在第 {after_line} 行後插入等待 DI[{port}]=={val_str}"

    def add_set_io(
        self, result: ConversionResult, after_line: int,
        port: int, value: bool = True
    ) -> tuple[ConversionResult, str]:
        """在指定行之後插入設定 DO"""
        ir = result.ir_program
        new_actions = []
        inserted = False
        for action in ir.actions:
            new_actions.append(action)
            if action.source_line == after_line:
                io_action = SetIOAction(
                    source_line=None,
                    source_text=f"[插入] DO[{port}]={'ON' if value else 'OFF'}",
                    io_type=IOType.DIGITAL,
                    port=port,
                    value=value,
                )
                new_actions.append(io_action)
                inserted = True
        ir.actions = new_actions

        if not inserted:
            return result, f"未找到第 {after_line} 行，無法插入。"

        new_result = self._re_emit(result)
        val_str = "ON" if value else "OFF"
        return new_result, f"已在第 {after_line} 行後插入 DO[{port}]={val_str}"

    def _re_emit(self, result: ConversionResult) -> ConversionResult:
        """重新生成目標劇本"""
        tgt = self.converter.registry.get(result.target_brand)
        if tgt is None:
            return result
        new_script = tgt.emitter.emit(result.ir_program)
        result.target_script = new_script
        return result


class ChatAssistant:
    """對話式編修助手"""

    def __init__(self, registry: BrandRegistry) -> None:
        self.registry = registry
        self.converter = Converter(registry)
        self.editor = ScriptEditor(self.converter)
        self.current_result: Optional[ConversionResult] = None
        self.history: list[dict[str, str]] = []
        self._ollama_available: Optional[bool] = None
        # 暫存待確認的操作
        self._pending_action: Optional[dict] = None
        self._pending_description: str = ""

    def check_ollama(self) -> bool:
        """檢查 Ollama 是否可用且模型存在"""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    self._ollama_available = False
                    return False
                data = _json.loads(resp.read().decode("utf-8"))
                model_names = [m.get("name", "") for m in data.get("models", [])]
                # 檢查目標模型是否已安裝
                self._ollama_available = any(
                    OLLAMA_MODEL in name for name in model_names
                )
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def chat(self, user_message: str) -> tuple[str, Optional[dict]]:
        """
        處理使用者訊息。

        回傳 (回覆文字, 操作指令 dict 或 None)
        操作指令格式: {"action": "...", "params": {...}, "description": "..."}
        """
        self.history.append({"role": "user", "content": user_message})

        # 先嘗試規則式解析（不依賴 LLM，快速回應常見操作）
        rule_response, rule_action = self._rule_based_parse(user_message)
        if rule_action:
            self.history.append({"role": "assistant", "content": rule_response})
            return rule_response, rule_action

        # 如果 Ollama 可用，使用 LLM
        if self.check_ollama():
            response = self._call_ollama(user_message)
            # 嘗試從 LLM 回覆中提取操作指令
            action = self._extract_action_from_response(response)
            self.history.append({"role": "assistant", "content": response})
            return response, action

        # 降級模式
        response = self._fallback_response(user_message)
        self.history.append({"role": "assistant", "content": response})
        return response, None

    def apply_action(self, action: dict) -> tuple[str, str]:
        """
        執行操作指令，回傳 (操作結果摘要, 新的目標劇本)
        """
        if self.current_result is None:
            return "尚未載入劇本。", ""

        action_type = action.get("action", "")
        params = action.get("params", {})

        if action_type == "modify_speed":
            lines = params.get("lines", [])
            factor = params.get("factor", 1.0)
            if not lines:
                # 無指定行 → 修改全部
                self.current_result, summary = self.editor.modify_all_speeds(
                    self.current_result, factor
                )
            else:
                # 先嘗試用給定行號，如果一個都對不上就改為全部
                valid_source_lines = {
                    a.source_line for a in self.current_result.ir_program.actions
                    if isinstance(a, MoveAction) and a.source_line is not None
                }
                matched = [ln for ln in lines if ln in valid_source_lines]
                if matched:
                    self.current_result, summary = self.editor.modify_speed(
                        self.current_result, matched, factor
                    )
                else:
                    # 行號全部無效 → 退回修改全部
                    self.current_result, summary = self.editor.modify_all_speeds(
                        self.current_result, factor
                    )
                    summary = f"（指定行號未匹配運動指令，已改為修改全部）\n{summary}"

        elif action_type == "delete_lines":
            lines = params.get("lines", [])
            self.current_result, summary = self.editor.delete_lines(
                self.current_result, lines
            )

        elif action_type == "add_wait_time":
            after = params.get("after_line", 0)
            duration = params.get("duration", 1000)
            self.current_result, summary = self.editor.add_wait_time(
                self.current_result, after, duration
            )

        elif action_type == "add_wait_io":
            after = params.get("after_line", 0)
            port = params.get("port", 1)
            value = params.get("value", True)
            self.current_result, summary = self.editor.add_wait_io(
                self.current_result, after, port, value
            )

        elif action_type == "add_set_io":
            after = params.get("after_line", 0)
            port = params.get("port", 1)
            value = params.get("value", True)
            self.current_result, summary = self.editor.add_set_io(
                self.current_result, after, port, value
            )

        else:
            return f"未知的操作: {action_type}", self.current_result.target_script

        return summary, self.current_result.target_script

    def load_script(
        self, script: str, source_brand: str, target_brand: str,
        program_name: str = "MAIN",
    ) -> ConversionResult:
        """載入並轉換劇本"""
        self.current_result = self.converter.convert(
            script, source_brand, target_brand, program_name
        )
        self.history = []  # 重置對話歷史
        return self.current_result

    def get_line_explanation(self, line_num: int) -> str:
        """取得單行的轉換說明"""
        if self.current_result is None:
            return "尚未載入劇本。"
        for rec in self.current_result.records:
            if rec.source_line == line_num:
                parts = [
                    f"來源（第 {line_num} 行）: {rec.source_text.strip()}",
                    f"目標: {rec.target_text.strip()}",
                    f"動作類型: {rec.ir_action_type}",
                ]
                if rec.explanation:
                    parts.append(f"說明: {rec.explanation}")
                if rec.status == "warning":
                    parts.append("[警告] 此指令可能需要人工確認")
                return "\n".join(parts)
        return f"找不到第 {line_num} 行。"

    # ── 規則式解析（不需要 LLM）──

    def _rule_based_parse(
        self, message: str
    ) -> tuple[str, Optional[dict]]:
        """用關鍵字規則解析常見操作意圖"""
        msg = message.strip()

        # ── 速度修改（支援雙向語序）──
        # 提取行號範圍（如果有）
        def _extract_lines(text: str) -> list[int]:
            m = re.search(r"第\s*(\d+)\s*(?:到|~|-)\s*(\d+)\s*行", text)
            if m:
                return list(range(int(m.group(1)), int(m.group(2)) + 1))
            m = re.search(r"第\s*(\d+)\s*行", text)
            if m:
                return [int(m.group(1))]
            return []

        def _speed_action(factor: float, lines: list[int]) -> tuple[str, dict]:
            desc = f"所有運動指令速度 x{factor:.2f}" if not lines else f"第 {lines[0]}-{lines[-1]} 行速度 x{factor:.2f}"
            action = {"action": "modify_speed", "params": {"lines": lines, "factor": factor}, "description": desc}
            return f"將{desc}，確認套用嗎？", action

        # 降低/減少: "速度降低30%", "降低速度30%", "把速度降30%"
        speed_down = re.search(
            r"(?:(?:速度|speed).*?(?:降低|減少|降|減)|(?:降低|減少|降|減).*?(?:速度|speed))\s*(\d+)\s*%", msg
        )
        if speed_down:
            pct = int(speed_down.group(1))
            return _speed_action(1 - pct / 100, _extract_lines(msg))

        # 提高/增加: "速度提高50%", "提高速度50%", "把速度加50%"
        speed_up = re.search(
            r"(?:(?:速度|speed).*?(?:提高|增加|提升|加快|加)|(?:提高|增加|提升|加快|加).*?(?:速度|speed))\s*(\d+)\s*%", msg
        )
        if speed_up:
            pct = int(speed_up.group(1))
            return _speed_action(1 + pct / 100, _extract_lines(msg))

        # 乘以: "速度乘以0.7", "速度x1.5"
        speed_mul = re.search(r"(?:速度|speed).*?(?:乘以|乘|[x*×])\s*([\d.]+)", msg)
        if speed_mul:
            return _speed_action(float(speed_mul.group(1)), _extract_lines(msg))

        # 設為: "速度設為200", "速度改成300" — 暫不支援絕對值，提示用倍率
        speed_set = re.search(r"(?:速度|speed).*?(?:設為|設成|改為|改成)\s*(\d+)", msg)
        if speed_set:
            return "目前僅支援倍率調整（如「速度提高50%」「速度乘以0.8」），尚不支援設定絕對速度值。", None

        # 刪除行: "刪除第5行", "刪除第3到7行"
        del_match = re.search(r"刪除.*?第\s*(\d+)\s*(?:到|~|-)\s*(\d+)\s*行", msg)
        if del_match:
            start, end = int(del_match.group(1)), int(del_match.group(2))
            lines = list(range(start, end + 1))
            action = {"action": "delete_lines", "params": {"lines": lines}, "description": f"刪除第 {start}-{end} 行"}
            return f"將刪除第 {start} 到 {end} 行，確認套用嗎？", action

        del_match2 = re.search(r"刪除.*?第\s*(\d+)\s*行", msg)
        if del_match2:
            line = int(del_match2.group(1))
            action = {"action": "delete_lines", "params": {"lines": [line]}, "description": f"刪除第 {line} 行"}
            return f"將刪除第 {line} 行，確認套用嗎？", action

        # 插入等待: "在第5行後加等待1秒", "第3行後插入等待DI[1]"
        wait_time_match = re.search(
            r"(?:在)?第\s*(\d+)\s*行後.*?等待\s*([\d.]+)\s*(?:秒|s|sec)", msg
        )
        if wait_time_match:
            after = int(wait_time_match.group(1))
            duration = float(wait_time_match.group(2)) * 1000
            action = {"action": "add_wait_time", "params": {"after_line": after, "duration": duration}, "description": f"第 {after} 行後插入等待 {duration}ms"}
            return f"將在第 {after} 行後插入等待 {duration:.0f}ms，確認套用嗎？", action

        wait_time_ms_match = re.search(
            r"(?:在)?第\s*(\d+)\s*行後.*?等待\s*(\d+)\s*(?:毫秒|ms)", msg
        )
        if wait_time_ms_match:
            after = int(wait_time_ms_match.group(1))
            duration = float(wait_time_ms_match.group(2))
            action = {"action": "add_wait_time", "params": {"after_line": after, "duration": duration}, "description": f"第 {after} 行後插入等待 {duration}ms"}
            return f"將在第 {after} 行後插入等待 {duration:.0f}ms，確認套用嗎？", action

        wait_di_match = re.search(
            r"(?:在)?第\s*(\d+)\s*行後.*?等待\s*DI\[(\d+)\]\s*(?:==?\s*)?(ON|OFF)?",
            msg, re.IGNORECASE,
        )
        if wait_di_match:
            after = int(wait_di_match.group(1))
            port = int(wait_di_match.group(2))
            value = (wait_di_match.group(3) or "ON").upper() != "OFF"
            val_str = "ON" if value else "OFF"
            action = {"action": "add_wait_io", "params": {"after_line": after, "port": port, "value": value}, "description": f"第 {after} 行後插入等待 DI[{port}]=={val_str}"}
            return f"將在第 {after} 行後插入等待 DI[{port}]=={val_str}，確認套用嗎？", action

        # 插入 IO: "在第5行後加DO[1]=ON"
        io_match = re.search(
            r"(?:在)?第\s*(\d+)\s*行後.*?DO\[(\d+)\]\s*=\s*(ON|OFF)",
            msg, re.IGNORECASE,
        )
        if io_match:
            after = int(io_match.group(1))
            port = int(io_match.group(2))
            value = io_match.group(3).upper() == "ON"
            val_str = "ON" if value else "OFF"
            action = {"action": "add_set_io", "params": {"after_line": after, "port": port, "value": value}, "description": f"第 {after} 行後插入 DO[{port}]={val_str}"}
            return f"將在第 {after} 行後插入 DO[{port}]={val_str}，確認套用嗎？", action

        # 解釋行: "解釋第5行", "第10行什麼意思"
        explain_match = re.search(r"(?:解釋|說明|什麼意思).*?第\s*(\d+)\s*行", msg)
        if not explain_match:
            explain_match = re.search(r"第\s*(\d+)\s*行.*?(?:解釋|說明|什麼意思)", msg)
        if explain_match:
            line = int(explain_match.group(1))
            explanation = self.get_line_explanation(line)
            return explanation, None

        # 解釋範圍: "解釋第5到10行"
        explain_range = re.search(
            r"(?:解釋|說明).*?第\s*(\d+)\s*(?:到|~|-)\s*(\d+)\s*行", msg
        )
        if explain_range:
            start, end = int(explain_range.group(1)), int(explain_range.group(2))
            explanations = []
            for ln in range(start, end + 1):
                explanations.append(self.get_line_explanation(ln))
            return "\n\n".join(explanations), None

        return "", None

    def _extract_action_from_response(self, response: str) -> Optional[dict]:
        """從 LLM 回覆中提取 JSON 操作指令"""
        # 尋找 JSON 區塊
        json_match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", response)
        if json_match:
            try:
                action = json.loads(json_match.group())
                if "action" in action:
                    return action
            except json.JSONDecodeError:
                pass
        return None

    def _call_ollama(self, message: str) -> str:
        """呼叫 Ollama API"""
        import urllib.request

        context = ""
        if self.current_result:
            # 建立帶行號的劇本文字，方便 LLM 理解
            source_lines = self.current_result.source_script.splitlines()
            numbered_source = "\n".join(
                f"  {i+1}: {line}" for i, line in enumerate(source_lines)
            )
            target_lines = self.current_result.target_script.splitlines()
            numbered_target = "\n".join(
                f"  {i+1}: {line}" for i, line in enumerate(target_lines)
            )
            context = (
                f"\n\n--- 目前劇本狀態 ---\n"
                f"來源品牌：{self.current_result.source_brand}\n"
                f"目標品牌：{self.current_result.target_brand}\n"
                f"動作數：{self.current_result.ir_program.action_count}\n"
                f"\n來源劇本（含行號）：\n{numbered_source}\n"
                f"\n目標劇本（含行號）：\n{numbered_target}\n"
                f"\n重要：JSON 操作中的行號必須使用「來源劇本」的行號。"
                f"\n如果使用者要修改全部速度，lines 請留空陣列 []。"
                f"\n只有使用者明確指定特定行時才填入行號。"
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + context},
            *self.history[-10:],
        ]

        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "（無回覆）")
        except Exception as e:
            return f"LLM 呼叫失敗：{e}"

    def _fallback_response(self, message: str) -> str:
        """無 LLM 時的基本回覆"""
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ("解釋", "explain", "說明", "報告")):
            if self.current_result:
                return self.current_result.report()
            return "請先載入劇本。"
        if any(kw in msg_lower for kw in ("品牌", "brand", "列表")):
            return f"已載入品牌：{', '.join(self.registry.list_brands())}"
        return (
            "目前為基本模式（Ollama 未連接）。\n"
            "可直接使用以下指令格式：\n"
            "  - 「把速度降低 30%」\n"
            "  - 「刪除第 5 到 10 行」\n"
            "  - 「在第 3 行後加等待 1 秒」\n"
            "  - 「在第 5 行後加等待 DI[1]==ON」\n"
            "  - 「解釋第 8 行」\n"
            "啟動 Ollama 後可使用更自由的自然語言。"
        )
