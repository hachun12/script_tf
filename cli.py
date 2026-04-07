"""
CLI 入口點

用法：
  python cli.py convert input.ls --from fanuc --to abb
  python cli.py convert input.ls --to kuka --output result.src
  python cli.py brands
  python cli.py validate brands/fanuc/
  python cli.py chat
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.converter import Converter
from core.registry import BrandRegistry
from core.validator import validate_brand_definition


def create_registry() -> BrandRegistry:
    registry = BrandRegistry()
    registry.load_all()
    return registry


def cmd_convert(args: argparse.Namespace) -> None:
    """執行劇本轉換"""
    registry = create_registry()
    converter = Converter(registry)

    # 讀取來源劇本
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"錯誤：找不到檔案 {input_path}")
        sys.exit(1)

    script = input_path.read_text(encoding="utf-8")

    # 偵測或指定來源品牌
    source_brand = args.source
    if not source_brand:
        source_brand = registry.detect_brand_by_extension(str(input_path))
    if not source_brand:
        source_brand = registry.detect_brand(script)
    if not source_brand:
        print("錯誤：無法自動偵測來源品牌，請使用 --from 指定")
        sys.exit(1)

    target_brand = args.target
    if not target_brand:
        print("錯誤：請使用 --to 指定目標品牌")
        sys.exit(1)

    # 執行轉換
    try:
        result = converter.convert(
            script, source_brand, target_brand, program_name=input_path.stem
        )
    except ValueError as e:
        print(f"錯誤：{e}")
        sys.exit(1)

    # 輸出結果
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(result.target_script, encoding="utf-8")
        print(f"已輸出至 {output_path}")
    else:
        print(result.target_script)

    # 顯示報告
    if args.report:
        print("\n")
        print(result.report())

    # 警告提示
    if result.warnings:
        print(f"\n⚠ {len(result.warnings)} 個警告，請檢查轉換報告", file=sys.stderr)


def cmd_brands(args: argparse.Namespace) -> None:
    """列出所有已載入的品牌"""
    registry = create_registry()
    brands = registry.list_brands()
    if not brands:
        print("尚未載入任何品牌。請在 brands/ 目錄中新增品牌定義。")
        return

    print(f"已載入 {len(brands)} 個品牌：\n")
    for name in brands:
        brand = registry.get(name)
        if brand:
            exts = ", ".join(brand.file_extensions)
            cmds = len(brand.definition.get("commands", {}))
            print(f"  {name:<12} {brand.description}")
            print(f"  {'':12} 副檔名: {exts}  |  命令數: {cmds}")
            print()


def cmd_validate(args: argparse.Namespace) -> None:
    """驗證品牌定義檔"""
    brand_dir = Path(args.brand_dir)
    if not brand_dir.exists():
        print(f"錯誤：找不到目錄 {brand_dir}")
        sys.exit(1)

    result = validate_brand_definition(brand_dir)
    print(result.report())
    if not result.passed:
        sys.exit(1)


def cmd_chat(args: argparse.Namespace) -> None:
    """啟動對話式編修模式（CLI）"""
    from core.registry import BrandRegistry
    from llm.assistant import ChatAssistant

    registry = create_registry()
    assistant = ChatAssistant(registry)

    print("=" * 50)
    print("  機器人劇本轉換助手 (對話模式)")
    print("=" * 50)
    print()

    if not assistant.check_ollama():
        print("Ollama 未連接，使用規則式模式。")
        print("可用指令範例：")
        print("  - 把速度降低 30%")
        print("  - 刪除第 5 到 10 行")
        print("  - 在第 3 行後加等待 1 秒")
        print("  - 解釋第 8 行")
    else:
        print("Ollama 已連接，可使用自然語言互動。")
    print()

    brands = registry.list_brands()
    print(f"已載入品牌：{', '.join(brands)}")
    print()
    print("命令：")
    print("  load <file> --from <brand> --to <brand>  載入劇本")
    print("  show                                      顯示目前劇本")
    print("  report                                    顯示轉換報告")
    print("  apply                                     套用上次建議的操作")
    print("  quit                                      離開")
    print()

    last_action = None
    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再見！")
            break
        if user_input.lower() == "show":
            if assistant.current_result:
                print("\n--- 來源劇本 ---")
                print(assistant.current_result.source_script)
                print("\n--- 目標劇本 ---")
                print(assistant.current_result.target_script)
            else:
                print("尚未載入劇本。")
            continue
        if user_input.lower() == "report":
            if assistant.current_result:
                print(assistant.current_result.report())
            else:
                print("尚未載入劇本。")
            continue
        if user_input.lower() == "apply":
            if last_action and assistant.current_result:
                summary, new_script = assistant.apply_action(last_action)
                print(f"\n{summary}")
                print(f"\n--- 更新後的目標劇本 ---")
                print(new_script)
                last_action = None
            else:
                print("沒有待套用的操作。")
            continue
        if user_input.lower().startswith("load "):
            _cli_load(user_input, assistant)
            continue

        # 對話
        response, action = assistant.chat(user_input)
        print(f"\n助手> {response}")
        if action:
            last_action = action
            print("(輸入 'apply' 套用此操作)")
        print()


def _cli_load(user_input: str, assistant) -> None:
    """CLI load 命令"""
    parts = user_input.split()
    file_path = source_brand = target_brand = None
    i = 1
    while i < len(parts):
        if parts[i] == "--from" and i + 1 < len(parts):
            source_brand = parts[i + 1]; i += 2
        elif parts[i] == "--to" and i + 1 < len(parts):
            target_brand = parts[i + 1]; i += 2
        elif file_path is None:
            file_path = parts[i]; i += 1
        else:
            i += 1
    if not all([file_path, source_brand, target_brand]):
        print("用法：load <file> --from <brand> --to <brand>")
        return
    path = Path(file_path)
    if not path.exists():
        print(f"找不到檔案：{file_path}")
        return
    script = path.read_text(encoding="utf-8")
    try:
        result = assistant.load_script(script, source_brand, target_brand)
        print(f"已載入並轉換：{source_brand} → {target_brand}")
        print(f"動作數：{result.ir_program.action_count}, 警告：{len(result.warnings)}")
    except ValueError as e:
        print(f"錯誤：{e}")


def cmd_ui(args: argparse.Namespace) -> None:
    """啟動 Web UI"""
    try:
        from ui.app import launch
    except ImportError:
        print("Web UI 需要安裝 Gradio：pip install gradio")
        sys.exit(1)

    print("啟動 Web UI...")
    launch(share=args.share, server_port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="script_tf",
        description="跨品牌機器人劇本轉換工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # convert
    p_convert = subparsers.add_parser("convert", help="轉換劇本")
    p_convert.add_argument("input", help="來源劇本檔案路徑")
    p_convert.add_argument("--from", dest="source", help="來源品牌 (可自動偵測)")
    p_convert.add_argument("--to", dest="target", required=True, help="目標品牌")
    p_convert.add_argument("-o", "--output", help="輸出檔案路徑")
    p_convert.add_argument(
        "-r", "--report", action="store_true", help="顯示轉換報告"
    )

    # brands
    subparsers.add_parser("brands", help="列出已載入的品牌")

    # validate
    p_validate = subparsers.add_parser("validate", help="驗證品牌定義檔")
    p_validate.add_argument("brand_dir", help="品牌目錄路徑")

    # chat
    subparsers.add_parser("chat", help="啟動對話式編修模式 (CLI)")

    # ui
    p_ui = subparsers.add_parser("ui", help="啟動 Web UI")
    p_ui.add_argument(
        "--port", type=int, default=7860, help="伺服器埠號 (預設 7860)"
    )
    p_ui.add_argument(
        "--share", action="store_true", help="建立公開分享連結"
    )

    args = parser.parse_args()

    if args.command == "convert":
        cmd_convert(args)
    elif args.command == "brands":
        cmd_brands(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "chat":
        cmd_chat(args)
    elif args.command == "ui":
        cmd_ui(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
