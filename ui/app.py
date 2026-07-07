"""
Gradio Web UI - 三欄式劇本轉換介面

參考工業控制介面設計：
- 深色頂部標題列
- 各區塊有色彩標頭 + 邊框
- 底部狀態列
"""

from __future__ import annotations

import gradio as gr
import tempfile
import os
from pathlib import Path

from core.registry import BrandRegistry
from core.converter import Converter
from llm.assistant import ChatAssistant


# ── 全域狀態 ──
registry = BrandRegistry()
registry.load_all()
assistant = ChatAssistant(registry)

_last_action: dict | None = None


def get_brand_choices() -> list[str]:
    return registry.list_brands()


def load_file(file) -> str:
    if file is None:
        return ""
    path = Path(file) if isinstance(file, str) else Path(file.name)
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="cp950")
        except Exception as e:
            return f"[讀取錯誤] {e}"


def auto_detect_brand(file, source_script: str) -> str:
    if file is not None:
        path = Path(file) if isinstance(file, str) else Path(file.name)
        detected = registry.detect_brand_by_extension(str(path))
        if detected:
            return detected
    if source_script.strip():
        detected = registry.detect_brand(source_script)
        if detected:
            return detected
    choices = get_brand_choices()
    return choices[0] if choices else ""


def do_convert(source_script: str, source_brand: str, target_brand: str):
    if not source_script.strip():
        return "", "請先輸入或上傳來源劇本。", "⏳ 等待輸入..."
    if not source_brand or not target_brand:
        return "", "請選擇來源和目標品牌。", "⚠ 品牌未選擇"
    if source_brand == target_brand:
        return source_script, "來源和目標為同一品牌，無需轉換。", "ℹ 同品牌"
    try:
        result = assistant.load_script(
            source_script, source_brand, target_brand, "MAIN"
        )
        report = result.report()
        warnings = len(result.warnings)
        total = len(result.records)
        ok = sum(1 for r in result.records if r.status == "ok")
        status = f"✅ 轉換完成: {ok}/{total} 成功"
        if warnings:
            status += f" | ⚠ {warnings} 個警告"
        return result.target_script, report, status
    except Exception as e:
        return "", f"轉換錯誤：{e}", f"❌ 錯誤: {e}"


def on_file_upload(file):
    script = load_file(file)
    brand = auto_detect_brand(file, script)
    return script, brand


def chat_respond(message: str, chat_history: list):
    """
    處理對話輸入。
    回傳: (chatbot, chat_input, confirm_group, action_desc, target_script, status_bar)
    - 規則引擎匹配 → 直接套用，立即更新劇本
    - LLM 回傳操作 → 顯示確認區，等用戶點套用
    - 純問答 → 只更新對話
    """
    global _last_action
    if not message.strip():
        return chat_history, "", gr.update(visible=False), "", gr.update(), gr.update()

    response, action = assistant.chat(message)
    chat_history = chat_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": response},
    ]

    if action:
        if assistant.current_result is None:
            chat_history[-1]["content"] += "\n\n⚠ 請先轉換劇本後再進行編修。"
            return chat_history, "", gr.update(visible=False), "", gr.update(), gr.update()

        # 規則式解析（source="rule"）為確定性、非注入來源，可直接套用。
        # LLM 產生的操作（source="llm"）可能受不可信劇本內容影響（prompt injection），
        # 一律進入確認區，等使用者親自按「套用」才執行，不自動修改劇本。
        if action.get("source") == "rule":
            summary, new_script = assistant.apply_action(action)
            chat_history[-1]["content"] += f"\n\n✅ 已套用: {summary}"
            return (
                chat_history, "", gr.update(visible=False), "",
                gr.update(value=new_script), f"✅ 已套用: {action.get('description', '')}"
            )

        # LLM 來源 → 暫存待確認，顯示確認區
        _last_action = action
        desc = action.get("description") or action.get("action", "（未命名操作）")
        chat_history[-1]["content"] += "\n\n⏸ 此操作由 AI 解析產生，請確認後再套用。"
        return (
            chat_history, "", gr.update(visible=True), desc,
            gr.update(), "⏸ 待確認 AI 操作"
        )

    return chat_history, "", gr.update(visible=False), "", gr.update(), gr.update()


