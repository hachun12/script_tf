"""
轉換引擎整合測試
"""

import sys
from pathlib import Path

import pytest

# 確保專案根目錄在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.converter import Converter
from core.registry import BrandRegistry
from core.validator import validate_brand_definition


@pytest.fixture
def registry() -> BrandRegistry:
    reg = BrandRegistry()
    reg.load_all()
    return reg


@pytest.fixture
def converter(registry: BrandRegistry) -> Converter:
    return Converter(registry)


FANUC_SAMPLE = """\
! test program
UTOOL_NUM=1
J P[1] 50% FINE
L P[2] 500mm/sec FINE
DO[1]=ON
WAIT DI[1]=ON
WAIT 1.0(sec)
L P[3] 200mm/sec FINE
DO[1]=OFF
"""


class TestBrandRegistry:
    def test_load_brands(self, registry: BrandRegistry):
        brands = registry.list_brands()
        assert len(brands) >= 3
        assert "FANUC" in brands
        assert "ABB" in brands
        assert "KUKA" in brands

    def test_get_brand(self, registry: BrandRegistry):
        fanuc = registry.get("FANUC")
        assert fanuc is not None
        assert fanuc.name == "FANUC"

    def test_case_insensitive(self, registry: BrandRegistry):
        assert registry.get("fanuc") is not None
        assert registry.get("FANUC") is not None

    def test_detect_by_extension(self, registry: BrandRegistry):
        assert registry.detect_brand_by_extension("test.ls") == "FANUC"
        assert registry.detect_brand_by_extension("test.mod") == "ABB"
        assert registry.detect_brand_by_extension("test.src") == "KUKA"


class TestConverter:
    def test_fanuc_to_abb(self, converter: Converter):
        result = converter.convert(FANUC_SAMPLE, "FANUC", "ABB", "TEST")
        assert result.success
        assert result.target_brand == "ABB"
        assert "MoveAbsJ" in result.target_script or "MoveL" in result.target_script
        assert len(result.records) > 0

    def test_fanuc_to_kuka(self, converter: Converter):
        result = converter.convert(FANUC_SAMPLE, "FANUC", "KUKA", "TEST")
        assert result.success
        assert result.target_brand == "KUKA"
        assert len(result.records) > 0

    def test_unknown_brand_raises(self, converter: Converter):
        with pytest.raises(ValueError, match="未知"):
            converter.convert(FANUC_SAMPLE, "FANUC", "NONEXIST")

    def test_report_generated(self, converter: Converter):
        result = converter.convert(FANUC_SAMPLE, "FANUC", "ABB", "TEST")
        report = result.report()
        assert "轉換報告" in report
        assert "FANUC" in report
        assert "ABB" in report


class TestValidator:
    def test_validate_fanuc(self):
        brands_dir = Path(__file__).parent.parent / "brands" / "fanuc"
        result = validate_brand_definition(brands_dir)
        assert result.passed

    def test_validate_abb(self):
        brands_dir = Path(__file__).parent.parent / "brands" / "abb"
        result = validate_brand_definition(brands_dir)
        assert result.passed

    def test_validate_kuka(self):
        brands_dir = Path(__file__).parent.parent / "brands" / "kuka"
        result = validate_brand_definition(brands_dir)
        assert result.passed

    def test_validate_missing_dir(self, tmp_path: Path):
        result = validate_brand_definition(tmp_path / "nonexistent")
        # tmp_path/nonexistent doesn't exist, so we create it empty
        empty_dir = tmp_path / "empty_brand"
        empty_dir.mkdir()
        result = validate_brand_definition(empty_dir)
        assert not result.passed


class TestIRParsing:
    def test_fanuc_parse_move_joint(self, registry: BrandRegistry):
        fanuc = registry.get("FANUC")
        assert fanuc is not None
        program = fanuc.parser.parse("J P[1] 50% FINE", "test")
        assert program.action_count >= 1

    def test_fanuc_parse_set_io(self, registry: BrandRegistry):
        fanuc = registry.get("FANUC")
        assert fanuc is not None
        program = fanuc.parser.parse("DO[1]=ON", "test")
        assert program.action_count >= 1

    def test_fanuc_parse_comment(self, registry: BrandRegistry):
        fanuc = registry.get("FANUC")
        assert fanuc is not None
        program = fanuc.parser.parse("! this is a comment", "test")
        assert program.action_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
