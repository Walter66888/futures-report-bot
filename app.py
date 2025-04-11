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
from datetime import datetime
import PyPDF2

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

logger = logging.getLogger(__name__)

@app.route("/test-permissions", methods=['GET'])
def test_permissions():
    """測試檔案系統權限"""
    results = {}
    
    # 測試 pdf_files 目錄
    try:
        os.makedirs("pdf_files", exist_ok=True)
        test_file_path = "pdf_files/permission_test.txt"
        with open(test_file_path, 'w') as f:
            f.write("權限測試")
        with open(test_file_path, 'r') as f:
            content = f.read()
        os.remove(test_file_path)
        results["pdf_files"] = "成功 (建立、寫入、讀取和刪除)"
    except Exception as e:
        results["pdf_files"] = f"失敗: {str(e)}"
    
    # 測試 report_cache.json
    try:
        with open("report_cache.json", 'w') as f:
            f.write('{"test": true}')
        with open("report_cache.json", 'r') as f:
            content = f.read()
        results["report_cache.json"] = "成功 (寫入和讀取)"
    except Exception as e:
        results["report_cache.json"] = f"失敗: {str(e)}"
    
    logger.info(f"檔案系統權限測試結果: {results}")
    return str(results)

@app.route("/test-cache", methods=['GET'])
def test_cache():
    """測試緩存讀寫"""
    try:
        from datetime import datetime
        import json
        import pytz
        
        TW_TIMEZONE = pytz.timezone('Asia/Taipei')
        CACHE_FILE = "report_cache.json"
        
        # 嘗試寫入緩存
        test_data = {"test": "data", "timestamp": datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S')}
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False)
        
        # 嘗試讀取緩存
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                read_data = json.load(f)
            return f"緩存讀寫測試成功。寫入: {test_data}, 讀取: {read_data}"
        else:
            return "緩存寫入成功但無法找到文件"
    except Exception as e:
        return f"測試緩存時出錯: {str(e)}"

@app.route("/check-pdf", methods=['GET'])
def check_pdf():
    """检查PDF文件内容"""
    try:
        date_str = request.args.get('date', datetime.now(TW_TIMEZONE).strftime('%Y%m%d'))
        pdf_type = request.args.get('type', 'fubon')
        
        if pdf_type not in ['fubon', 'sinopac']:
            return "无效的PDF类型，请选择 'fubon' 或 'sinopac'", 400
        
        pdf_path = f"pdf_files/{pdf_type}_{date_str}.pdf"
        
        if not os.path.exists(pdf_path):
            return f"PDF文件不存在: {pdf_path}", 404
        
        # 尝试使用PyPDF2读取PDF
        try:
            with open(pdf_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page].extract_text()
            
            # 获取PDF基本信息
            page_count = len(pdf_reader.pages)
            text_length = len(text)
            
            # 返回PDF文本预览
            preview = text[:1000] + ("..." if len(text) > 1000 else "")
            
            # 测试一些关键正则表达式
            import re
            
            # 测试加权指数正则
            taiex_matches = []
            taiex_patterns = [
                r"加權指數\s+(\d+\.\d+)\s+[▲▼]\s*(\d+\.\d+)\s*\(\s*(\d+\.\d+)%\)",
                r"加權指數[:\s]+(\d+[\.,]\d+)\s*[▲▼]\s*(\d+[\.,]\d+)\s*\(\s*([+-]?\d+[\.,]\d+)%\)",
                r"加權指數.*?(\d+\.\d+).*?(\d+\.\d+).*?(\d+\.\d+)%"
            ]
            
            for pattern in taiex_patterns:
                match = re.search(pattern, text)
                if match:
                    taiex_matches.append({
                        'pattern': pattern,
                        'groups': match.groups()
                    })
            
            # 三大法人买卖超正则
            insti_matches = []
            insti_patterns = [
                r"三大法人買賣超\s*\(億\)\s+\+?(-?\d+\.\d+)",
                r"三大法人買賣超.*?(\+?-?\d+\.\d+)",
                r"三大法人.*?(\+?-?\d+\.\d+)"
            ]
            
            for pattern in insti_patterns:
                match = re.search(pattern, text)
                if match:
                    insti_matches.append({
                        'pattern': pattern,
                        'groups': match.groups()
                    })
            
            return f"""
            <h1>PDF文件检查结果</h1>
            <p>文件: {pdf_path}</p>
            <p>页数: {page_count}</p>
            <p>提取文本长度: {text_length}</p>
            
            <h2>加权指数正则匹配结果:</h2>
            <pre>{taiex_matches}</pre>
            
            <h2>三大法人正则匹配结果:</h2>
            <pre>{insti_matches}</pre>
            
            <h2>文本预览:</h2>
            <pre style="white-space: pre-wrap; word-wrap: break-word;">{preview}</pre>
            """
        except Exception as pdf_error:
            return f"读取PDF文件失败: {str(pdf_error)}", 500
        
    except Exception as e:
        return f"检查PDF时出错: {str(e)}", 500

# LINE Bot 設定
try:
    line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
    handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))
    logger.info("LINE Bot 初始化成功")
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
    
    logger.info(f"收到來自 {user_id} 的訊息: {text}")
    
    # 判斷是否為私人訊息和密語
    if event.source.type == 'user' and text == SECRET_COMMAND:
        logger.info(f"檢測到密語命令: {text}")
        handle_line_message(line_bot_api, event, is_secret_command=True)
    else:
        # 嘗試匹配歷史日期查詢
        import re
        from handlers.line_handler import DATE_COMMAND_PATTERN
        date_match = re.match(DATE_COMMAND_PATTERN, text)
        if date_match:
            date_str = date_match.group(1)
            logger.info(f"檢測到歷史日期查詢: {date_str}")
            handle_line_message(line_bot_api, event)
        # 其他訊息處理，在開發階段可用於測試
        elif os.environ.get('FLASK_ENV') == 'development':
            handle_line_message(line_bot_api, event)
        else:
            # 檢查是否包含其他密語關鍵字
            from handlers.line_handler import COMMAND_MAPPING
            for cmd in COMMAND_MAPPING.keys():
                if cmd in text:
                    logger.info(f"檢測到專門報告關鍵字: {cmd}")
                    handle_line_message(line_bot_api, event)
                    break

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