def apply_pending_action():
    global _last_action
    if assistant.current_result is None:
        return gr.update(value=""), "⚠ 尚未載入劇本。", gr.update(visible=False)
    if _last_action is None:
        return (
            gr.update(value=assistant.current_result.target_script),
            "⚠ 無待執行的操作。",
            gr.update(visible=False),
        )
    summary, new_script = assistant.apply_action(_last_action)
    _last_action = None
    return gr.update(value=new_script), f"✅ 已套用: {summary}", gr.update(visible=False)


def cancel_action():
    global _last_action
    _last_action = None
    return gr.update(visible=False)


def export_script(target_script: str, target_brand: str):
    """匯出目標劇本為檔案"""
    if not target_script.strip():
        return None
    # 根據品牌決定副檔名
    ext_map = {
        "fanuc": ".ls",
        "abb": ".mod",
        "kuka": ".src",
        "ruby": ".script",
    }
    ext = ext_map.get(target_brand.lower(), ".txt")
    filename = f"converted_{target_brand.lower()}{ext}"
    tmp_dir = tempfile.mkdtemp()
    filepath = os.path.join(tmp_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(target_script)
    return filepath


# ── CSS 樣式 ──

CSS_TEXT = """
/* 全域背景 */
.gradio-container {
    background: #e8ecf1 !important;
    max-width: 100% !important;
    padding-top: 0 !important;
}

/* 頂部標題列 */
.app-header {
    background: linear-gradient(135deg, #1a2332 0%, #2c3e50 100%);
    color: white;
    padding: 16px 28px;
    border-radius: 0 0 10px 10px;
    margin: -8px -8px 14px -8px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.3);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.app-header-left h1 {
    color: #fff !important; margin: 0 !important; font-size: 21px !important; font-weight: 700;
}
.app-header-left p {
    color: #94a3b8 !important; margin: 4px 0 0 0 !important; font-size: 13px !important;
}
.app-header-right {
    display: flex; gap: 10px; align-items: center;
}
.header-badge {
    display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 600;
}
.badge-green { background: #166534; color: #4ade80; }
.badge-yellow { background: #713f12; color: #fbbf24; }

/* 區塊欄位 - 使用 elem_classes 套用到 gr.Column */
.col-source {
    background: #fff !important;
    border: 2px solid #0ea5e9 !important;
    border-radius: 8px !important;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.col-target {
    background: #fff !important;
    border: 2px solid #22c55e !important;
    border-radius: 8px !important;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.col-chat {
    background: #fff !important;
    border: 2px solid #f59e0b !important;
    border-radius: 8px !important;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* 區塊標題橫條 (HTML 元素) */
.section-bar {
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: #fff;
    margin: 0;
}
.section-bar-source { background: linear-gradient(90deg, #0369a1, #0ea5e9); }
.section-bar-target { background: linear-gradient(90deg, #15803d, #22c55e); }
.section-bar-chat   { background: linear-gradient(90deg, #b45309, #f59e0b); }

/* 程式碼區域 */
.code-area textarea {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace !important;
    font-size: 13px !important; line-height: 1.6 !important;
    background: #f1f5f9 !important; color: #1e293b !important; border: 1px solid #cbd5e1 !important;
    border-radius: 4px !important;
}
.code-area-target textarea {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace !important;
    font-size: 13px !important; line-height: 1.6 !important;
    background: #f0fdf4 !important; color: #1e293b !important; border: 1px solid #86efac !important;
    border-radius: 4px !important;
}
/* gr.Code 用 CodeMirror 渲染，不是 textarea，文字顏色要單獨覆寫 */
.code-area .cm-editor, .code-area .cm-scroller, .code-area .cm-gutters {
    background: #f1f5f9 !important;
}
.code-area .cm-content, .code-area .cm-line, .code-area .cm-gutterElement {
    color: #1e293b !important;
}
.code-area-target .cm-editor, .code-area-target .cm-scroller, .code-area-target .cm-gutters {
    background: #f0fdf4 !important;
}
.code-area-target .cm-content, .code-area-target .cm-line, .code-area-target .cm-gutterElement {
    color: #1e293b !important;
}
.report-area textarea {
    font-family: 'Consolas', monospace !important;
    font-size: 12px !important; line-height: 1.5 !important;
    background: #fffbeb !important; color: #1e293b !important; border: 1px solid #fde68a !important;
}

/* 轉換按鈕 */
.convert-btn button {
    min-height: 42px !important; font-size: 15px !important;
    font-weight: 700 !important; letter-spacing: 2px;
    border-radius: 6px !important;
    background: linear-gradient(90deg, #0ea5e9, #22c55e) !important;
    color: #fff !important; border: none !important;
    box-shadow: 0 2px 8px rgba(14,165,233,0.4) !important;
}
.convert-btn button:hover {
    box-shadow: 0 4px 14px rgba(14,165,233,0.6) !important;
    transform: translateY(-1px);
}

/* 套用 / 取消 / 送出按鈕 */
.apply-btn button {
    background: linear-gradient(90deg, #22c55e, #16a34a) !important;
    color: #fff !important; border: none !important; font-weight: 700 !important;
    border-radius: 6px !important;
}
.cancel-btn button {
    background: #64748b !important; color: #fff !important;
    border: none !important; font-weight: 600 !important; border-radius: 6px !important;
}
.send-btn button {
    background: linear-gradient(90deg, #f59e0b, #d97706) !important;
    color: #fff !important; border: none !important; font-weight: 700 !important;
    border-radius: 6px !important;
}

/* 匯出按鈕 */
.export-btn button {
    background: linear-gradient(90deg, #6366f1, #8b5cf6) !important;
    color: #fff !important; border: none !important; font-weight: 700 !important;
    border-radius: 6px !important;
}

/* 操作確認區 */
.confirm-area {
    background: #fef3c7 !important; border: 2px solid #f59e0b !important;
    border-radius: 6px !important; padding: 10px !important; margin: 6px 0 !important;
}

/* 底部狀態列 */
.status-bar {
    background: #1e293b !important;
    padding: 6px 20px !important;
    border-radius: 8px !important;
    margin-top: 10px !important;
}
.status-bar input, .status-bar textarea {
    background: transparent !important; border: none !important;
    color: #94a3b8 !important; font-size: 13px !important; font-weight: 600 !important;
}

/* Chatbot */
.chatbot-box {
    border: 1px solid #e2e8f0 !important; border-radius: 6px !important;
    background: #f8fafc !important;
}

/* 右欄 AI 助手 - 自動填滿高度 */
.col-chat { display: flex !important; flex-direction: column !important; }
.col-chat > .block { flex: 1 !important; display: flex !important; flex-direction: column !important; }
.col-chat .tabs { flex: 1 !important; display: flex !important; flex-direction: column !important; margin: 0 !important; }
.col-chat .tabitem { flex: 1 !important; display: flex !important; flex-direction: column !important; padding: 4px 10px !important; }
.col-chat .chatbot-box { flex: 1 !important; min-height: 200px !important; margin: 0 !important; }
.col-chat .chatbot-box > div { height: 100% !important; }
.col-chat .gap { gap: 6px !important; }

/* 欄位內部 padding */
.col-source > .block, .col-target > .block, .col-chat > .block {
    padding: 0 !important;
}
.col-source .form, .col-target .form, .col-chat .form,
.col-source .block, .col-target .block, .col-chat .block {
    padding-left: 14px !important;
    padding-right: 14px !important;
}
.col-chat .block {
    padding-left: 8px !important;
    padding-right: 8px !important;
}

/* 隱藏 footer */
footer { display: none !important; }
"""

HEAD_CONTENT = f"<style>{CSS_TEXT}</style>"


def _ollama_badge() -> str:
    if assistant.check_ollama():
        return '<span class="header-badge badge-green">Ollama ON</span>'
    return '<span class="header-badge badge-yellow">Ollama OFF</span>'


# ── 建立 UI ──

def build_ui() -> gr.Blocks:

    with gr.Blocks(title="Script TF - 跨品牌機器人劇本轉換") as app:

        # ══════════════════════
        # 頂部標題列
        # ══════════════════════
        gr.HTML(f"""
        <div class="app-header">
            <div class="app-header-left">
                <h1>&#9881; Script TF &mdash; 跨品牌機器人劇本轉換工具</h1>
                <p>上傳或貼入來源劇本 &#8594; 選擇目標品牌 &#8594; 一鍵轉換 &nbsp;|&nbsp; 右側對話窗支援自然語言編修</p>
            </div>
            <div class="app-header-right">
                {_ollama_badge()}
                <span class="header-badge badge-green">{len(get_brand_choices())} 品牌</span>
            </div>
        </div>
        """)

        # ══════════════════════
        # 三欄主體
        # ══════════════════════
        with gr.Row(equal_height=True):

            # ── 左欄：來源劇本 ──
            with gr.Column(scale=4, min_width=300, elem_classes=["col-source"]):
                gr.HTML('<div class="section-bar section-bar-source">&#128196; &nbsp; 來源劇本 SOURCE</div>')
                with gr.Row():
                    source_brand = gr.Dropdown(
                        choices=get_brand_choices(),
                        value=get_brand_choices()[0] if get_brand_choices() else None,
                        label="來源品牌", scale=2,
                    )
                    file_upload = gr.File(
                        label="上傳檔案",
                        file_types=[".ls", ".tp", ".mod", ".rapid", ".src",
                                    ".krl", ".script", ".rb", ".txt"],
                        scale=3,
                    )
                source_script = gr.Code(
                    label="劇本內容", lines=24,
                    language=None, show_line_numbers=True,
                    interactive=True,
                    elem_classes=["code-area"],
                )

            # ── 中欄：目標劇本 ──
            with gr.Column(scale=4, min_width=300, elem_classes=["col-target"]):
                gr.HTML('<div class="section-bar section-bar-target">&#128204; &nbsp; 目標劇本 TARGET</div>')
                with gr.Row():
                    target_brand = gr.Dropdown(
                        choices=get_brand_choices(),
                        value=(
                            get_brand_choices()[1]
                            if len(get_brand_choices()) > 1 else None
                        ),
                        label="目標品牌", scale=3,
                    )
                    convert_btn = gr.Button(
                        "▶ 轉換", variant="primary",
                        scale=2, elem_classes=["convert-btn"],
                    )
                target_script = gr.Code(
                    label="轉換結果", lines=22,
                    language=None, show_line_numbers=True,
                    interactive=True,
                    elem_classes=["code-area-target"],
                )
                with gr.Row():
                    export_btn = gr.Button(
                        "💾 匯出存檔", variant="secondary",
                        elem_classes=["export-btn"],
                    )
                    export_file = gr.File(
                        label="下載", visible=False, interactive=False,
                    )

            # ── 右欄：AI 助手 ──
            with gr.Column(scale=4, min_width=300, elem_classes=["col-chat"]):
                gr.HTML('<div class="section-bar section-bar-chat">&#129302; &nbsp; AI 助手 ASSISTANT</div>')
                with gr.Tabs():

                    with gr.Tab("對話編修"):
                        chatbot = gr.Chatbot(
                            label="對話",
                            elem_classes=["chatbot-box"],
                        )
                        with gr.Group(
                            visible=False, elem_classes=["confirm-area"],
                        ) as confirm_group:
                            action_desc = gr.Textbox(
                                label="待執行操作", interactive=False, lines=1,
                            )
                            with gr.Row():
                                apply_btn = gr.Button(
                                    "✔ 套用", variant="primary",
                                    size="sm", elem_classes=["apply-btn"],
                                )
                                cancel_btn = gr.Button(
                                    "✖ 取消", variant="secondary",
                                    size="sm", elem_classes=["cancel-btn"],
                                )
                        with gr.Row():
                            chat_input = gr.Textbox(
                                label="輸入指令",
                                placeholder="例：把速度降低30%...",
                                lines=1, scale=4,
                            )
                            send_btn = gr.Button(
                                "送出", variant="primary",
                                scale=1, elem_classes=["send-btn"],
                            )

                    with gr.Tab("轉換報告"):
                        report_box = gr.Textbox(
                            label="逐行對照報告", lines=20, max_lines=30,
                            interactive=False, elem_classes=["report-area"],
                        )

                    with gr.Tab("使用說明"):
                        gr.Markdown("""
**轉換操作：**
1. 左欄上傳或貼入來源劇本
2. 選擇來源品牌和目標品牌
3. 點擊「轉換」按鈕

**對話編修（不需要 Ollama）：**

| 指令範例 | 功能 |
|---------|------|
| 把速度降低 30% | 全部速度 x0.7 |
| 把第 5 到 10 行速度降低 50% | 指定行速度修改 |
| 刪除第 5 行 | 刪除指定行 |
| 在第 3 行後加等待 1 秒 | 插入等待 |
| 在第 5 行後加等待 DI[1]==ON | 插入 I/O 等待 |
| 在第 8 行後加 DO[2]=OFF | 插入 I/O 輸出 |
| 解釋第 10 行 | 解釋轉換邏輯 |

**已支援品牌：** """ + " / ".join(f"**{b}**" for b in get_brand_choices()))

        # ══════════════════════
        # 底部狀態列
        # ══════════════════════
        with gr.Row(elem_classes=["status-bar"]):
            status_bar = gr.Textbox(
                value="⏳ 就緒 — 等待輸入劇本",
                label="", interactive=False, scale=4,
                show_label=False,
            )
            ollama_status = gr.Textbox(
                value=(
                    "🟢 Ollama: 已連接" if assistant.check_ollama()
                    else "🟡 Ollama: 未連接（規則式模式）"
                ),
                label="", interactive=False, scale=2,
                show_label=False,
            )

        # ══════════════════════
        # 事件綁定
        # ══════════════════════
        file_upload.change(
            fn=on_file_upload, inputs=[file_upload],
            outputs=[source_script, source_brand],
        )
        convert_btn.click(
            fn=do_convert,
            inputs=[source_script, source_brand, target_brand],
            outputs=[target_script, report_box, status_bar],
        )
        send_btn.click(
            fn=chat_respond, inputs=[chat_input, chatbot],
            outputs=[chatbot, chat_input, confirm_group, action_desc, target_script, status_bar],
        )
        chat_input.submit(
            fn=chat_respond, inputs=[chat_input, chatbot],
            outputs=[chatbot, chat_input, confirm_group, action_desc, target_script, status_bar],
        )
        apply_btn.click(
            fn=apply_pending_action, inputs=[],
            outputs=[target_script, status_bar, confirm_group],
        )
        cancel_btn.click(
            fn=cancel_action, inputs=[], outputs=[confirm_group],
        )
        export_btn.click(
            fn=export_script, inputs=[target_script, target_brand],
            outputs=[export_file],
        ).then(
            fn=lambda: gr.update(visible=True), inputs=[], outputs=[export_file],
        )

    return app


def launch(share: bool = False, server_port: int = 7860) -> None:
    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=server_port,
        share=share,
        show_error=True,
        head=HEAD_CONTENT,
        css=CSS_TEXT,
    )
