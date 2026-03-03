請幫我修改一下 main.py

目前我有新增一個 `downloaded` 到 `Message` 的 model 中，這個欄位是用來表示檔案是否已經下載了
我的計畫是

- 讀取 `./data/{group_id}.json` 變成 `original_chat_data`
- 執行 `tdl chat export ...` 輸出成 `./data/{group_id}_new.json` 並讀取成 `new_chat_data`
- 將 `original_chat_data` 與 `new_chat_data` 合併成 `combined_chat_data`，合併的邏輯是以 `id` 和 `datetime` 為基準
- 將 `combined_chat_data` 先進行存檔, 覆蓋掉 `./data/{group_id}.json`, 並刪除 `./data/{group_id}_new.json` 方便後續使用
- 開始迴圈執行 `tdl download --url ...`, 跳過 `downloaded` 為 `True` 的
- 下載完畢以後將對應的 downloaded 改成 True
- 迴圈全部結束以後存一次修改過後的 `./data/{group_id}.json` 文件
