"""
LINE 訊息處理模組
"""
import os
import logging
from linebot.models import TextSendMessage, ImageSendMessage
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

def send_pdf_to_line(line_bot_api, target_id, pdf_path, title):
    """
    將PDF轉為圖片發送至LINE
    
    Args:
        line_bot_api: LINE Bot API實例
        target_id: 目標ID
        pdf_path: PDF檔案路徑
        title: 標題
    """
    try:
        from crawlers.utils import convert_pdf_to_images
        
        # 轉換PDF為圖片
        images = convert_pdf_to_images(pdf_path)
        
        if not images:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"無法處理PDF: {title}")
            )
            return
        
        # 先發送標題
        line_bot_api.push_message(
            target_id,
            TextSendMessage(text=f"【{title}】已更新")
        )
        
        # 發送所有圖片
        for i, image in enumerate(images):
            # 保存臨時圖片
            temp_path = f"temp_img_{i}.jpg"
            image.save(temp_path, "JPEG")
            
            # 上傳圖片並發送
            with open(temp_path, 'rb') as f:
                file_content = f.read()
            
            # 因LINE有檔案大小限制，可能需要調整圖片大小
            # 這裡假設圖片大小合適，實際使用時需要檢查
            
            # 使用push_message發送圖片
            # 注意：這裡需要提供可公開訪問的URL，LINE Bot有免費的方法可以上傳圖片
            # 實際實作時需要替換成真實的URL服務
            line_bot_api.push_message(
                target_id,
                ImageSendMessage(
                    original_content_url="https://example.com/image.jpg",  # 替換為實際URL
                    preview_image_url="https://example.com/image.jpg"  # 替換為實際URL
                )
            )
            
            # 刪除臨時檔案
            os.remove(temp_path)
        
        logger.info(f"成功發送PDF圖片給目標: {target_id}")
    
    except Exception as e:
        logger.error(f"發送PDF圖片時出錯: {str(e)}")
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"發送PDF圖片時出錯: {title}")
            )
        except:
            pass
