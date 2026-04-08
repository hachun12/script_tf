# Script TF - 跨品牌機器人劇本轉換工具

離線的跨品牌工業機器人劇本轉換程式。採用混合式架構：規則引擎負責精確轉換，LLM 負責對話式編修與解釋。

## 架構

```
來源劇本 → Parser → IR (中間表示層) → Emitter → 目標劇本
                         ↑
                   對話式編修助手
              (規則式意圖解析 + LLM 輔助)
```

## 系統需求

- **Python** 3.10 以上（建議 3.11+）
- **作業系統**：Windows / macOS / Linux
- **Ollama**（選用）：若需要進階 AI 對話功能

## 完整部署步驟

### 1. 安裝 Python

前往 [python.org](https://www.python.org/downloads/) 下載安裝 Python 3.11+。
安裝時請勾選 **「Add Python to PATH」**。

驗證安裝：
```bash
python --version   # 應顯示 3.10 以上
```

### 2. 下載專案

```bash
git clone https://github.com/hachun12/script_tf.git
cd script_tf
```

### 3. 建立虛擬環境（建議）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

這會安裝以下套件：
- `pyyaml` — YAML 品牌定義解析
- `gradio` — Web UI 框架
- `pytest` — 測試框架

### 5. 安裝 Ollama（選用，進階 AI 對話功能）

如果只需要規則式對話指令（如「把速度降低 30%」），可以跳過此步驟。
安裝 Ollama 後才能使用自由自然語言對話功能。

**安裝 Ollama：**

前往 [ollama.com](https://ollama.com/) 下載安裝對應平台的版本。

**下載模型：**

```bash
ollama pull llama3.2:3b
```

> 模型大小約 2GB，下載時間視網路速度而定。
> 如需更高品質的回應，可改用較大模型：`ollama pull llama3.1:8b`（約 4.7GB），
> 但需在 `llm/assistant.py` 中將 `OLLAMA_MODEL` 改為 `"llama3.1:8b"`。

**啟動 Ollama 服務：**

```bash
ollama serve
```

> Windows 安裝後 Ollama 通常會自動在背景執行，可跳過此步驟。
> 驗證是否運行：瀏覽器開啟 http://localhost:11434 應顯示 "Ollama is running"。

### 6. 啟動服務

```bash
# 啟動 Web UI（推薦）
python cli.py ui
```

啟動後開啟瀏覽器 http://localhost:7860 即可使用。

## CLI 命令

```bash
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
- 也可以直接進行自然會話互動（如：這段劇本在做什麼、劇本邏輯、有沒有優化空間等）

### 進階對話（需要 Ollama）

安裝 Ollama 並下載模型後（見上方部署步驟第 5 步），可使用更自由的自然語言對話。

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
