我發現 `tdl` 有一個功能是
`tdl dl -f` 這樣的做法是可以直接從 export 的 json 文件下載東西
但我擔心未來這個功能會被刪除 所以我同時保留了原本的 `download_media`, 做了一個 `download_media_from_file`

但我不確定目前寫法和流程正不正確 好像有點亂 請你幫我 refactor 一下

新的流程應該是
export chat data -> 確認本地是否有這個文件 -> 標記 downloaded -> 將沒 downloaded 的那些欄位保存下來 -> 將這個 temp 路徑保存 -> tdl 執行 -f 指令 -> 刪除 temp 文件

目前我已經將兩個 function 整合成一個 `download_media`
但我發現最後面

```
    result = check_chat_data(path=download_path, chat_data=combined_chat_data)
    save_chat_data(path=original_chat_path, chat_data=result)
```

存檔時 只存到了 downloaded = True 的那些資訊 我不確定到底是哪裡出問題 請你幫我調查
