"""
永豐期貨盤後籌碼報告爬蟲
"""
import os
import re
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz
import PyPDF2
from io import BytesIO

# 導入數據提取器
from .futures_data_extractor import extract_pdf_data

# 設定日誌
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

def check_sinopac_futures_report():
    """
    檢查永豐期貨是否有最新報告
    
    Returns:
        str: PDF檔案路徑，若未找到則返回None
    """
    try:
        # 取得當前日期
        today = datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')
        year, month, day = today.split('/')
        date_str = f"{year}{month}{day}"
        
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
        
        # 檢查是否已有本地檔案
        pdf_path = os.path.join("pdf_files", f"sinopac_{date_str}.pdf")
        if os.path.exists(pdf_path):
            logger.info(f"永豐期貨報告本地檔案已存在: {pdf_path}")
            return pdf_path
        
        # 發送請求
        logger.info(f"嘗試連接永豐期貨網站: {url}")
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尋找今日的報告連結
        report_links = []
        
        # 尋找包含台指期籌碼快訊的連結
        for li in soup.find_all('li'):
            # 查找a標籤
            a_tags = li.find_all('a')
            for a in a_tags:
                if '台指期籌碼快訊' in a.text:
                    # 查找相鄰的span標籤，可能包含日期
                    span_tags = li.find_all('span')
                    for span in span_tags:
                        if today in span.text:
                            href = a.get('href')
                            if href:
                                full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                                report_links.append({
                                    'title': a.text.strip(),
                                    'url': full_url,
                                    'date': span.text.strip()
                                })
                                logger.info(f"找到永豐期貨報告: {a.text.strip()} - {span.text.strip()}")
        
        # 如果找到報告，下載PDF
        if report_links:
            # 下載PDF檔案
            report = report_links[0]  # 取第一個符合條件的報告
            logger.info(f"正在下載永豐期貨報告: {report['url']}")
            pdf_response = session.get(report['url'], headers=headers, timeout=30)
            pdf_response.raise_for_status()
            
            # 確保目錄存在
            os.makedirs("pdf_files", exist_ok=True)
            
            # 保存PDF檔案
            with open(pdf_path, 'wb') as f:
                f.write(pdf_response.content)
            
            logger.info(f"成功下載永豐期貨報告: {report['title']}")
            return pdf_path
        else:
            logger.info(f"永豐期貨今日 ({today}) 報告尚未發布")
            return None
    
    except Exception as e:
        logger.error(f"檢查永豐期貨報告時出錯: {str(e)}", exc_info=True)
        return None

def extract_sinopac_report_data(pdf_path):
    """
    從永豐期貨PDF檔案提取籌碼數據
    
    Args:
        pdf_path: PDF檔案路徑
        
    Returns:
        dict: 提取的籌碼資料
    """
    # 使用通用的數據提取器處理PDF
    return extract_pdf_data(pdf_path, '永豐期貨')

# 測試函數
if __name__ == "__main__":
    result = check_sinopac_futures_report()
    print(f"永豐期貨報告: {result}")
    
    if result:
        data = extract_sinopac_report_data(result)
        print(f"解析結果: {data}")
