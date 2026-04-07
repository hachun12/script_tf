"""
對話助手與劇本編輯器測試
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.registry import BrandRegistry
from core.converter import Converter
from llm.assistant import ChatAssistant, ScriptEditor


@pytest.fixture
def registry() -> BrandRegistry:
    reg = BrandRegistry()
    reg.load_all()
    return reg


@pytest.fixture
def assistant(registry: BrandRegistry) -> ChatAssistant:
    return ChatAssistant(registry)


RUBY_SAMPLE = """\
// test
MOVE_POINT  P0  VEL=40
MOVE_LINE  P1  VEL=20
MOVE_LINE  P2  VEL=10  CONT=10
IO  OUT1[0]=ON
DELAY  500
WAITFOR  IN1[0]==ON
MOVE_LINE  P3  VEL=15
IO  OUT1[0]=OFF
"""


class TestScriptEditor:
    def test_modify_all_speeds(self, registry: BrandRegistry):
        assistant = ChatAssistant(registry)
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        editor = ScriptEditor(Converter(registry))

        result, summary = editor.modify_all_speeds(assistant.current_result, 0.5)
        assert "速度" in summary
        # 驗證速度確實降低了
        for action in result.ir_program.actions:
            from core.ir import MoveAction
            if isinstance(action, MoveAction) and action.velocity is not None:
                assert action.velocity <= 20  # 原本最大 40, *0.5 = 20

    def test_modify_speed_specific_lines(self, registry: BrandRegistry):
        assistant = ChatAssistant(registry)
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        editor = ScriptEditor(Converter(registry))

        result, summary = editor.modify_speed(
            assistant.current_result, [3, 4], 2.0
        )
        assert "速度" in summary

    def test_delete_lines(self, registry: BrandRegistry):
        assistant = ChatAssistant(registry)
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        original_count = assistant.current_result.ir_program.action_count
        editor = ScriptEditor(Converter(registry))

        result, summary = editor.delete_lines(assistant.current_result, [5])
        assert "刪除" in summary
        assert result.ir_program.action_count < original_count

    def test_add_wait_time(self, registry: BrandRegistry):
        assistant = ChatAssistant(registry)
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        original_count = assistant.current_result.ir_program.action_count
        editor = ScriptEditor(Converter(registry))

        result, summary = editor.add_wait_time(
            assistant.current_result, 3, 1000
        )
        assert "等待" in summary
        assert result.ir_program.action_count == original_count + 1

    def test_add_wait_io(self, registry: BrandRegistry):
        assistant = ChatAssistant(registry)
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        original_count = assistant.current_result.ir_program.action_count
        editor = ScriptEditor(Converter(registry))

        result, summary = editor.add_wait_io(
            assistant.current_result, 3, 2, True
        )
        assert "DI" in summary
        assert result.ir_program.action_count == original_count + 1

    def test_add_set_io(self, registry: BrandRegistry):
        assistant = ChatAssistant(registry)
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        original_count = assistant.current_result.ir_program.action_count
        editor = ScriptEditor(Converter(registry))

        result, summary = editor.add_set_io(
            assistant.current_result, 3, 1, False
        )
        assert "DO" in summary
        assert result.ir_program.action_count == original_count + 1


class TestChatAssistant:
    def test_load_script(self, assistant: ChatAssistant):
        result = assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        assert result is not None
        assert result.target_brand == "FANUC"
        assert assistant.current_result is result

    def test_rule_parse_speed_decrease(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        response, action = assistant._rule_based_parse("把速度降低30%")
        assert action is not None
        assert action["action"] == "modify_speed"
        assert action["params"]["factor"] == pytest.approx(0.7)

    def test_rule_parse_speed_increase(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        response, action = assistant._rule_based_parse("速度提高50%")
        assert action is not None
        assert action["action"] == "modify_speed"
        assert action["params"]["factor"] == pytest.approx(1.5)

    def test_rule_parse_speed_with_lines(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        response, action = assistant._rule_based_parse("把第3到5行速度降低50%")
        assert action is not None
        assert action["params"]["lines"] == [3, 4, 5]
        assert action["params"]["factor"] == pytest.approx(0.5)

    def test_rule_parse_delete_range(self, assistant: ChatAssistant):
        response, action = assistant._rule_based_parse("刪除第5到8行")
        assert action is not None
        assert action["action"] == "delete_lines"
        assert action["params"]["lines"] == [5, 6, 7, 8]

    def test_rule_parse_delete_single(self, assistant: ChatAssistant):
        response, action = assistant._rule_based_parse("刪除第5行")
        assert action is not None
        assert action["action"] == "delete_lines"
        assert action["params"]["lines"] == [5]

    def test_rule_parse_add_wait_time(self, assistant: ChatAssistant):
        response, action = assistant._rule_based_parse("在第3行後加等待1.5秒")
        assert action is not None
        assert action["action"] == "add_wait_time"
        assert action["params"]["after_line"] == 3
        assert action["params"]["duration"] == 1500

    def test_rule_parse_add_wait_ms(self, assistant: ChatAssistant):
        response, action = assistant._rule_based_parse("在第5行後加等待500毫秒")
        assert action is not None
        assert action["action"] == "add_wait_time"
        assert action["params"]["duration"] == 500

    def test_rule_parse_add_wait_di(self, assistant: ChatAssistant):
        response, action = assistant._rule_based_parse("在第5行後加等待DI[2]==ON")
        assert action is not None
        assert action["action"] == "add_wait_io"
        assert action["params"]["port"] == 2
        assert action["params"]["value"] is True

    def test_rule_parse_add_do(self, assistant: ChatAssistant):
        response, action = assistant._rule_based_parse("在第5行後加DO[1]=OFF")
        assert action is not None
        assert action["action"] == "add_set_io"
        assert action["params"]["port"] == 1
        assert action["params"]["value"] is False

    def test_rule_parse_explain(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        response, action = assistant._rule_based_parse("解釋第3行")
        assert action is None  # 解釋不需要操作指令
        assert "第 3 行" in response or "來源" in response

    def test_apply_action(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        action = {
            "action": "modify_speed",
            "params": {"lines": [], "factor": 0.5},
        }
        summary, new_script = assistant.apply_action(action)
        assert "速度" in summary
        assert new_script  # 有產生新劇本

    def test_chat_returns_tuple(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        response, action = assistant.chat("把速度降低30%")
        assert isinstance(response, str)
        assert action is None or isinstance(action, dict)

    def test_get_line_explanation(self, assistant: ChatAssistant):
        assistant.load_script(RUBY_SAMPLE, "RUBY", "FANUC")
        expl = assistant.get_line_explanation(2)
        assert "來源" in expl or "第 2 行" in expl


class TestRubyConversions:
    """確保 Ruby 品牌在整合助手後仍正常運作"""

    def test_ruby_to_all_brands(self, registry: BrandRegistry):
        converter = Converter(registry)
        for target in registry.list_brands():
            if target == "RUBY":
                continue
            result = converter.convert(RUBY_SAMPLE, "RUBY", target)
            assert result.success, f"Ruby -> {target} 失敗"

    def test_all_brands_to_ruby(self, registry: BrandRegistry):
        converter = Converter(registry)
        fanuc_script = """\
! test
UTOOL_NUM=1
J P[1] 50% FINE
L P[2] 500mm/sec FINE
DO[1]=ON
WAIT DI[1]=ON
"""
        result = converter.convert(fanuc_script, "FANUC", "RUBY")
        assert result.success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
