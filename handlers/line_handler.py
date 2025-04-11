"""
LINE 訊息處理模組
"""
import os
import re
import logging
import threading
import json
from datetime import datetime, timedelta
import pytz
from linebot.models import TextSendMessage
from .report_handler import generate_report_text, get_latest_report_data, generate_specialized_report
from crawlers.fubon_crawler import check_fubon_futures_report, extract_fubon_report_data
from crawlers.sinopac_crawler import check_sinopac_futures_report, extract_sinopac_report_data
from crawlers.utils import is_trading_day, get_trading_days

# 設定日誌
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

# 密語指令映射表 (指令 -> 報告類型)
COMMAND_MAPPING = {
    '期貨籌碼': 'futures',
    '選擇權籌碼': 'options',
    '三大法人籌碼': 'institutional',
    '散戶籌碼': 'retail',
    '完整籌碼報告': 'full'
}

# 主密語
MAIN_SECRET_COMMAND = "盤後籌碼2025"

# 歷史查詢密語格式
DATE_COMMAND_PATTERN = r"盤後籌碼-(\d{8})"

# 管理員特殊命令 - 抓取歷史數據
ADMIN_FETCH_COMMAND = "盤後籌碼管理員-開始抓取歷史數據X9527"

# 查詢已抓取數據的命令
LIST_AVAILABLE_COMMAND = "盤後籌碼-列表"

# 查詢爬取狀態的命令
CRAWL_STATUS_COMMAND = "盤後籌碼-狀態"

# 報告快取，格式為 {'日期': {'fubon': {...}, 'sinopac': {...}, 'combined': {...}}}
REPORT_CACHE = {}

# 爬取統計
CRAWL_STATS = {
    'last_run': None,
    'total_attempts': 0,
    'success_count': 0,
    'failed_dates': {},  # {date_str: {'fubon': error, 'sinopac': error}}
    'in_progress': False,
    'current_progress': 0,
    'total_tasks': 0
}

# 正在處理的日期請求
PROCESSING_DATES = set()

# 是否正在進行大規模歷史數據抓取
IS_FETCHING_HISTORY = False

# 確保快取目錄存在
os.makedirs("pdf_files", exist_ok=True)

# 快取檔案路徑
CACHE_FILE = "report_cache.json"

# 載入快取
def load_cache():
    """載入報告快取"""
    global REPORT_CACHE
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                REPORT_CACHE = json.load(f)
            logger.info(f"已從 {CACHE_FILE} 載入 {len(REPORT_CACHE)} 個日期的報告快取")
    except Exception as e:
        logger.error(f"載入快取時出錯: {str(e)}")

