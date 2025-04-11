"""
LINE 訊息處理模組
"""
import os
import logging
from linebot.models import TextSendMessage
from .report_handler import generate_report_text, get_latest_report_data

# 設定日誌
logger = logging.getLogger(__name__)

def handle_line_message(line_bot_api, event, is_secret_command=False):
    """
    處理LINE訊息
    
    Args:
        line_bot_api: LINE Bot API實例
        event: LINE訊息事件
        is_secret_command: 是否為密語指令
    """
    try:
        # 取得用戶ID
        if event.source.type == 'user':
            user_id = event.source.user_id
            target_id = user_id  # 私人訊息回覆
        elif event.source.type == 'group':
            group_id = event.source.group_id
            target_id = group_id  # 群組訊息回覆
        elif event.source.type == 'room':
            room_id = event.source.room_id
            target_id = room_id  # 聊天室訊息回覆
        else:
            logger.warning(f"未知的訊息來源類型: {event.source.type}")
            return
        
        # 處理密語指令 - 發送最新報告
        if is_secret_command:
            send_latest_report(line_bot_api, target_id)
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
