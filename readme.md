# Script TF - 跨品牌機器人劇本轉換工具

離線的跨品牌工業機器人劇本轉換程式。採用混合式架構：規則引擎負責精確轉換，LLM 負責對話式編修與解釋。

## 架構

```
來源劇本 → Parser → IR (中間表示層) → Emitter → 目標劇本
                         ↑
                   對話式編修助手
              (規則式意圖解析 + LLM 輔助)
```

## 快速開始

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動 Web UI（推薦）
python cli.py ui

# 列出已支援品牌
python cli.py brands

# 轉換劇本
python cli.py convert examples/fanuc_sample.ls --from fanuc --to abb
python cli.py convert examples/ruby_sample.script --from ruby --to kuka -r

# 輸出到檔案
python cli.py convert examples/fanuc_sample.ls --to abb -o output.mod

# 驗證品牌定義
python cli.py validate brands/fanuc/

# 對話模式 (CLI)
python cli.py chat
```

## Web UI

啟動 `python cli.py ui` 後開啟瀏覽器 http://localhost:7860

三欄式介面：
- **左欄**：上傳或貼入來源劇本，選擇來源品牌
- **中欄**：轉換結果，選擇目標品牌，一鍵轉換
- **右欄**：AI 對話助手 / 轉換報告 / 使用說明

### 對話式編修（不需要 Ollama）

內建規則式意圖解析，以下指令可直接使用：
- 「把速度降低 30%」
- 「把第 5 到 10 行速度降低 50%」
- 「刪除第 5 行」/ 「刪除第 3 到 7 行」
- 「在第 3 行後加等待 1 秒」
- 「在第 5 行後加等待 500 毫秒」
- 「在第 5 行後加等待 DI[1]==ON」
- 「在第 8 行後加 DO[2]=OFF」
- 「解釋第 10 行」/ 「解釋第 5 到 10 行」

### 進階對話（需要 Ollama）

安裝並啟動 Ollama 後，可使用更自由的自然語言：
```bash
ollama pull qwen2.5-coder:7b
ollama serve
```

## 已支援品牌

| 品牌 | 語言 | 副檔名 | 類型 |
|------|------|--------|------|
| FANUC | TP/LS | .ls, .tp | YAML (Generic) |
| ABB | RAPID | .mod, .rapid | YAML (Generic) |
| KUKA | KRL | .src, .krl | YAML (Generic) |
| RUBY (PMC) | Ruby Script | .script, .rb | YAML + Plugin |

## 新增品牌

### 簡單品牌（僅 YAML）

在 `brands/` 下建立目錄，加入 `definition.yaml`：

```
brands/your_brand/
└── definition.yaml
```

### 複雜品牌（YAML + Python Plugin）

```
brands/your_brand/
├── definition.yaml
├── parser.py      # 自訂解析器（實作 BrandParser）
└── emitter.py     # 自訂生成器（實作 BrandEmitter）
```

驗證：`python cli.py validate brands/your_brand/`

## 專案結構

```
script_tf/
├── core/
│   ├── ir.py             # 中間表示層（14 種動作類型）
│   ├── parser_base.py    # 解析器基底 + 通用解析器
│   ├── emitter_base.py   # 生成器基底 + 通用生成器
│   ├── registry.py       # 品牌自動發現與註冊
│   ├── converter.py      # 轉換管線 + 轉換報告
│   └── validator.py      # 品牌定義驗證
├── brands/
│   ├── fanuc/definition.yaml
│   ├── abb/definition.yaml
│   ├── kuka/definition.yaml
│   └── ruby/             # 自訂 Plugin 範例
│       ├── definition.yaml
│       ├── parser.py
│       └── emitter.py
├── llm/
│   ├── assistant.py      # 對話助手 + 劇本編輯器
│   └── prompts.py        # LLM 提示詞模板
├── ui/
│   └── app.py            # Gradio Web UI
├── examples/             # 範例劇本
├── tests/                # 37 個測試案例
├── cli.py                # CLI 入口
├── requirements.txt
└── readme.md
```

## 執行測試

```bash
pytest tests/ -v
```
