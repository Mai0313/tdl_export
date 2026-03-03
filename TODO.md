請幫我修改一下 main.py

目前我有新增一個 `downloaded` 到 `Message` 的 model 中，這個欄位是用來表示檔案是否已經下載了
我的計畫是
- 讀取 `./data/{group_id}.json`
- 執行 `tdl chat export ...` 並與 `./data/{group_id}.json` 合併
- 將合併完畢的 `./data/{group_id}.json` 加上 `downloaded` 欄位 (預設 False) 後重新存檔覆蓋
    - 但要注意 假設是 `True` 就不用覆寫掉
- 開始迴圈執行 `tdl download --url ...`, 跳過 `downloaded` 為 `True` 的
- 下載完畢以後將對應的 downloaded 改成 True
- 迴圈全部結束以後存一次修改過後的 `./data/{group_id}.json` 文件

但要注意一個問題, 在 `tdl download` 時, 我有透過 `--group` 讓 `tdl` 自動判定哪一些是 grouped 的影片跟圖片 它會自動一起下載
所以標記 downloaded 的時候 要把 date 完全相同的也一起標記成 True
