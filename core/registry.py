"""
品牌註冊表

自動掃描 brands/ 目錄，載入所有品牌定義。
支援 YAML-only 品牌（使用 GenericParser/Emitter）和
自訂 Plugin 品牌（使用品牌目錄下的 parser.py / emitter.py）。
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.emitter_base import BrandEmitter, GenericEmitter
from core.parser_base import BrandParser, GenericParser


@dataclass
class Brand:
    """已載入的品牌資訊"""
    name: str
    definition: dict[str, Any]
    parser: BrandParser
    emitter: BrandEmitter
    file_extensions: list[str]

    @property
    def description(self) -> str:
        return self.definition.get("description", self.name)


class BrandRegistry:
    """品牌註冊表：自動發現與管理所有品牌"""

    def __init__(self, brands_dir: str | Path | None = None) -> None:
        self._brands: dict[str, Brand] = {}
        if brands_dir is None:
            brands_dir = Path(__file__).parent.parent / "brands"
        self._brands_dir = Path(brands_dir)

    def load_all(self) -> None:
        """掃描 brands/ 目錄，載入所有品牌"""
        if not self._brands_dir.exists():
            return
        for brand_path in sorted(self._brands_dir.iterdir()):
            if not brand_path.is_dir():
                continue
            definition_file = brand_path / "definition.yaml"
            if not definition_file.exists():
                continue
            self._load_brand(brand_path, definition_file)

    def _load_brand(self, brand_path: Path, definition_file: Path) -> None:
        """載入單一品牌"""
        with open(definition_file, "r", encoding="utf-8") as f:
            definition = yaml.safe_load(f)

        brand_name = definition.get("brand", brand_path.name).upper()

        # 檢查是否有自訂 parser
        parser_file = brand_path / "parser.py"
        if parser_file.exists():
            parser = self._load_plugin(parser_file, "Parser", brand_name)
        else:
            parser = GenericParser(definition)

        # 檢查是否有自訂 emitter
        emitter_file = brand_path / "emitter.py"
        if emitter_file.exists():
            emitter = self._load_plugin(emitter_file, "Emitter", brand_name)
        else:
            emitter = GenericEmitter(definition)

        self._brands[brand_name] = Brand(
            name=brand_name,
            definition=definition,
            parser=parser,
            emitter=emitter,
            file_extensions=definition.get("file_extensions", []),
        )

    @staticmethod
    def _load_plugin(
        plugin_file: Path, class_suffix: str, brand_name: str
    ) -> Any:
        """動態載入品牌自訂的 parser.py 或 emitter.py"""
        module_name = f"brands.{brand_name.lower()}.{plugin_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin: {plugin_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 尋找名稱結尾為 Parser 或 Emitter 的類別（跳過抽象基底類別）
        import inspect
        for attr_name in dir(module):
            if attr_name.endswith(class_suffix):
                cls = getattr(module, attr_name)
                if isinstance(cls, type) and not inspect.isabstract(cls):
                    return cls()
        raise ImportError(
            f"No class ending with '{class_suffix}' found in {plugin_file}"
        )

    # ── 查詢方法 ──

    def get(self, brand_name: str) -> Brand | None:
        return self._brands.get(brand_name.upper())

    def list_brands(self) -> list[str]:
        return sorted(self._brands.keys())

    def detect_brand(self, script: str) -> str | None:
        """自動偵測劇本的品牌"""
        for name, brand in self._brands.items():
            if brand.parser.can_parse(script):
                return name
        return None

    def detect_brand_by_extension(self, filename: str) -> str | None:
        """根據副檔名偵測品牌"""
        ext = Path(filename).suffix.lower()
        for name, brand in self._brands.items():
            if ext in brand.file_extensions:
                return name
        return None

    def __contains__(self, brand_name: str) -> bool:
        return brand_name.upper() in self._brands

    def __len__(self) -> int:
        return len(self._brands)
