"""
LINE 訊息處理模組
"""
import os
import re
import logging
from linebot.models import TextSendMessage
from .report_handler import generate_report_text, get_latest_report_data, generate_specialized_report

# 設定日誌
logger = logging.getLogger(__name__)

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
        if is_secret_command:
            # 主密語 - 發送基本籌碼報告
            send_latest_report(line_bot_api, target_id)
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

def send_latest_report(line_bot_api, target_id):
    """
    發送最新籌碼報告
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID（用戶ID或群組ID）
    """
    try:
        # 獲取最新報告數據
        report_data = get_latest_report_data()
        
        if not report_data:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text="目前尚未有最新的籌碼報告可供查詢，請稍後再試。")
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
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text="目前尚未有最新的籌碼報告可供查詢，請稍後再試。")
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
