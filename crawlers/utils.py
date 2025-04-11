"""
爬蟲共用工具函數
"""
import os
import re
import logging
import random
import time
import requests
from datetime import datetime, timedelta
import pytz
from PIL import Image
import PyPDF2
from pdf2image import convert_from_path
from io import BytesIO

# 設定日誌
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

def get_today_date():
    """
    獲取今日日期（台灣時間）
    
    Returns:
        datetime: 台灣今日日期
    """
    return datetime.now(TW_TIMEZONE)

def is_trading_day(date=None):
    """
    判斷是否為交易日
    
    Args:
        date: 日期，默認為今天
        
    Returns:
        bool: 是否為交易日
    """
    if date is None:
        date = get_today_date()
    
    # 週六日不是交易日
    if date.weekday() >= 5:  # 5=週六, 6=週日
        return False
    
    # TODO: 在此加入假日判斷邏輯
    
    return True

def random_sleep(min_seconds=1, max_seconds=3):
    """
    隨機睡眠一段時間，避免被目標網站發現爬蟲行為
    
    Args:
        min_seconds: 最小睡眠秒數
        max_seconds: 最大睡眠秒數
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    time.sleep(sleep_time)

def get_user_agent():
    """
    隨機獲取一個User-Agent
    
    Returns:
        str: User-Agent字符串
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    ]
    return random.choice(user_agents)

def get_request_headers():
    """
    獲取HTTP請求標頭
    
    Returns:
        dict: HTTP請求標頭
    """
    return {
        'User-Agent': get_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

def download_file(url, save_path=None, headers=None, timeout=30):
    """
    下載檔案
    
    Args:
        url: 檔案URL
        save_path: 保存路徑，若為None則不保存
        headers: HTTP請求標頭
        timeout: 超時時間
        
    Returns:
        bytes: 檔案內容，若下載失敗則返回None
    """
    try:
        if not headers:
            headers = get_request_headers()
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # 若指定保存路徑，則保存檔案
        if save_path:
            # 確保目錄存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
        
        return response.content
    
    except Exception as e:
        logger.error(f"下載檔案時出錯 {url}: {str(e)}")
        return None

def convert_pdf_to_text(pdf_path):
    """
    將PDF檔案轉換為文字
    
    Args:
        pdf_path: PDF檔案路徑
        
    Returns:
        str: 轉換後的文字
    """
    try:
        if not os.path.exists(pdf_path):
            logger.error(f"PDF檔案不存在: {pdf_path}")
            return ""
        
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page].extract_text()
        
        return text
    
    except Exception as e:
        logger.error(f"PDF轉換文字時出錯: {str(e)}")
        return ""

def convert_pdf_to_images(pdf_path, output_folder=None, dpi=200):
    """
    將PDF檔案轉換為圖片
    
    Args:
        pdf_path: PDF檔案路徑
        output_folder: 圖片輸出目錄，若為None則不保存
        dpi: 圖片解析度
        
    Returns:
        list: 圖片物件列表
    """
    try:
        if not os.path.exists(pdf_path):
            logger.error(f"PDF檔案不存在: {pdf_path}")
            return []
        
        # 轉換PDF為圖片
        images = convert_from_path(pdf_path, dpi=dpi)
        
        # 若指定輸出目錄，則保存圖片
        if output_folder:
            # 確保目錄存在
            os.makedirs(output_folder, exist_ok=True)
            
            # 保存圖片
            image_paths = []
            for i, image in enumerate(images):
                image_path = os.path.join(output_folder, f"page_{i+1}.jpg")
                image.save(image_path, "JPEG")
                image_paths.append(image_path)
            
            return image_paths
        
        return images
    
    except Exception as e:
        logger.error(f"PDF轉換圖片時出錯: {str(e)}")
        return []

def clean_text(text):
    """
    清理文字，移除多餘的空白和換行
    
    Args:
        text: 原始文字
        
    Returns:
        str: 清理後的文字
    """
    if not text:
        return ""
    
    # 移除多餘空白
    text = re.sub(r'\s+', ' ', text)
    # 移除開頭和結尾的空白
    text = text.strip()
    
    return text
