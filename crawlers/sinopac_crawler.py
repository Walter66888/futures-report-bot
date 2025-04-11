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
        
        # 如果找到報告，下載PDF
        if report_links:
            # 下載PDF檔案
            report = report_links[0]  # 取第一個符合條件的報告
            pdf_response = session.get(report['url'], headers=headers, timeout=30)
            pdf_response.raise_for_status()
            
            # 確保目錄存在
            os.makedirs("pdf_files", exist_ok=True)
            
            # 保存PDF檔案
            pdf_filename = f"sinopac_{year}{month}{day}.pdf"
            pdf_path = os.path.join("pdf_files", pdf_filename)
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_response.content)
            
            logger.info(f"成功下載永豐期貨報告: {report['title']}")
            return pdf_path
        else:
            logger.info(f"永豐期貨今日 ({today}) 報告尚未發布")
            return None
    
    except Exception as e:
        logger.error(f"檢查永豐期貨報告時出錯: {str(e)}")
        return None

def extract_sinopac_report_data(pdf_path):
    """
    從永豐期貨PDF檔案提取籌碼數據
    
    Args:
        pdf_path: PDF檔案路徑
        
    Returns:
        dict: 提取的籌碼資料
    """
    try:
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"PDF檔案不存在: {pdf_path}")
            return None
        
        # 讀取PDF
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page].extract_text()
        
        # 初始化結果字典
        result = {
            'date': datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d'),
            'source': '永豐期貨',
            'taiex': {
                'close': 0,
                'change': 0,
                'change_percent': 0,
                'volume': 0
            },
            'institutional': {
                'total': 0,
                'foreign': 0,
                'investment_trust': 0,
                'dealer': 0
            },
            'futures': {
                'foreign_oi': 0,
                'foreign_oi_change': 0,
                'dealer_oi': 0,
                'dealer_oi_change': 0,
                'investment_trust_oi': 0,
                'investment_trust_oi_change': 0,
                'total_oi': 0,
                'total_oi_change': 0
            },
            'options': {
                'foreign_call_oi': 0,
                'foreign_call_oi_change': 0,
                'foreign_put_oi': 0,
                'foreign_put_oi_change': 0,
                'pc_ratio': 0,
                'pc_ratio_prev': 0
            },
            'retail': {
                'mtx_long': 0,
                'mtx_short': 0,
                'ratio': 0,
                'ratio_prev': 0,
                'xmtx_long': 0,
                'xmtx_short': 0,
                'xmtx_ratio': 0,
                'xmtx_ratio_prev': 0
            },
            'vix': 0
        }
        
        # 提取加權指數數據
        taiex_pattern = r"加權指數\s*(\d+\.\d+)\s*\S\s*(\d+\.\d+)\s*\(\s*(\d+\.\d+)%\)"
        taiex_match = re.search(taiex_pattern, text)
        if taiex_match:
            result['taiex']['close'] = float(taiex_match.group(1))
            result['taiex']['change'] = float(taiex_match.group(2))
            result['taiex']['change_percent'] = float(taiex_match.group(3))
        
        # 提取三大法人買賣超
        total_pattern = r"三大法人.*?(\+?-?\d+\.\d+)"
        foreign_pattern = r"外資買賣超.*?(\+?-?\d+\.\d+)"
        trust_pattern = r"投信買賣超.*?(\+?-?\d+\.\d+)"
        dealer_pattern = r"自營買賣超.*?(\+?-?\d+\.\d+)"
        
        total_match = re.search(total_pattern, text)
        foreign_match = re.search(foreign_pattern, text)
        trust_match = re.search(trust_pattern, text)
        dealer_match = re.search(dealer_pattern, text)
        
        if total_match:
            result['institutional']['total'] = float(total_match.group(1).replace('+', ''))
        if foreign_match:
            result['institutional']['foreign'] = float(foreign_match.group(1).replace('+', ''))
        if trust_match:
            result['institutional']['investment_trust'] = float(trust_match.group(1).replace('+', ''))
        if dealer_match:
            result['institutional']['dealer'] = float(dealer_match.group(1).replace('+', ''))
        
        # 提取期貨未平倉
        foreign_oi_pattern = r"外資台指淨未平倉.*?(-?\d+)"
        foreign_oi_change_pattern = r"外資台指淨未平倉增減.*?(-?\d+)"
        
        foreign_oi_match = re.search(foreign_oi_pattern, text)
        foreign_oi_change_match = re.search(foreign_oi_change_pattern, text)
        
        if foreign_oi_match:
            result['futures']['foreign_oi'] = int(foreign_oi_match.group(1))
        if foreign_oi_change_match:
            result['futures']['foreign_oi_change'] = int(foreign_oi_change_match.group(1))
        
        # 提取選擇權資料
        call_oi_pattern = r"外資買權淨未平倉.*?(\d+)"
        call_oi_change_pattern = r"外資買權淨未平倉增減.*?(-?\d+)"
        put_oi_pattern = r"外資賣權淨未平倉.*?(\d+)"
        put_oi_change_pattern = r"外資賣權淨未平倉增減.*?(-?\d+)"
        
        call_oi_match = re.search(call_oi_pattern, text)
        call_oi_change_match = re.search(call_oi_change_pattern, text)
        put_oi_match = re.search(put_oi_pattern, text)
        put_oi_change_match = re.search(put_oi_change_pattern, text)
        
        if call_oi_match:
            result['options']['foreign_call_oi'] = int(call_oi_match.group(1))
        if call_oi_change_match:
            result['options']['foreign_call_oi_change'] = int(call_oi_change_match.group(1))
        if put_oi_match:
            result['options']['foreign_put_oi'] = int(put_oi_match.group(1))
        if put_oi_change_match:
            result['options']['foreign_put_oi_change'] = int(put_oi_change_match.group(1))
        
        # 提取PC Ratio
        pc_ratio_pattern = r"全市場Put/Call Ratio\s+(\d+\.\d+)%.*?(\d+\.\d+)%"
        pc_ratio_match = re.search(pc_ratio_pattern, text)
        if pc_ratio_match:
            result['options']['pc_ratio'] = float(pc_ratio_match.group(1))
            result['options']['pc_ratio_prev'] = float(pc_ratio_match.group(2))
        
        # 提取散戶多空比
        retail_pattern = r"小台散戶多空比\s+(-?\d+\.\d+)%.*?(-?\d+\.\d+)%"
        retail_match = re.search(retail_pattern, text)
        if retail_match:
            result['retail']['ratio'] = float(retail_match.group(1))
            result['retail']['ratio_prev'] = float(retail_match.group(2))
        
        # 提取微台散戶多空比
        xmtx_pattern = r"微台散戶多空比\s+(\+?-?\d+\.\d+)%.*?(\+?-?\d+\.\d+)%"
        xmtx_match = re.search(xmtx_pattern, text)
        if xmtx_match:
            result['retail']['xmtx_ratio'] = float(xmtx_match.group(1).replace('+', ''))
            result['retail']['xmtx_ratio_prev'] = float(xmtx_match.group(2).replace('+', ''))
        
        # 提取VIX指標
        vix_pattern = r"VIX指標\s+(\d+\.\d+)"
        vix_match = re.search(vix_pattern, text)
        if vix_match:
            result['vix'] = float(vix_match.group(1))
        
        return result
    
    except Exception as e:
        logger.error(f"解析永豐期貨報告時出錯: {str(e)}")
        return None

# 測試函數
if __name__ == "__main__":
    result = check_sinopac_futures_report()
    print(f"永豐期貨報告: {result}")
    
    if result:
        data = extract_sinopac_report_data(result)
        print(f"解析結果: {data}")
