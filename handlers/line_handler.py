"""
LINE 訊息處理模組
"""
import os
import re
import logging
from datetime import datetime, timedelta
import pytz
from linebot.models import TextSendMessage
from .report_handler import generate_report_text, get_latest_report_data, generate_specialized_report
from crawlers.fubon_crawler import check_fubon_futures_report, extract_fubon_report_data
from crawlers.sinopac_crawler import check_sinopac_futures_report, extract_sinopac_report_data
from crawlers.utils import is_trading_day

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

# 報告快取，格式為 {'日期': {'fubon': {...}, 'sinopac': {...}, 'combined': {...}}}
REPORT_CACHE = {}

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
        
        # 取得用戶ID
        if event.source.type == 'user':
            user_id = event.source.user_id
            target_id = user_id  # 私人訊息回覆
            is_private = True
        elif event.source.type == 'group':
            group_id = event.source.group_id
            target_id = group_id  # 群組訊息回覆
            is_private = False
        elif event.source.type == 'room':
            room_id = event.source.room_id
            target_id = room_id  # 聊天室訊息回覆
            is_private = False
        else:
            logger.warning(f"未知的訊息來源類型: {event.source.type}")
            return
        
        # 處理密語指令 - 發送最新報告
        if is_secret_command or text == MAIN_SECRET_COMMAND:
            # 主密語 - 發送基本籌碼報告
            send_latest_report(line_bot_api, target_id)
            return
        
        # 檢查是否為歷史日期查詢
        date_match = re.match(DATE_COMMAND_PATTERN, text)
        if date_match:
            date_str = date_match.group(1)  # 格式為 YYYYMMDD
            try:
                # 轉換為日期物件
                year = int(date_str[:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                query_date = datetime(year, month, day, tzinfo=TW_TIMEZONE)
                
                # 檢查是否為有效的交易日
                if not is_trading_day(query_date):
                    line_bot_api.push_message(
                        target_id,
                        TextSendMessage(text=f"{query_date.strftime('%Y/%m/%d')} 不是交易日，無法查詢籌碼資料。")
                    )
                    return
                
                # 發送指定日期的報告
                send_date_report(line_bot_api, target_id, query_date)
                return
            except ValueError:
                line_bot_api.push_message(
                    target_id,
                    TextSendMessage(text="日期格式錯誤，請使用「盤後籌碼-YYYYMMDD」格式查詢，例如：盤後籌碼-20250410")
                )
                return
        
        # 在私人訊息中處理其他密語指令
        if is_private:
            # 檢查是否為專門的密語指令
            for cmd, report_type in COMMAND_MAPPING.items():
                if cmd in text:
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
                send_specialized_report(line_bot_api, target_id, matched_type)
                return
    
    except Exception as e:
        logger.error(f"處理LINE訊息時出錯: {str(e)}")
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text="處理您的訊息時發生錯誤，請稍後再試。")
            )
        except:
            pass

