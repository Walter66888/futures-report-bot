"""
富邦期貨盤後籌碼報告爬蟲
"""
import os
import re
import logging
from datetime import datetime
import requests
import pytz
import PyPDF2
from io import BytesIO

# 導入數據提取器
from .futures_data_extractor import extract_pdf_data

# 設定日誌
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

def check_fubon_futures_report():
    """
    檢查富邦期貨是否有最新報告
    
    Returns:
        str: PDF檔案路徑，若未找到則返回None
    """
    try:
        # 取得當前日期
        current_date = datetime.now(TW_TIMEZONE).strftime('%Y.%m.%d')
        year, month, day = current_date.split('.')
        
        # 構建 PDF URL
        pdf_filename = f"TWPM_{year}.{month}.{day}.pdf"
        base_url = "https://www.fubon.com/futures/wcm/home/taiwanaferhours/image/taiwanaferhours/"
        pdf_url = f"{base_url}{pdf_filename}"
        
        # 設定請求標頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 嘗試下載 PDF
        response = requests.get(pdf_url, headers=headers, timeout=30)
        
        # 檢查是否成功
        if response.status_code == 200 and response.headers.get('Content-Type', '').lower().startswith('application/pdf'):
            # 確保目錄存在
            os.makedirs("pdf_files", exist_ok=True)
            
            # 保存 PDF
            pdf_path = os.path.join("pdf_files", f"fubon_{year}{month}{day}.pdf")
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"成功下載富邦期貨報告: {pdf_filename}")
            return pdf_path
        else:
            logger.info(f"富邦期貨今日 ({current_date}) 報告尚未發布")
            return None
    
    except Exception as e:
        logger.error(f"檢查富邦期貨報告時出錯: {str(e)}")
        return None

def extract_fubon_report_data(pdf_path):
    """
    從富邦期貨PDF檔案提取籌碼數據
    
    Args:
        pdf_path: PDF檔案路徑
        
    Returns:
        dict: 提取的籌碼資料
    """
    # 使用通用的數據提取器處理PDF
    return extract_pdf_data(pdf_path, '富邦期貨')

# 測試函數
if __name__ == "__main__":
    result = check_fubon_futures_report()
    print(f"富邦期貨報告: {result}")
    
    if result:
        data = extract_fubon_report_data(result)
        print(f"解析結果: {data}")
