# 台灣期貨盤後籌碼快報 LINE Bot

自動監控富邦期貨和永豐期貨的盤後籌碼報告，並整合成統一格式推送到 LINE。

## 功能

- 自動監控富邦期貨和永豐期貨兩個來源的盤後籌碼報告
- 每個交易日 14:45 開始定時檢查報告更新
- 兩份報告都更新後，自動整合數據並推送到 LINE 群組
- 支援私人訊息密語觸發，隨時查看最新籌碼報告

## 環境需求

- Python 3.9 或更高版本
- 以下 Python 套件：
  - Flask
  - LINE Bot SDK
  - Requests
  - BeautifulSoup4
  - PyPDF2
  - pdf2image
  - Pillow
  - 其他（見 requirements.txt）

## 安裝與設定

### 1. 複製專案

```bash
git clone https://github.com/你的用戶名/futures-report-bot.git
cd futures-report-bot
```

### 2. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數

建立 `.env` 檔案並填入以下內容：

```
LINE_CHANNEL_ACCESS_TOKEN=你的LINE Bot頻道存取權杖
LINE_CHANNEL_SECRET=你的LINE Bot頻道密鑰
LINE_GROUP_ID=要推送訊息的群組ID
FLASK_ENV=production
PORT=5000
```

### 4. 啟動服務

```bash
python app.py
```

## Render 部署說明

1. 登入 [Render](https://render.com/)
2. 建立新的 Web Service
3. 連結到你的 GitHub 專案
4. 設定以下資訊：
   - Name: futures-report-bot
   - Runtime: Python 3.9
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. 新增環境變數（同上述 .env 檔案的內容）
6. 點擊「Create Web Service」

## 使用說明

1. 將 LINE Bot 加為好友
2. 邀請 Bot 加入群組（如需群組推送功能）
3. 每個交易日下午，Bot 會自動監控並推送期貨籌碼報告
4. 在私人訊息中發送密語指令「盤後籌碼2025」可立即獲取最新報告

## 密語觸發

- 私人訊息中輸入「盤後籌碼2025」可觸發 Bot 回傳最新籌碼報告
- 密語可在 app.py 中的 SECRET_COMMAND 變數修改

## 授權

MIT

## 免責聲明

本程式僅供參考，不構成任何投資建議。使用者應自行判斷投資決策，並承擔相關風險。
