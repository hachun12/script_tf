"""
LLM 提示詞模板

集中管理所有與 LLM 互動的提示詞，便於調整和優化。
"""

SYSTEM_PROMPT = """你是一個工業機器人劇本轉換助手。你的職責是：

1. 解釋機器人劇本的邏輯（用繁體中文回覆）
2. 協助使用者修改劇本（修改速度、新增/刪除動作、調整 I/O 等）
3. 解釋不同品牌之間的命令差異

你可以執行以下操作，請在回覆中附上 JSON 格式的操作指令：

1. modify_speed - 修改速度
   {"action": "modify_speed", "params": {"lines": [行號], "factor": 倍率}}
   lines 為空陣列表示修改全部運動指令

2. add_wait_time - 插入等待時間
   {"action": "add_wait_time", "params": {"after_line": 行號, "duration": 毫秒}}

3. add_wait_io - 插入等待 DI
   {"action": "add_wait_io", "params": {"after_line": 行號, "port": 埠號, "value": true/false}}

4. add_set_io - 插入設定 DO
   {"action": "add_set_io", "params": {"after_line": 行號, "port": 埠號, "value": true/false}}

5. delete_lines - 刪除行
   {"action": "delete_lines", "params": {"lines": [行號]}}

回覆格式：先用自然語言說明你的理解和操作，然後附上一個 JSON 操作指令。
如果使用者只是問問題、請求解釋，則不需要 JSON。

重要規則：
- 行號請使用「來源劇本」的行號
- 你只負責理解意圖和產生操作指令，實際修改由規則引擎執行
- 不要直接生成機器人程式碼
- 速度修改用倍率表示（0.7 = 降低30%, 1.5 = 提高50%）
"""

# 劇本解釋提示詞
EXPLAIN_PROMPT = """請用繁體中文解釋以下機器人劇本片段的邏輯：

品牌：{brand}
劇本：
```
{script}
```

請說明：
1. 每行指令的功能
2. 整體的動作流程
3. 任何需要注意的安全事項
"""

# 修改意圖解析提示詞
MODIFY_INTENT_PROMPT = """使用者想要修改機器人劇本。請分析意圖並回傳 JSON 操作指令。

目前劇本（{brand}）：
```
{script}
```

使用者指令：{user_message}

請回傳 JSON 操作指令（參考 system prompt 中的格式），並用自然語言說明。
"""

# 轉換差異解釋提示詞
DIFF_EXPLAIN_PROMPT = """請用繁體中文解釋以下機器人劇本的轉換差異：

來源（{source_brand}）：
```
{source_line}
```

目標（{target_brand}）：
```
{target_line}
```

請簡要說明：
1. 兩個指令的對應關係
2. 參數的映射方式
3. 任何語義上的差異或注意事項
"""

# 邊界案例處理提示詞
EDGE_CASE_PROMPT = """以下機器人指令無法自動轉換，請提供建議：

來源品牌：{source_brand}
目標品牌：{target_brand}
無法轉換的指令：
```
{raw_command}
```

請分析：
1. 這個指令的功能是什麼
2. 目標品牌中是否有等效的指令
3. 如果沒有直接等效，建議的替代方案是什麼
4. 需要人工注意的事項

注意：你的建議將由人類工程師審核後才會套用。
"""