def send_latest_report(line_bot_api, target_id):
    """
    發送最新籌碼報告
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
    """
    try:
        # 獲取今日日期
        today = datetime.now(TW_TIMEZONE).strftime('%Y%m%d')
        
        # 檢查快取中是否有今日報告
        if today in REPORT_CACHE and REPORT_CACHE[today].get('combined'):
            logger.info(f"使用快取的今日報告: {today}")
            report_text = generate_report_text(REPORT_CACHE[today]['combined'])
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=report_text)
            )
            return
        
        # 獲取最新報告數據
        report_data = get_latest_report_data()
        
        if not report_data:
            # 告知用戶尚無最新報告，提供歷史查詢選項
            message = (
                "目前尚未有最新的籌碼報告可供查詢。\n\n"
                "您可以使用「盤後籌碼-YYYYMMDD」格式查詢特定日期的報告，"
                "例如：盤後籌碼-20250410"
            )
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=message)
            )
            return
        
        # 生成報告文字
        report_text = generate_report_text(report_data)
        
        # 發送報告
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=report_text)
        )
        
        logger.info(f"成功發送籌碼報告給目標: {target_id}")
    
    except Exception as e:
        logger.error(f"發送籌碼報告時出錯: {str(e)}")
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text="發送報告時出錯，請稍後再試。")
            )
        except:
            pass

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
        
        # 檢查快取中是否有此日期的報告
        if date_str in REPORT_CACHE and REPORT_CACHE[date_str].get('combined'):
            logger.info(f"使用快取的報告: {date_str}")
            report_text = generate_report_text(REPORT_CACHE[date_str]['combined'])
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=report_text)
            )
            return
        
        # 通知用戶正在獲取報告
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"正在獲取 {formatted_date} 的籌碼報告，請稍候...")
        )
        
        # 構建檔案名稱
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        # 嘗試獲取富邦報告
        fubon_data = None
        fubon_pdf_path = f"pdf_files/fubon_{date_str}.pdf"
        if os.path.exists(fubon_pdf_path):
            # 如果已存在，直接解析
            fubon_data = extract_fubon_report_data(fubon_pdf_path)
        else:
            # 嘗試下載該日期的報告
            pdf_filename = f"TWPM_{year}.{month}.{day}.pdf"
            base_url = "https://www.fubon.com/futures/wcm/home/taiwanaferhours/image/taiwanaferhours/"
            pdf_url = f"{base_url}{pdf_filename}"
            
            import requests
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(pdf_url, headers=headers, timeout=30)
                
                if response.status_code == 200 and response.headers.get('Content-Type', '').lower().startswith('application/pdf'):
                    # 確保目錄存在
                    os.makedirs("pdf_files", exist_ok=True)
                    
                    # 保存 PDF
                    with open(fubon_pdf_path, 'wb') as f:
                        f.write(response.content)
                    
                    # 解析數據
                    fubon_data = extract_fubon_report_data(fubon_pdf_path)
            except:
                logger.error(f"下載富邦期貨 {date_str} 報告失敗")
        
        # 嘗試獲取永豐報告
        sinopac_data = None
        sinopac_pdf_path = f"pdf_files/sinopac_{date_str}.pdf"
        if os.path.exists(sinopac_pdf_path):
            # 如果已存在，直接解析
            sinopac_data = extract_sinopac_report_data(sinopac_pdf_path)
        else:
            # 永豐的歷史報告需要從網頁爬取，比較複雜，這裡略過實現
            # 如果需要完整實現，可以修改 check_sinopac_futures_report 函數，使其支持指定日期
            pass
        
        # 組合報告數據
        if fubon_data or sinopac_data:
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
            
            # 生成報告文字
            report_text = generate_report_text(combined_data)
            
            # 發送報告
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=report_text)
            )
            
            logger.info(f"成功發送 {date_str} 的籌碼報告給目標: {target_id}")
        else:
            # 如果沒有找到任何報告
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"抱歉，無法獲取 {formatted_date} 的籌碼報告。該日可能不是交易日，或報告尚未發布。")
            )
    
    except Exception as e:
        logger.error(f"發送歷史籌碼報告時出錯: {str(e)}")
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"獲取 {query_date.strftime('%Y/%m/%d')} 的報告時出錯，請稍後再試或嘗試其他日期。")
            )
        except:
            pass

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
        
        if not report_data:
            message = (
                f"目前尚未有最新的{COMMAND_MAPPING.get(report_type, '籌碼')}報告可供查詢。\n\n"
                "您可以使用「盤後籌碼-YYYYMMDD」格式查詢特定日期的報告，"
                "例如：盤後籌碼-20250410"
            )
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=message)
            )
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
        logger.error(f"發送專門報告時出錯: {str(e)}")
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"發送{report_type}專門報告時出錯，請稍後再試。")
            )
        except:
            pass
