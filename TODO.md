我發現 `tdl` 有一個功能是
`tdl dl -f` 這樣的做法是可以直接從 export 的 json 文件下載東西
但我擔心未來這個功能會被刪除 所以我同時保留了原本的 `download_media`, 做了一個 `download_media_from_file`

但我不確定目前寫法和流程正不正確 好像有點亂 請你幫我 refactor 一下

新的流程應該是
export chat data -> 確認本地是否有這個文件 -> 標記 downloaded -> 將沒 downloaded 的那些欄位保存下來 -> 將這個 temp 路徑保存 -> tdl 執行 -f 指令 -> 刪除 temp 文件

我想請你看一下有沒有更好的寫法同時保留 `download_media` 和 `download_media_from_file`
並且確保兩個 function 都是可以跳過已下載的文件
雖然 tdl 有提供 --skip-same, 但我不希望依賴這個功能 我想要自己紀錄