# 保存快取
def save_cache():
    """保存報告快取"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(REPORT_CACHE, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存 {len(REPORT_CACHE)} 個日期的報告快取到 {CACHE_FILE}")
    except Exception as e:
        logger.error(f"保存快取時出錯: {str(e)}")

# 初始化時載入快取
load_cache()

def handle_line_message(line_bot_api, event, is_secret_command=False):
    """
    處理LINE訊息
    
    Args:
        line_bot_api: LINE Bot API實例
        event: LINE訊息事件
        is_secret_command: 是否為密語指令
    """
    try:
        text = event.message.text.strip()
        reply_token = event.reply_token
        
        logger.info(f"收到訊息: {text}, reply_token: {reply_token}")
        
        # 取得用戶ID
        if event.source.type == 'user':
            user_id = event.source.user_id
            target_id = user_id  # 私人訊息回覆
            is_private = True
            logger.info(f"從用戶 {user_id} 收到私人訊息")
        elif event.source.type == 'group':
            group_id = event.source.group_id
            target_id = group_id  # 群組訊息回覆
            is_private = False
            logger.info(f"從群組 {group_id} 收到訊息")
        elif event.source.type == 'room':
            room_id = event.source.room_id
            target_id = room_id  # 聊天室訊息回覆
            is_private = False
            logger.info(f"從聊天室 {room_id} 收到訊息")
        else:
            logger.warning(f"未知的訊息來源類型: {event.source.type}")
            return
        
        # 匹配管理員特殊命令 - 抓取歷史數據
        if text == ADMIN_FETCH_COMMAND and is_private:
            logger.info(f"收到管理員特殊命令: {text}")
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="收到歷史數據抓取命令，即將開始執行...")
            )
            start_historical_fetch(line_bot_api, target_id)
            return
        
        # 匹配查詢已抓取數據的命令
        if text == LIST_AVAILABLE_COMMAND:
            logger.info(f"收到查詢可用報告列表命令: {text}")
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="正在查詢可用的報告列表，請稍候...")
            )
            list_available_reports(line_bot_api, target_id)
            return
        
        # 匹配查詢爬取狀態的命令
        if text == CRAWL_STATUS_COMMAND and is_private:
            logger.info(f"收到查詢爬取狀態命令: {text}")
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="正在獲取爬取狀態，請稍候...")
            )
            show_crawl_status(line_bot_api, target_id)
            return
        
        # 處理密語指令 - 發送最新報告
        if is_secret_command or text == MAIN_SECRET_COMMAND:
            logger.info(f"收到主密語命令: {text}")
            # 主密語 - 發送基本籌碼報告
            send_latest_report(line_bot_api, target_id, reply_token)
            return
        
        # 檢查是否為歷史日期查詢
        date_match = re.match(DATE_COMMAND_PATTERN, text)
        if date_match:
            date_str = date_match.group(1)  # 格式為 YYYYMMDD
            logger.info(f"收到歷史日期查詢: {date_str}")
            try:
                # 轉換為日期物件
                year = int(date_str[:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                query_date = datetime(year, month, day, tzinfo=TW_TIMEZONE)
                
                # 檢查是否為有效的交易日
                if not is_trading_day(query_date):
                    logger.info(f"{date_str} 不是交易日")
                    line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text=f"{query_date.strftime('%Y/%m/%d')} 不是交易日，無法查詢籌碼資料。")
                    )
                    return
                
                # 立即回覆，避免超時
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=f"正在獲取 {query_date.strftime('%Y/%m/%d')} 的籌碼報告，請稍候...")
                )
                
                # 在背景執行查詢，避免阻塞和超時
                thread = threading.Thread(
                    target=send_date_report_async,
                    args=(line_bot_api, target_id, query_date),
                    daemon=True
                )
                thread.start()
                return
            except ValueError as e:
                logger.error(f"日期格式解析錯誤: {str(e)}")
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="日期格式錯誤，請使用「盤後籌碼-YYYYMMDD」格式查詢，例如：盤後籌碼-20250410")
                )
                return
        
        # 在私人訊息中處理其他密語指令
        if is_private:
            # 檢查是否為專門的密語指令
            for cmd, report_type in COMMAND_MAPPING.items():
                if cmd in text:
                    logger.info(f"收到專門報告密語命令: {cmd}")
                    line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text=f"正在獲取{cmd}報告，請稍候...")
                    )
                    send_specialized_report(line_bot_api, target_id, report_type)
                    return
                
            # 關鍵字分析，判斷用戶想要的是哪種報告
            from templates.specialized_reports import REPORT_KEYWORDS
            matched_type = None
            
            # 檢查文字中是否包含特定報告類型的關鍵字
            for report_type, keywords in REPORT_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in text:
                        matched_type = report_type
                        break
                if matched_type:
                    break
            
            # 如果找到匹配的報告類型，發送對應的專門報告
            if matched_type:
                logger.info(f"根據關鍵字匹配到報告類型: {matched_type}")
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=f"正在獲取{COMMAND_MAPPING.get(matched_type, '籌碼')}報告，請稍候...")
                )
                send_specialized_report(line_bot_api, target_id, matched_type)
                return
    
    except Exception as e:
        logger.error(f"處理LINE訊息時出錯: {str(e)}", exc_info=True)
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="處理您的訊息時發生錯誤，請稍後再試。")
            )
        except Exception as reply_error:
            logger.error(f"回覆錯誤訊息時也失敗: {str(reply_error)}", exc_info=True)

def send_latest_report(line_bot_api, target_id, reply_token=None):
    """
    發送最新籌碼報告
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
        reply_token: 回覆令牌，若提供則使用reply_message
    """
    try:
        # 獲取今日日期
        today = datetime.now(TW_TIMEZONE).strftime('%Y%m%d')
        logger.info(f"嘗試獲取今日({today})報告")
        
        # 檢查快取中是否有今日報告
        if today in REPORT_CACHE and REPORT_CACHE[today].get('combined'):
            logger.info(f"使用快取的今日報告: {today}")
            report_text = generate_report_text(REPORT_CACHE[today]['combined'])
            
            if reply_token:
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=report_text)
                )
            else:
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=report_text)
                )
            return
        
        # 獲取最新報告數據
        report_data = get_latest_report_data()
        
        if not report_data:
            logger.info("沒有最新報告數據")
            # 檢查是否有最近的報告
            available_dates = get_available_dates()
            recent_date = get_most_recent_date(available_dates)
            
            if recent_date:
                # 告知用戶尚無最新報告，但提供最近的報告
                message = (
                    "目前尚未有今日的籌碼報告。\n\n"
                    f"最近的報告是 {recent_date[:4]}/{recent_date[4:6]}/{recent_date[6:8]} 的報告。\n"
                    f"您可以輸入「盤後籌碼-{recent_date}」查看該日報告，\n"
                    f"或輸入「盤後籌碼-列表」查看所有可用的報告日期。"
                )
            else:
                # 告知用戶尚無任何報告
                message = (
                    "目前系統中尚未有任何籌碼報告。\n\n"
                    "您可以使用「盤後籌碼-YYYYMMDD」格式查詢特定日期的報告，"
                    "例如：盤後籌碼-20250410"
                )
            
            if reply_token:
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=message)
                )
            else:
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=message)
                )
            return
        
        # 生成報告文字
        report_text = generate_report_text(report_data)
        
        # 發送報告
        if reply_token:
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=report_text)
            )
        else:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=report_text)
            )
        
        logger.info(f"成功發送籌碼報告給目標: {target_id}")
    
    except Exception as e:
        logger.error(f"發送籌碼報告時出錯: {str(e)}", exc_info=True)
        try:
            if reply_token:
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="發送報告時出錯，請稍後再試。錯誤詳情: " + str(e))
                )
            else:
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text="發送報告時出錯，請稍後再試。")
                )
        except Exception as send_error:
            logger.error(f"發送錯誤訊息時也失敗: {str(send_error)}", exc_info=True)

def send_date_report_async(line_bot_api, target_id, query_date):
    """
    非同步發送指定日期的籌碼報告
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
        query_date: 查詢日期（datetime對象）
    """
    try:
        date_str = query_date.strftime('%Y%m%d')
        logger.info(f"非同步處理日期 {date_str} 的報告查詢")
        
        # 檢查是否已經在處理同一日期
        if date_str in PROCESSING_DATES:
            logger.info(f"日期 {date_str} 已有另一個請求正在處理")
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"已有另一個請求正在處理 {query_date.strftime('%Y/%m/%d')} 的報告，請稍候...")
            )
            return
        
        # 標記為正在處理
        PROCESSING_DATES.add(date_str)
        
        try:
            send_date_report(line_bot_api, target_id, query_date)
        finally:
            # 無論成功與否，都移除處理標記
            PROCESSING_DATES.remove(date_str)
            logger.info(f"完成處理日期 {date_str} 的報告查詢")
    
    except Exception as e:
        logger.error(f"非同步發送歷史籌碼報告時出錯: {str(e)}", exc_info=True)
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"處理 {query_date.strftime('%Y/%m/%d')} 的報告時出錯，請稍後再試。錯誤詳情: {str(e)}")
            )
        except Exception as push_error:
            logger.error(f"嘗試發送錯誤訊息時也失敗: {str(push_error)}", exc_info=True)

def send_date_report(line_bot_api, target_id, query_date):
    """
    發送指定日期的籌碼報告
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
        query_date: 查詢日期（datetime對象）
    """
    try:
        date_str = query_date.strftime('%Y%m%d')
        formatted_date = query_date.strftime('%Y/%m/%d')
        logger.info(f"開始處理 {date_str} 的報告")
        
        # 檢查快取中是否有此日期的報告
        if date_str in REPORT_CACHE and REPORT_CACHE[date_str].get('combined'):
            logger.info(f"使用快取的報告: {date_str}")
            report_text = generate_report_text(REPORT_CACHE[date_str]['combined'])
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=report_text)
            )
            return
        
        # 更新爬取統計
        CRAWL_STATS['total_attempts'] += 1
        
        # 構建檔案名稱
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        # 嘗試獲取富邦報告
        fubon_data = None
        fubon_error = None
        fubon_pdf_path = f"pdf_files/fubon_{date_str}.pdf"
        if os.path.exists(fubon_pdf_path):
            # 如果已存在，直接解析
            logger.info(f"找到富邦報告文件: {fubon_pdf_path}")
            try:
                fubon_data = extract_fubon_report_data(fubon_pdf_path)
                if not fubon_data:
                    fubon_error = "解析PDF失敗"
                    logger.error(f"解析富邦PDF失敗: {fubon_pdf_path}")
            except Exception as e:
                fubon_error = str(e)
                logger.error(f"解析富邦期貨 {date_str} 報告時出錯: {str(e)}", exc_info=True)
        else:
            logger.info(f"未找到富邦報告文件，嘗試下載: {fubon_pdf_path}")
            # 嘗試下載該日期的報告
            pdf_filename = f"TWPM_{year}.{month}.{day}.pdf"
            base_url = "https://www.fubon.com/futures/wcm/home/taiwanaferhours/image/taiwanaferhours/"
            pdf_url = f"{base_url}{pdf_filename}"
            
            import requests
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                logger.info(f"嘗試下載富邦報告: {pdf_url}")
                response = requests.get(pdf_url, headers=headers, timeout=30)
                
                if response.status_code == 200 and response.headers.get('Content-Type', '').lower().startswith('application/pdf'):
                    logger.info(f"成功獲取富邦報告，狀態碼: {response.status_code}")
                    # 確保目錄存在
                    os.makedirs("pdf_files", exist_ok=True)
                    
                    # 保存 PDF
                    with open(fubon_pdf_path, 'wb') as f:
                        f.write(response.content)
                    
                    logger.info(f"富邦PDF保存成功: {fubon_pdf_path}")
                    
                    # 解析數據
                    fubon_data = extract_fubon_report_data(fubon_pdf_path)
                    if not fubon_data:
                        fubon_error = "解析PDF失敗"
                        logger.error(f"解析富邦PDF失敗: {fubon_pdf_path}")
                else:
                    fubon_error = f"HTTP狀態碼: {response.status_code}"
                    logger.warning(f"富邦報告下載失敗，狀態碼: {response.status_code}")
                    line_bot_api.push_message(
                        target_id,
                        TextSendMessage(text=f"無法從富邦期貨獲取 {formatted_date} 的報告 (狀態碼: {response.status_code})，嘗試其他來源...")
                    )
            except Exception as e:
                fubon_error = str(e)
                logger.error(f"下載富邦期貨 {date_str} 報告失敗: {str(e)}", exc_info=True)
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=f"獲取富邦期貨 {formatted_date} 的報告時出錯，嘗試其他來源...")
                )
        
        # 嘗試獲取永豐報告
        sinopac_data = None
        sinopac_error = None
        sinopac_pdf_path = f"pdf_files/sinopac_{date_str}.pdf"
        if os.path.exists(sinopac_pdf_path):
            # 如果已存在，直接解析
            logger.info(f"找到永豐報告文件: {sinopac_pdf_path}")
            try:
                sinopac_data = extract_sinopac_report_data(sinopac_pdf_path)
                if not sinopac_data:
                    sinopac_error = "解析PDF失敗"
                    logger.error(f"解析永豐PDF失敗: {sinopac_pdf_path}")
            except Exception as e:
                sinopac_error = str(e)
                logger.error(f"解析永豐期貨 {date_str} 報告時出錯: {str(e)}", exc_info=True)
        else:
            logger.info(f"未找到永豐報告文件，嘗試下載: {sinopac_pdf_path}")
            # 嘗試從永豐網站下載歷史報告
            try:
                from bs4 import BeautifulSoup
                
                # 設定目標URL
                url = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
                
                # 使用進階的請求標頭和Session保持連接
                import requests
                session = requests.Session()
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0'
                }
                
                # 發送請求
                logger.info(f"嘗試訪問永豐網站: {url}")
                response = session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                # 使用BeautifulSoup解析HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 尋找報告連結
                report_links = []
                target_date = f"{year}/{month}/{day}"
                logger.info(f"尋找永豐網站上日期為 {target_date} 的報告")
                
                # 遍歷所有列表項
                for li in soup.find_all('li'):
                    # 查找a標籤
                    a_tags = li.find_all('a')
                    for a in a_tags:
                        if '台指期籌碼快訊' in a.text:
                            # 查找相鄰的span標籤，可能包含日期
                            span_tags = li.find_all('span')
                            for span in span_tags:
                                if target_date in span.text:
                                    href = a.get('href')
                                    if href:
                                        full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                                        report_links.append({
                                            'title': a.text.strip(),
                                            'url': full_url,
                                            'date': span.text.strip()
                                        })
                                        logger.info(f"找到永豐報告: {a.text.strip()} - {span.text.strip()}")
                
                # 如果找到報告，下載PDF
                if report_links:
                    # 下載PDF檔案
                    report = report_links[0]  # 取第一個符合條件的報告
                    logger.info(f"嘗試下載永豐報告: {report['url']}")
                    pdf_response = session.get(report['url'], headers=headers, timeout=30)
                    pdf_response.raise_for_status()
                    
                    # 保存PDF檔案
                    with open(sinopac_pdf_path, 'wb') as f:
                        f.write(pdf_response.content)
                    
                    logger.info(f"永豐PDF保存成功: {sinopac_pdf_path}")
                    
                    # 解析PDF數據
                    sinopac_data = extract_sinopac_report_data(sinopac_pdf_path)
                    if not sinopac_data:
                        sinopac_error = "解析PDF失敗"
                        logger.error(f"解析永豐PDF失敗: {sinopac_pdf_path}")
                else:
                    sinopac_error = "在網站上找不到符合日期的報告"
                    logger.info(f"永豐期貨 {date_str} 報告在網站上找不到")
            except Exception as e:
                sinopac_error = str(e)
                logger.error(f"下載永豐期貨 {date_str} 報告失敗: {str(e)}", exc_info=True)
        
        # 更新爬取統計
        if date_str not in CRAWL_STATS['failed_dates']:
            CRAWL_STATS['failed_dates'][date_str] = {}
        
        if fubon_error:
            CRAWL_STATS['failed_dates'][date_str]['fubon'] = fubon_error
            logger.warning(f"富邦報告處理失敗: {fubon_error}")
        if sinopac_error:
            CRAWL_STATS['failed_dates'][date_str]['sinopac'] = sinopac_error
            logger.warning(f"永豐報告處理失敗: {sinopac_error}")
        
        # 組合報告數據
        if fubon_data or sinopac_data:
            # 增加爬取成功計數
            CRAWL_STATS['success_count'] += 1
            logger.info(f"成功獲取 {date_str} 的報告數據")
            
            # 如果有任一報告數據，進行組合
            from .report_handler import combine_reports_data
            combined_data = combine_reports_data(fubon_data, sinopac_data)
            
            # 更新報告日期
            combined_data['date'] = formatted_date
            
            # 保存到快取
            REPORT_CACHE[date_str] = {
                'fubon': fubon_data,
                'sinopac': sinopac_data,
                'combined': combined_data,
                'last_update': datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S')
            }
            
            # 保存快取到檔案
            save_cache()
            logger.info(f"報告數據已保存到快取: {date_str}")
            
            # 生成報告文字
            report_text = generate_report_text(combined_data)
            
            # 發送報告
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=report_text)
            )
            
            logger.info(f"成功發送 {date_str} 的籌碼報告給目標: {target_id}")
            
            # 如果之前有錯誤記錄，現在成功了，移除錯誤記錄
            if date_str in CRAWL_STATS['failed_dates']:
                del CRAWL_STATS['failed_dates'][date_str]
        else:
            # 如果沒有找到任何報告
            logger.warning(f"無法獲取 {date_str} 的任何報告數據")
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"抱歉，無法獲取 {formatted_date} 的籌碼報告。該日可能不是交易日，或報告尚未發布。\n\n您可以輸入「盤後籌碼-列表」查看所有可用的報告日期。")
            )
    
    except Exception as e:
        logger.error(f"發送歷史籌碼報告時出錯: {str(e)}", exc_info=True)
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"獲取 {query_date.strftime('%Y/%m/%d')} 的報告時出錯，請稍後再試或嘗試其他日期。錯誤詳情: {str(e)}")
            )
        except Exception as push_error:
            logger.error(f"嘗試發送錯誤訊息時也失敗: {str(push_error)}", exc_info=True)

def start_historical_fetch(line_bot_api, target_id):
    """
    開始抓取歷史數據
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID）
    """
    global IS_FETCHING_HISTORY
    
    if IS_FETCHING_HISTORY:
        logger.warning("已有歷史數據抓取任務正在進行中")
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text="已有歷史數據抓取任務正在進行中，請等待完成。")
        )
        return
    
    logger.info("開始歷史數據抓取任務")
    line_bot_api.push_message(
        target_id,
        TextSendMessage(text="開始抓取歷史數據，這可能需要一段時間，請耐心等待。抓取完成後將通知您。")
    )
    
    # 在背景執行查詢，避免阻塞和超時
    thread = threading.Thread(
        target=fetch_historical_data_async,
        args=(line_bot_api, target_id),
        daemon=True
    )
    thread.start()

def fetch_historical_data_async(line_bot_api, target_id):
    """
    非同步抓取歷史數據
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID）
    """
    global IS_FETCHING_HISTORY
    
    try:
        IS_FETCHING_HISTORY = True
        CRAWL_STATS['in_progress'] = True
        CRAWL_STATS['last_run'] = datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S')
        logger.info("開始非同步歷史數據抓取")
        
        # 獲取最近3個月的交易日
        end_date = datetime.now(TW_TIMEZONE)
        start_date = end_date - timedelta(days=90)
        trading_days = get_trading_days(start_date, end_date)
        
        total_days = len(trading_days)
        CRAWL_STATS['total_tasks'] = total_days
        processed_days = 0
        success_days = 0
        
        # 每10個日期發送一次進度更新
        progress_interval = max(1, total_days // 10)
        
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"將抓取最近3個月的 {total_days} 個交易日數據...")
        )
        
        for date in trading_days:
            date_str = date.strftime('%Y%m%d')
            CRAWL_STATS['current_progress'] = processed_days
            logger.info(f"處理日期 {date_str} ({processed_days+1}/{total_days})")
            
            # 如果已有數據，則跳過
            if date_str in REPORT_CACHE and REPORT_CACHE[date_str].get('combined'):
                logger.info(f"日期 {date_str} 已有快取數據，跳過")
                processed_days += 1
                success_days += 1
                continue
            
            try:
                # 抓取該日期的報告
                year = date_str[:4]
                month = date_str[4:6]
                day = date_str[6:8]
                
                # 嘗試獲取富邦報告
                fubon_data = None
                fubon_error = None
                fubon_pdf_path = f"pdf_files/fubon_{date_str}.pdf"
                if os.path.exists(fubon_pdf_path):
                    # 如果已存在，直接解析
                    logger.info(f"找到富邦報告文件: {fubon_pdf_path}")
                    try:
                        fubon_data = extract_fubon_report_data(fubon_pdf_path)
                        if not fubon_data:
                            fubon_error = "解析PDF失敗"
                            logger.error(f"解析富邦PDF失敗: {fubon_pdf_path}")
                    except Exception as e:
                        fubon_error = str(e)
                        logger.error(f"解析富邦期貨 {date_str} 報告時出錯: {str(e)}", exc_info=True)
                else:
                    logger.info(f"未找到富邦報告文件，嘗試下載: {fubon_pdf_path}")
                    # 嘗試下載該日期的報告
                    pdf_filename = f"TWPM_{year}.{month}.{day}.pdf"
                    base_url = "https://www.fubon.com/futures/wcm/home/taiwanaferhours/image/taiwanaferhours/"
                    pdf_url = f"{base_url}{pdf_filename}"
                    
                    import requests
                    try:
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        logger.info(f"嘗試下載富邦報告: {pdf_url}")
                        response = requests.get(pdf_url, headers=headers, timeout=30)
                        
                        if response.status_code == 200 and response.headers.get('Content-Type', '').lower().startswith('application/pdf'):
                            logger.info(f"成功獲取富邦報告，狀態碼: {response.status_code}")
                            # 確保目錄存在
                            os.makedirs("pdf_files", exist_ok=True)
                            
                            # 保存 PDF
                            with open(fubon_pdf_path, 'wb') as f:
                                f.write(response.content)
                            
                            logger.info(f"富邦PDF保存成功: {fubon_pdf_path}")
                            
                            # 解析數據
                            fubon_data = extract_fubon_report_data(fubon_pdf_path)
                            if not fubon_data:
                                fubon_error = "解析PDF失敗"
                                logger.error(f"解析富邦PDF失敗: {fubon_pdf_path}")
                        else:
                            fubon_error = f"HTTP狀態碼: {response.status_code}"
                            logger.warning(f"富邦報告下載失敗，狀態碼: {response.status_code}")
                    except Exception as e:
                        fubon_error = str(e)
                        logger.error(f"下載富邦期貨 {date_str} 報告失敗: {str(e)}", exc_info=True)
                
                # 嘗試獲取永豐報告
                sinopac_data = None
                sinopac_error = None
                sinopac_pdf_path = f"pdf_files/sinopac_{date_str}.pdf"
                if os.path.exists(sinopac_pdf_path):
                    # 如果已存在，直接解析
                    logger.info(f"找到永豐報告文件: {sinopac_pdf_path}")
                    try:
                        sinopac_data = extract_sinopac_report_data(sinopac_pdf_path)
                        if not sinopac_data:
                            sinopac_error = "解析PDF失敗"
                            logger.error(f"解析永豐PDF失敗: {sinopac_pdf_path}")
                    except Exception as e:
                        sinopac_error = str(e)
                        logger.error(f"解析永豐期貨 {date_str} 報告時出錯: {str(e)}", exc_info=True)
                else:
                    logger.info(f"未找到永豐報告文件，嘗試下載: {sinopac_pdf_path}")
                    # 嘗試從永豐網站下載歷史報告
                    try:
                        from bs4 import BeautifulSoup
                        
                        # 設定目標URL
                        url = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
                        
                        # 使用進階的請求標頭和Session保持連接
                        session = requests.Session()
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Cache-Control': 'max-age=0'
                        }
                        
                        # 發送請求
                        logger.info(f"嘗試訪問永豐網站: {url}")
                        response = session.get(url, headers=headers, timeout=30)
                        response.raise_for_status()
                        
                        # 使用BeautifulSoup解析HTML
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # 尋找報告連結
                        report_links = []
                        target_date = f"{year}/{month}/{day}"
                        logger.info(f"尋找永豐網站上日期為 {target_date} 的報告")
                        
                        # 遍歷所有列表項
                        for li in soup.find_all('li'):
                            # 查找a標籤
                            a_tags = li.find_all('a')
                            for a in a_tags:
                                if '台指期籌碼快訊' in a.text:
                                    # 查找相鄰的span標籤，可能包含日期
                                    span_tags = li.find_all('span')
                                    for span in span_tags:
                                        if target_date in span.text:
                                            href = a.get('href')
                                            if href:
                                                full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                                                report_links.append({
                                                    'title': a.text.strip(),
                                                    'url': full_url,
                                                    'date': span.text.strip()
                                                })
                                                logger.info(f"找到永豐報告: {a.text.strip()} - {span.text.strip()}")
                        
                        # 如果找到報告，下載PDF
                        if report_links:
                            # 下載PDF檔案
                            report = report_links[0]  # 取第一個符合條件的報告
                            logger.info(f"嘗試下載永豐報告: {report['url']}")
                            pdf_response = session.get(report['url'], headers=headers, timeout=30)
                            pdf_response.raise_for_status()
                            
                            # 保存PDF檔案
                            with open(sinopac_pdf_path, 'wb') as f:
                                f.write(pdf_response.content)
                            
                            logger.info(f"永豐PDF保存成功: {sinopac_pdf_path}")
                            
                            # 解析PDF數據
                            sinopac_data = extract_sinopac_report_data(sinopac_pdf_path)
                            if not sinopac_data:
                                sinopac_error = "解析PDF失敗"
                                logger.error(f"解析永豐PDF失敗: {sinopac_pdf_path}")
                        else:
                            sinopac_error = "在網站上找不到符合日期的報告"
                            logger.info(f"永豐期貨 {date_str} 報告在網站上找不到")
                    except Exception as e:
                        sinopac_error = str(e)
                        logger.error(f"下載永豐期貨 {date_str} 報告失敗: {str(e)}", exc_info=True)
                
                # 更新爬取統計
                if date_str not in CRAWL_STATS['failed_dates']:
                    CRAWL_STATS['failed_dates'][date_str] = {}
                
                if fubon_error:
                    CRAWL_STATS['failed_dates'][date_str]['fubon'] = fubon_error
                    logger.warning(f"富邦報告處理失敗: {fubon_error}")
                if sinopac_error:
                    CRAWL_STATS['failed_dates'][date_str]['sinopac'] = sinopac_error
                    logger.warning(f"永豐報告處理失敗: {sinopac_error}")
                
                # 組合報告數據
                if fubon_data or sinopac_data:
                    # 如果有任一報告數據，進行組合
                    from .report_handler import combine_reports_data
                    combined_data = combine_reports_data(fubon_data, sinopac_data)
                    
                    # 更新報告日期
                    formatted_date = date.strftime('%Y/%m/%d')
                    combined_data['date'] = formatted_date
                    
                    # 保存到快取
                    REPORT_CACHE[date_str] = {
                        'fubon': fubon_data,
                        'sinopac': sinopac_data,
                        'combined': combined_data,
                        'last_update': datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S')
                    }
                    
                    success_days += 1
                    logger.info(f"成功處理 {date_str} 的報告數據")
                    
                    # 如果之前有錯誤記錄，現在成功了，移除錯誤記錄
                    if date_str in CRAWL_STATS['failed_dates']:
                        del CRAWL_STATS['failed_dates'][date_str]
                
                processed_days += 1
                
                # 每隔一定數量的日期發送進度更新
                if processed_days % progress_interval == 0:
                    # 保存快取到檔案
                    save_cache()
                    logger.info(f"進度更新: {processed_days}/{total_days} ({processed_days/total_days*100:.1f}%)")
                    
                    line_bot_api.push_message(
                        target_id,
                        TextSendMessage(text=f"歷史數據抓取進度: {processed_days}/{total_days} ({processed_days/total_days*100:.1f}%)")
                    )
                
                # 休息一下，避免請求過於頻繁
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"抓取 {date_str} 的歷史數據時出錯: {str(e)}", exc_info=True)
                processed_days += 1
        
        # 保存最終快取到檔案
        save_cache()
        logger.info(f"歷史數據抓取完成，成功: {success_days}/{total_days}")
        
        # 更新爬取統計
        CRAWL_STATS['in_progress'] = False
        CRAWL_STATS['current_progress'] = total_days
        CRAWL_STATS['success_count'] = success_days
        
        # 發送完成消息
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"歷史數據抓取完成！成功獲取 {success_days}/{total_days} 個交易日的數據。\n\n您可以輸入「盤後籌碼-列表」查看所有可用的報告日期，或輸入「盤後籌碼-狀態」查看詳細的爬取統計。")
        )
    
    except Exception as e:
        logger.error(f"抓取歷史數據時出錯: {str(e)}", exc_info=True)
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"抓取歷史數據時發生錯誤: {str(e)}")
        )
    finally:
        IS_FETCHING_HISTORY = False
        CRAWL_STATS['in_progress'] = False
        logger.info("完成歷史數據抓取任務")

def list_available_reports(line_bot_api, target_id):
    """
    列出所有可用的報告日期
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
    """
    try:
        available_dates = get_available_dates()
        logger.info(f"獲取可用報告日期，共 {len(available_dates)} 個")
        
        if not available_dates:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text="目前系統中沒有任何可用的籌碼報告。\n\n您可以使用「盤後籌碼管理員-開始抓取歷史數據X9527」命令來抓取歷史數據。")
            )
            return
        
        # 按日期排序
        sorted_dates = sorted(available_dates, reverse=True)
        
        # 將日期格式化為更易讀的形式
        formatted_dates = [f"{date[:4]}/{date[4:6]}/{date[6:8]}" for date in sorted_dates]
        
        # 分組顯示，避免訊息過長
        chunks = [formatted_dates[i:i+15] for i in range(0, len(formatted_dates), 15)]
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                header = f"系統中有 {len(formatted_dates)} 個日期的籌碼報告可供查詢：\n\n"
                message = header + "\n".join(chunk)
                if len(chunks) > 1:
                    message += "\n\n(接續...)"
            else:
                message = f"可查詢日期 (續 {i+1}/{len(chunks)})：\n\n" + "\n".join(chunk)
                if i < len(chunks) - 1:
                    message += "\n\n(接續...)"
            
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=message)
            )
            logger.info(f"發送可用報告列表 {i+1}/{len(chunks)}")
        
        # 發送使用指引
        usage_guide = (
            "查詢指令使用說明：\n"
            "1. 「盤後籌碼-YYYYMMDD」：查詢特定日期的報告\n"
            "2. 「盤後籌碼2025」：查詢最新報告\n"
            "3. 「期貨籌碼」、「選擇權籌碼」等：查詢特定類型的報告"
        )
        
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=usage_guide)
        )
    
    except Exception as e:
        logger.error(f"列出可用報告時出錯: {str(e)}", exc_info=True)
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"列出可用報告時出錯，請稍後再試。錯誤詳情: {str(e)}")
        )

def show_crawl_status(line_bot_api, target_id):
    """
    顯示爬取狀態
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID）
    """
    try:
        # 獲取基本統計信息
        last_run = CRAWL_STATS.get('last_run', '尚未執行')
        total_attempts = CRAWL_STATS.get('total_attempts', 0)
        success_count = CRAWL_STATS.get('success_count', 0)
        failed_count = len(CRAWL_STATS.get('failed_dates', {}))
        in_progress = CRAWL_STATS.get('in_progress', False)
        current_progress = CRAWL_STATS.get('current_progress', 0)
        total_tasks = CRAWL_STATS.get('total_tasks', 0)
        
        # 計算成功率
        success_rate = 0
        if total_attempts > 0:
            success_rate = (success_count / total_attempts) * 100
        
        # 生成狀態訊息
        status_message = f"【爬取狀態報告】\n\n"
        
        # 進行中狀態
        if in_progress:
            progress_percent = 0
            if total_tasks > 0:
                progress_percent = (current_progress / total_tasks) * 100
            status_message += f"⏳ 正在進行歷史數據抓取: {current_progress}/{total_tasks} ({progress_percent:.1f}%)\n\n"
        
        # 基本統計
        status_message += f"最後執行時間: {last_run}\n"
        status_message += f"總計嘗試次數: {total_attempts}\n"
        status_message += f"成功次數: {success_count}\n"
        status_message += f"失敗次數: {failed_count}\n"
        status_message += f"成功率: {success_rate:.1f}%\n\n"
        
        # 獲取快取的統計
        cached_dates = len(REPORT_CACHE)
        status_message += f"快取報告數量: {cached_dates}\n"
        
        # 發送基本統計訊息
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=status_message)
        )
        logger.info("發送爬取狀態基本統計")
        
        # 如果有失敗記錄，發送失敗詳情
        failed_dates = CRAWL_STATS.get('failed_dates', {})
        if failed_dates:
            # 按日期排序
            sorted_dates = sorted(failed_dates.keys(), reverse=True)
            
            # 分組顯示，避免訊息過長
            chunks = [sorted_dates[i:i+5] for i in range(0, len(sorted_dates), 5)]
            
            for i, chunk in enumerate(chunks):
                if i == 0:
                    fail_message = f"【失敗記錄】(共 {len(sorted_dates)} 個日期)\n\n"
                else:
                    fail_message = f"【失敗記錄 (續 {i+1}/{len(chunks)})】\n\n"
                
                for date_str in chunk:
                    formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
                    fail_message += f"日期: {formatted_date}\n"
                    
                    if 'fubon' in failed_dates[date_str]:
                        fail_message += f"- 富邦期貨: {failed_dates[date_str]['fubon']}\n"
                    
                    if 'sinopac' in failed_dates[date_str]:
                        fail_message += f"- 永豐期貨: {failed_dates[date_str]['sinopac']}\n"
                    
                    fail_message += "\n"
                
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=fail_message)
                )
                logger.info(f"發送失敗記錄 {i+1}/{len(chunks)}")
        
        # 發送功能指引
        help_message = (
            "狀態管理命令：\n"
            "1. 「盤後籌碼管理員-開始抓取歷史數據X9527」：開始抓取歷史數據\n"
            "2. 「盤後籌碼-列表」：查看所有可用的報告日期\n"
            "3. 「盤後籌碼-狀態」：查看爬取狀態統計"
        )
        
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=help_message)
        )
    
    except Exception as e:
        logger.error(f"顯示爬取狀態時出錯: {str(e)}", exc_info=True)
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"顯示爬取狀態時出錯: {str(e)}")
        )

def get_available_dates():
    """
    獲取所有可用的報告日期
    
    Returns:
        list: 可用的報告日期列表
    """
    available_dates = []
    
    # 從快取中獲取
    for date_str, data in REPORT_CACHE.items():
        if data.get('combined'):
            available_dates.append(date_str)
    
    # 從 pdf_files 目錄中獲取
    if os.path.exists("pdf_files"):
        for filename in os.listdir("pdf_files"):
            if (filename.startswith("fubon_") or filename.startswith("sinopac_")) and filename.endswith(".pdf"):
                date_str = filename.split("_")[1].split(".")[0]  # 從 "type_YYYYMMDD.pdf" 提取日期
                if date_str not in available_dates and len(date_str) == 8 and date_str.isdigit():
                    available_dates.append(date_str)
    
    return available_dates

def get_most_recent_date(dates):
    """
    獲取最近的日期
    
    Args:
        dates: 日期字符串列表 (YYYYMMDD格式)
        
    Returns:
        str: 最近的日期
    """
    if not dates:
        return None
    
    return max(dates)

def send_specialized_report(line_bot_api, target_id, report_type):
    """
    發送專門類型的報告
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
        report_type: 報告類型 (futures, options, institutional, retail, full)
    """
    try:
        # 獲取最新報告數據
        report_data = get_latest_report_data()
        logger.info(f"嘗試獲取專門類型的報告: {report_type}")
        
        if not report_data:
            # 檢查是否有最近的報告
            available_dates = get_available_dates()
            recent_date = get_most_recent_date(available_dates)
            
            if recent_date and recent_date in REPORT_CACHE and REPORT_CACHE[recent_date].get('combined'):
                # 使用最近的報告
                report_data = REPORT_CACHE[recent_date]['combined']
                logger.info(f"使用最近日期 {recent_date} 的報告")
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=f"注意：目前沒有最新報告，以下是 {recent_date[:4]}/{recent_date[4:6]}/{recent_date[6:8]} 的報告：")
                )
            else:
                message = (
                    f"目前尚未有{COMMAND_MAPPING.get(report_type, '籌碼')}報告可供查詢。\n\n"
                    "您可以使用「盤後籌碼-YYYYMMDD」格式查詢特定日期的報告，"
                    "或輸入「盤後籌碼-列表」查看所有可用的報告日期。"
                )
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text=message)
                )
                logger.warning(f"沒有可用的專門報告數據: {report_type}")
                return
        
        # 生成專門報告文字
        report_text = generate_specialized_report(report_data, report_type)
        
        # 發送報告
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=report_text)
        )
        
        logger.info(f"成功發送{report_type}專門報告給目標: {target_id}")
    
    except Exception as e:
        logger.error(f"發送專門報告時出錯: {str(e)}", exc_info=True)
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"發送{report_type}專門報告時出錯，請稍後再試。錯誤詳情: {str(e)}")
            )
        except Exception as push_error:
            logger.error(f"發送錯誤訊息時也失敗: {str(push_error)}", exc_info=True)
