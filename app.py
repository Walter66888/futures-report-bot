"""
台灣期貨盤後籌碼快報 LINE Bot
自動監控富邦期貨和永豐期貨的盤後籌碼報告，並整合成統一格式推送到 LINE
"""
import os
import logging
import threading
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import pytz
from dotenv import load_dotenv

from crawlers.fubon_crawler import check_fubon_futures_report
from crawlers.sinopac_crawler import check_sinopac_futures_report
from handlers.line_handler import handle_line_message
from handlers.report_handler import monitor_futures_reports

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

app = Flask(__name__)

# LINE Bot 設定
try:
    line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
    handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))
except Exception as e:
    logger.error(f"LINE Bot 初始化錯誤: {str(e)}")
    # 在開發環境中，使用假的 LINE Bot API
    if os.environ.get('FLASK_ENV') == 'development':
        class DummyLineBotApi:
            def reply_message(self, *args, **kwargs):
                logger.info(f"DUMMY: reply_message({args}, {kwargs})")
                
            def push_message(self, *args, **kwargs):
                logger.info(f"DUMMY: push_message({args}, {kwargs})")
                
        line_bot_api = DummyLineBotApi()
        handler = None
    else:
        raise

# 設定密語 - 用於觸發私人訊息報告
SECRET_COMMAND = "盤後籌碼2025"  # 你可以自訂這個密語

@app.route("/callback", methods=['POST'])
def callback():
    """LINE Bot Webhook 回調函數"""
    if not handler:
        return 'LINE BOT not configured', 500
    
    # 獲取 X-Line-Signature 標頭
    signature = request.headers['X-Line-Signature']

    # 獲取請求體
    body = request.get_data(as_text=True)
    logger.info("Request body: " + body)

    # 處理 webhook
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理使用者發送的文字訊息"""
    text = event.message.text.strip()
    user_id = event.source.user_id
    
    # 判斷是否為私人訊息和密語
    if event.source.type == 'user' and text == SECRET_COMMAND:
        handle_line_message(line_bot_api, event, is_secret_command=True)
    else:
        # 其他訊息處理，在開發階段可用於測試
        if os.environ.get('FLASK_ENV') == 'development':
            handle_line_message(line_bot_api, event)

@app.route("/", methods=['GET'])
def index():
    """首頁"""
    return "台灣期貨盤後籌碼快報 LINE Bot 正在運行！"

@app.route("/test", methods=['GET'])
def test():
    """測試頁面，用於開發環境測試"""
    if os.environ.get('FLASK_ENV') != 'development':
        return "測試端點在生產環境中已停用", 403
    
    try:
        # 測試富邦爬蟲
        fubon_result = check_fubon_futures_report()
        fubon_status = "成功" if fubon_result else "失敗/尚未更新"
        
        # 測試永豐爬蟲
        sinopac_result = check_sinopac_futures_report()
        sinopac_status = "成功" if sinopac_result else "失敗/尚未更新"
        
        return f"""
        <h1>爬蟲測試結果</h1>
        <p>富邦期貨爬蟲: {fubon_status}</p>
        <p>永豐期貨爬蟲: {sinopac_status}</p>
        """
    except Exception as e:
        return f"測試時發生錯誤: {str(e)}", 500

def setup_reports_monitor():
    """設置報告監控器"""
    group_id = os.environ.get('LINE_GROUP_ID')
    if not group_id:
        logger.warning("未設定 LINE_GROUP_ID 環境變數，僅支援私人訊息觸發")
    
    # 在背景執行監控
    monitor_thread = threading.Thread(
        target=monitor_futures_reports,
        args=(line_bot_api, group_id),
        daemon=True
    )
    monitor_thread.start()
    logger.info("期貨報告監控器已啟動")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    setup_reports_monitor()  # 設置報告監控
    app.run(host='0.0.0.0', port=port)
