# Script TF — 跨品牌機器人劇本轉換工具

## 操作說明手冊

**版本：** 1.0  
**最後更新：** 2026-04-01

---

## 目錄

1. [系統簡介](#1-系統簡介)
2. [系統需求與安裝](#2-系統需求與安裝)
3. [快速開始](#3-快速開始)
4. [Web UI 操作說明](#4-web-ui-操作說明)
   - 4.1 [介面總覽](#41-介面總覽)
   - 4.2 [劇本轉換](#42-劇本轉換)
   - 4.3 [AI 對話編修](#43-ai-對話編修)
   - 4.4 [轉換報告](#44-轉換報告)
   - 4.5 [匯出存檔](#45-匯出存檔)
5. [CLI 命令列操作](#5-cli-命令列操作)
6. [支援品牌與命令對照](#6-支援品牌與命令對照)
7. [對話指令速查表](#7-對話指令速查表)
8. [新增品牌擴充指南](#8-新增品牌擴充指南)
9. [常見問題 FAQ](#9-常見問題-faq)

---

## 1. 系統簡介

**Script TF** 是一套離線運行的跨品牌工業機器人劇本轉換工具。核心功能包含：

- **自動轉換**：輸入來源品牌劇本，一鍵轉換為目標品牌格式
- **逐行對照報告**：每一行轉換都附帶邏輯說明，確保可追溯
- **AI 對話編修**：透過自然語言指令修改劇本（調速、刪行、插入等待...）
- **品牌擴充**：新增品牌只需撰寫 YAML 定義檔，無需修改核心程式

### 架構概念

```
來源劇本 → [Parser] → 中間表示(IR) → [Emitter] → 目標劇本
               ↑                            ↑
          品牌定義 YAML               品牌定義 YAML
```

所有轉換透過統一的中間表示（IR）進行，確保品牌間的轉換正確性。對話編修同樣在 IR 層面操作，再由 Emitter 重新生成語法正確的目標劇本。

---

## 2. 系統需求與安裝

### 系統需求

| 項目 | 最低需求 |
|------|---------|
| 作業系統 | Windows 10 / 11、Linux、macOS |
| Python | 3.10 以上 |
| 記憶體 | 4 GB（若使用 Ollama LLM 建議 8 GB 以上）|
| 磁碟空間 | 約 100 MB（不含 LLM 模型）|

### 安裝步驟

```bash
# 1. 進入專案目錄
cd script_tf

# 2. 安裝 Python 依賴
pip install -r requirements.txt

# 3.（可選）安裝 Ollama 以啟用進階自然語言功能
#    下載 Ollama: https://ollama.com
#    安裝完成後拉取模型：
ollama pull llama3.2:3b
```

### 驗證安裝

```bash
# 列出已載入品牌，確認安裝正常
python cli.py brands
```

預期輸出：

```
已載入 4 個品牌：

  FANUC        FANUC 機器人控制器
  ABB          ABB 機器人控制器 (RAPID)
  KUKA         KUKA 機器人控制器 (KRL)
  RUBY         PMC 自研控制器 (Ruby Script)
```

---

## 3. 快速開始

### 30 秒體驗：命令列轉換

```bash
# 將 FANUC 範例劇本轉換為 ABB 格式
python cli.py convert examples/fanuc_sample.ls --to abb

# 轉換為 KUKA 格式並儲存檔案
python cli.py convert examples/fanuc_sample.ls --to kuka -o output.src

# 轉換並顯示逐行報告
python cli.py convert examples/fanuc_sample.ls --to ruby -r
```

### 啟動 Web UI

```bash
python cli.py ui
```

瀏覽器開啟 **http://localhost:7860** 即可使用圖形介面。

---

## 4. Web UI 操作說明

### 4.1 介面總覽

啟動 Web UI 後，畫面分為三大區塊：

```
┌─────────────────────────────────────────────────────────────┐
│  ⚙ Script TF — 跨品牌機器人劇本轉換工具     [Ollama ON][4 品牌] │
├──────────────┬──────────────┬───────────────────────────────┤
│ 📄 來源劇本    │ 📌 目標劇本    │ 🤖 AI 助手                     │
│   SOURCE     │   TARGET     │   ASSISTANT                   │
│              │              │                               │
│ [來源品牌 ▼]  │ [目標品牌 ▼]  │ ┌─對話編修─┬─轉換報告─┬─使用說明─┐ │
│ [上傳檔案]    │ [▶ 轉換]     │ │                            │ │
│              │              │ │  對話區域                    │ │
│  (程式碼區)    │  (程式碼區)   │ │                            │ │
│  含行號顯示    │  含行號顯示   │ │  [輸入指令...] [送出]        │ │
│              │ [💾 匯出存檔]  │ │                            │ │
├──────────────┴──────────────┴───────────────────────────────┤
│  ⏳ 就緒 — 等待輸入劇本                    🟢 Ollama: 已連接    │
└─────────────────────────────────────────────────────────────┘
```

> **截圖位置：** 建議在此插入完整 UI 畫面截圖
> 
> 📸 `screenshots/ui_overview.png`

**介面元素說明：**

| 區域 | 說明 |
|------|------|
| 頂部標題列 | 顯示工具名稱、Ollama 連線狀態、已載入品牌數 |
| 左欄（藍色標頭） | 來源劇本區：選擇品牌、上傳檔案或貼入程式碼 |
| 中欄（綠色標頭） | 目標劇本區：選擇目標品牌、檢視轉換結果、匯出存檔 |
| 右欄（橘色標頭） | AI 助手：對話編修、轉換報告、使用說明 |
| 底部狀態列 | 顯示操作狀態與 Ollama 連線狀態 |

---

### 4.2 劇本轉換

#### 步驟一：輸入來源劇本

有兩種方式輸入來源劇本：

**方式 A — 上傳檔案：**

1. 點擊左欄「上傳檔案」按鈕
2. 選擇機器人劇本檔案（支援 `.ls`、`.mod`、`.src`、`.script` 等）
3. 系統自動偵測品牌並填入程式碼區

> 📸 `screenshots/upload_file.png`

**方式 B — 直接貼入：**

1. 在左欄程式碼區直接貼入劇本內容
2. 手動從下拉選單選擇「來源品牌」

#### 步驟二：選擇目標品牌

在中欄的「目標品牌」下拉選單中選擇要轉換的目標品牌。

#### 步驟三：執行轉換

點擊 **「▶ 轉換」** 按鈕，轉換結果會顯示在中欄的程式碼區（含行號）。

> 📸 `screenshots/conversion_result.png`

底部狀態列會顯示轉換結果摘要，例如：

```
✅ 轉換完成: 15/17 成功 | ⚠ 2 個警告
```

#### 轉換結果說明

- **成功的行**：直接轉換為目標品牌語法
- **警告（WARNING）**：該指令無法完全自動轉換（如品牌專屬命令），需人工確認
- **註解行**：原始註解保留並轉換為目標品牌的註解格式

---

### 4.3 AI 對話編修

轉換完成後，可透過右欄的「對話編修」頁籤，用自然語言修改劇本。

#### 使用方式

1. 在「輸入指令」欄位輸入修改需求（中文即可）
2. 點擊「送出」或按 Enter
3. 系統解析指令後**直接套用修改**，目標劇本立即更新
4. 對話區會顯示修改摘要（如哪些行的速度從多少改為多少）

> 📸 `screenshots/chat_modify_speed.png`

#### 常見對話指令範例

**速度調整：**

```
提高速度50%
把速度降低30%
速度乘以0.8
把第 8 到 12 行速度提高20%
```

**刪除行：**

```
刪除第 5 行
刪除第 3 到 7 行
```

**插入等待：**

```
在第 3 行後加等待 1 秒
在第 5 行後加等待 500 毫秒
在第 10 行後加等待 DI[1]==ON
```

**插入 I/O 輸出：**

```
在第 8 行後加 DO[2]=OFF
在第 12 行後加 DO[1]=ON
```

**解釋劇本：**

```
解釋第 10 行
解釋第 5 到 15 行
```

#### 規則式 vs. LLM 模式

| 模式 | 觸發條件 | 回應速度 | 說明 |
|------|---------|---------|------|
| 規則式 | 符合上述指令格式 | 瞬間 | 不需要 Ollama，離線即可使用 |
| LLM | 自由對話、複雜描述 | 數秒 | 需要 Ollama，支援更靈活的自然語言 |

系統會優先嘗試規則式解析，無法匹配時才轉交 LLM 處理。即使 Ollama 未啟動，所有上述常見指令格式都可正常使用。

---

### 4.4 轉換報告

點擊右欄的「轉換報告」頁籤，可查看逐行轉換對照報告。

報告內容包含：

```
=== 轉換報告: FANUC → ABB ===
程式名: PICK_PLACE
動作數: 17

逐行對照：
----
[第 5 行] UTOOL_NUM=1
  → ! Set tool: tool1
  動作: set_tool | 狀態: ok
----
[第 8 行] J P[1] 50% FINE
  → MoveAbsJ 1,,fine,;
  動作: move_joint | 狀態: ok
  說明: Joint move → MoveAbsJ
----
[第 13 行] DO[1]=ON
  → SetDO do_1,1;
  動作: set_digital_output | 狀態: ok
----
...
```

> 📸 `screenshots/conversion_report.png`

---

### 4.5 匯出存檔

1. 確認目標劇本內容正確（可直接在程式碼區手動編輯）
2. 點擊 **「💾 匯出存檔」** 按鈕
3. 瀏覽器會自動下載檔案，副檔名依目標品牌自動決定：

| 目標品牌 | 匯出副檔名 |
|---------|----------|
| FANUC | `.ls` |
| ABB | `.mod` |
| KUKA | `.src` |
| RUBY | `.script` |

---

## 5. CLI 命令列操作

除了 Web UI，系統也提供完整的命令列介面：

### 劇本轉換

```bash
# 基本轉換（自動偵測來源品牌）
python cli.py convert input.ls --to abb

# 指定來源品牌
python cli.py convert input.script --from ruby --to fanuc

# 輸出至檔案
python cli.py convert input.ls --to kuka -o result.src

# 顯示逐行轉換報告
python cli.py convert input.ls --to abb -r
```

### 品牌管理

```bash
# 列出所有已載入品牌
python cli.py brands

# 驗證品牌定義檔是否完整
python cli.py validate brands/fanuc/
python cli.py validate brands/ruby/
```

### 對話模式（CLI）

```bash
python cli.py chat
```

進入互動式對話後的操作：

```
你> load examples/fanuc_sample.ls --from fanuc --to abb
已載入並轉換：fanuc → abb

你> show
--- 來源劇本 ---
(顯示來源)
--- 目標劇本 ---
(顯示目標)

你> 提高速度50%
助手> 將所有運動指令速度 x1.50，已套用。

你> report
(顯示逐行轉換報告)

你> quit
再見！
```

### 啟動 Web UI

```bash
# 預設 port 7860
python cli.py ui

# 自訂 port
python cli.py ui --port 8080

# 建立公開分享連結（透過 Gradio 雲端中繼）
python cli.py ui --share
```

---

## 6. 支援品牌與命令對照

### 已支援品牌

| 品牌 | 語言 | 副檔名 | 說明 |
|------|------|--------|------|
| **FANUC** | TP / KAREL | `.ls` `.tp` | FANUC 機器人控制器 |
| **ABB** | RAPID | `.mod` `.rapid` | ABB 機器人控制器 |
| **KUKA** | KRL | `.src` `.krl` | KUKA 機器人控制器 |
| **RUBY** | Ruby Script | `.script` `.rb` | PMC 自研控制器 |

### 跨品牌命令對照表

| 功能 | FANUC | ABB | KUKA | RUBY |
|------|-------|-----|------|------|
| 關節移動 | `J P[n] %s FINE` | `MoveAbsJ` | `PTP` | `MOVE_POINT P[n]` |
| 直線移動 | `L P[n] mm/sec` | `MoveL` | `LIN` | `MOVE_LINE P[n]` |
| 圓弧移動 | `C P[n]` | `MoveC` | `CIRC` | `MOVE_CIRCLE P[v] P[n]` |
| 數位輸出 | `DO[n]=ON/OFF` | `SetDO` | `$OUT[n]=TRUE` | `IO OUT[m][b]=ON` |
| 等待輸入 | `WAIT DI[n]=ON` | `WaitDI` | `WAIT FOR $IN[n]` | `WAITFOR IN[m][b]==ON` |
| 等待時間 | `WAIT n(sec)` | `WaitTime` | `WAIT SEC n` | `DELAY ms` |
| 設定工具 | `UTOOL_NUM=n` | `tool` | `$TOOL` | `TOOL=n` |
| 設定基座標 | `UFRAME_NUM=n` | `wobj` | `$BASE` | `BASE=n` |
| 呼叫程式 | `CALL name` | `name` | `name()` | `CALL name` |

### RUBY 特殊指令

以下為 PMC 自研控制器專屬指令，轉換時會標記為警告（需人工確認）：

| 指令 | 功能 |
|------|------|
| `POLISH_LINE` | 直線拋光路徑 |
| `POLISH_CIRCLE` | 倒圓角拋光 |
| `LOOP / BREAK / END` | 迴圈控制 |
| `IF / ELSEIF / ELSE / END` | 條件判斷 |
| `SYNC` | 多劇本同步 |
| `COMM_*` | Socket 通訊指令 |
| `VISION` | 視覺辨識 |

---

## 7. 對話指令速查表

### 速度修改

| 指令 | 效果 | 範例 |
|------|------|------|
| `提高速度 N%` | 全部速度 ×(1+N/100) | `提高速度50%` → ×1.5 |
| `降低速度 N%` | 全部速度 ×(1-N/100) | `降低速度30%` → ×0.7 |
| `速度乘以 N` | 全部速度 ×N | `速度乘以0.5` → ×0.5 |
| `把第 A 到 B 行速度提高 N%` | 指定範圍速度修改 | `把第5到10行速度降低20%` |

### 行操作

| 指令 | 效果 |
|------|------|
| `刪除第 N 行` | 刪除指定行 |
| `刪除第 A 到 B 行` | 刪除範圍 |

### 插入指令

| 指令 | 效果 |
|------|------|
| `在第 N 行後加等待 X 秒` | 插入等待時間 |
| `在第 N 行後加等待 X 毫秒` | 插入等待（毫秒） |
| `在第 N 行後加等待 DI[P]==ON` | 插入等待數位輸入 |
| `在第 N 行後加 DO[P]=ON` | 插入設定數位輸出 |

### 查詢解釋

| 指令 | 效果 |
|------|------|
| `解釋第 N 行` | 顯示該行的轉換邏輯說明 |
| `解釋第 A 到 B 行` | 顯示範圍內的轉換說明 |

> **提示：** 以上指令由規則引擎處理，不需要 Ollama 即可使用。啟用 Ollama 後可使用更自由的自然語言描述。

---

## 8. 新增品牌擴充指南

### 方式一：YAML 定義（簡單品牌）

適用於語法結構簡單、命令與 IR 有直接對應的品牌。

1. 在 `brands/` 目錄下建立新資料夾：

```
brands/
  new_brand/
    definition.yaml
```

2. 編寫 `definition.yaml`：

```yaml
brand: NEW_BRAND
description: "新品牌控制器"
file_extensions: [".nb", ".prog"]
comment_prefix: "#"

units:
  linear: mm
  angular: deg
  velocity_linear: mm/s
  time: ms

commands:
  move_joint:
    ir_action: move_joint
    pattern: "MOVJ\\s+P(\\d+)\\s+VJ=(\\d+)"
    emit_template: "MOVJ P{point} VJ={velocity}"
    description: "關節移動"

  move_linear:
    ir_action: move_linear
    pattern: "MOVL\\s+P(\\d+)\\s+V=(\\d+)"
    emit_template: "MOVL P{point} V={velocity}"
    description: "直線移動"

  # ... 其他命令
```

3. 驗證定義：

```bash
python cli.py validate brands/new_brand/
```

4. 重新啟動程式，新品牌自動載入。

### 方式二：YAML + Python 插件（複雜品牌）

適用於語法複雜、需要特殊解析邏輯的品牌（如 RUBY）。

1. 除了 `definition.yaml`，另建 `parser.py` 和/或 `emitter.py`：

```
brands/
  complex_brand/
    definition.yaml
    parser.py       # 自訂解析器
    emitter.py      # 自訂生成器
```

2. `parser.py` 範例結構：

```python
from core.parser_base import BrandParser
from core.ir import IRProgram, MoveAction, MotionType

class ComplexBrandParser(BrandParser):
    def parse(self, script: str, program_name: str = "MAIN") -> IRProgram:
        program = IRProgram(name=program_name)
        for i, line in enumerate(script.splitlines(), 1):
            # 自訂解析邏輯
            ...
            program.actions.append(action)
        return program
```

3. `emitter.py` 範例結構：

```python
from core.emitter_base import BrandEmitter
from core.ir import IRProgram

class ComplexBrandEmitter(BrandEmitter):
    def emit(self, program: IRProgram) -> str:
        lines = []
        for action in program.actions:
            # 自訂生成邏輯
            ...
            lines.append(output_line)
        return "\n".join(lines)
```

系統啟動時會自動掃描 `brands/` 目錄並載入所有品牌插件。

---

## 9. 常見問題 FAQ

### Q1: 轉換結果出現 `[WARNING]` 是什麼意思？

代表該指令沒有直接的目標品牌對應（例如 RUBY 的 `POLISH_LINE` 在 ABB 中沒有等效指令）。這些行會保留為註解，需要工程師人工處理。

### Q2: Ollama 未連接也能使用嗎？

可以。核心轉換功能和常見對話指令（速度修改、刪除、插入等）都不依賴 Ollama。Ollama 僅用於更自由的自然語言對話。狀態列會顯示 `🟡 Ollama: 未連接（規則式模式）`。

### Q3: 如何啟動 Ollama？

```bash
# 安裝後在終端執行
ollama serve

# 確認模型已安裝
ollama list

# 如未安裝模型
ollama pull llama3.2:3b
```

### Q4: 轉換後的速度單位不對？

不同品牌使用不同的速度單位：
- FANUC: mm/sec（直線）、%（關節）
- ABB: mm/s
- KUKA: m/s（注意！比其他品牌小 1000 倍）
- RUBY: mm/s（直線）、deg/s（關節）

系統會自動進行單位轉換。如果發現異常，請在轉換報告中確認對照。

### Q5: 可以同時修改來源和目標劇本嗎？

- **來源劇本**（左欄）：可手動編輯，修改後需重新點擊「轉換」
- **目標劇本**（中欄）：可手動編輯，也可透過 AI 對話修改

### Q6: 對話修改會影響來源劇本嗎？

不會。所有對話修改都只作用在目標劇本上（透過 IR 層面修改後重新生成）。來源劇本始終保持原樣。

### Q7: 如何還原對話修改？

目前沒有「撤銷」功能。如需還原，重新點擊「▶ 轉換」即可從來源劇本重新生成。

### Q8: 支援批次轉換嗎？

CLI 目前支援單檔轉換。批次轉換可透過 shell 腳本實現：

```bash
# Linux / macOS
for f in scripts/*.ls; do
  python cli.py convert "$f" --to abb -o "output/$(basename "$f" .ls).mod"
done

# Windows PowerShell
Get-ChildItem scripts\*.ls | ForEach-Object {
  python cli.py convert $_.FullName --to abb -o "output\$($_.BaseName).mod"
}
```

### Q9: 程式出現錯誤怎麼辦？

1. 確認 Python 版本 >= 3.10
2. 確認所有依賴已安裝：`pip install -r requirements.txt`
3. 檢查品牌定義是否完整：`python cli.py validate brands/<品牌名>/`
4. 如 Web UI 無法啟動，確認 port 7860 未被佔用

---

## 附錄：專案目錄結構

```
script_tf/
├── cli.py                  # CLI 入口點
├── requirements.txt        # Python 依賴
├── core/                   # 核心引擎
│   ├── ir.py               #   中間表示 (IR) 資料結構
│   ├── parser_base.py      #   解析器基底類別
│   ├── emitter_base.py     #   生成器基底類別
│   ├── converter.py        #   轉換器（Parser→IR→Emitter）
│   ├── registry.py         #   品牌自動探索與註冊
│   └── validator.py        #   品牌定義驗證器
├── brands/                 # 品牌定義（可擴充）
│   ├── fanuc/
│   │   └── definition.yaml
│   ├── abb/
│   │   └── definition.yaml
│   ├── kuka/
│   │   └── definition.yaml
│   └── ruby/
│       ├── definition.yaml
│       ├── parser.py       #   自訂解析器
│       └── emitter.py      #   自訂生成器
├── llm/                    # AI 對話模組
│   ├── assistant.py        #   對話助手 + 劇本編輯器
│   └── prompts.py          #   LLM 提示詞模板
├── ui/                     # Web UI
│   └── app.py              #   Gradio 介面
├── examples/               # 範例劇本
│   ├── fanuc_sample.ls
│   └── ruby_sample.script
├── tests/                  # 測試
│   ├── test_converter.py
│   └── test_assistant.py
└── docs/                   # 文件
    └── user_manual.md      #   本手冊
```

---

> **Script TF** — 跨品牌機器人劇本轉換，一鍵完成。
