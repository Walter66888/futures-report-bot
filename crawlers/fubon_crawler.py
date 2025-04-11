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
            'source': '富邦期貨',
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
        taiex_pattern = r"加權指數\s+(\d+\.\d+)\s+[▲▼]\s*(\d+\.\d+)\s*\(\s*(\d+\.\d+)%\)"
        taiex_match = re.search(taiex_pattern, text)
        if taiex_match:
            result['taiex']['close'] = float(taiex_match.group(1))
            result['taiex']['change'] = float(taiex_match.group(2))
            result['taiex']['change_percent'] = float(taiex_match.group(3))
        
        # 提取三大法人買賣超
        inst_pattern = r"三大法人買賣超\s*\(億\)\s+\+?(-?\d+\.\d+)\s+外資買賣超\s*\(億\)\s+\+?(-?\d+\.\d+)\s+投信買賣超\s*\(億\)\s+\+?(-?\d+\.\d+)\s+自營買賣超\s*\(億\)\s+\+?(-?\d+\.\d+)"
        inst_match = re.search(inst_pattern, text)
        if inst_match:
            result['institutional']['total'] = float(inst_match.group(1))
            result['institutional']['foreign'] = float(inst_match.group(2))
            result['institutional']['investment_trust'] = float(inst_match.group(3))
            result['institutional']['dealer'] = float(inst_match.group(4))
        
        # 提取期貨未平倉
        futures_pattern = r"外資台指淨未平倉\s*\(口\)\s+(-?\d+)\s+外資台指淨未平倉增減\s*\(口\)\s+(-?\d+)"
        futures_match = re.search(futures_pattern, text)
        if futures_match:
            result['futures']['foreign_oi'] = int(futures_match.group(1))
            result['futures']['foreign_oi_change'] = int(futures_match.group(2))
        
        # 提取選擇權資料
        options_pattern = r"外資買權淨未平倉\s*\(口\)\s+(\d+)\s+外資買權淨未平倉增減\s*\(口\)\s+(-?\d+)\s+外資賣權淨未平倉\s*\(口\)\s+(\d+)\s+外資賣權淨未平倉增減\s*\(口\)\s+(-?\d+)"
        options_match = re.search(options_pattern, text)
        if options_match:
            result['options']['foreign_call_oi'] = int(options_match.group(1))
            result['options']['foreign_call_oi_change'] = int(options_match.group(2))
            result['options']['foreign_put_oi'] = int(options_match.group(3))
            result['options']['foreign_put_oi_change'] = int(options_match.group(4))
        
        # 提取PC Ratio
        pc_ratio_pattern = r"全市場Put/Call Ratio\s+(\d+\.\d+)%\s+[\u2191\u2193]\s+(\d+\.\d+)%"
        pc_ratio_match = re.search(pc_ratio_pattern, text)
        if pc_ratio_match:
            result['options']['pc_ratio'] = float(pc_ratio_match.group(1))
            result['options']['pc_ratio_prev'] = float(pc_ratio_match.group(2))
        
        # 提取散戶多空比
        retail_pattern = r"小台散戶多空比\s+(-?\d+\.\d+)%\s+[\u2191\u2193]\s+(-?\d+\.\d+)%"
        retail_match = re.search(retail_pattern, text)
        if retail_match:
            result['retail']['ratio'] = float(retail_match.group(1))
            result['retail']['ratio_prev'] = float(retail_match.group(2))
        
        # 提取微台散戶多空比
        xmtx_pattern = r"微台散戶多空比\s+(-?\d+\.\d+)%\s+[\u2191\u2193]\s+(-?\d+\.\d+)%"
        xmtx_match = re.search(xmtx_pattern, text)
        if xmtx_match:
            result['retail']['xmtx_ratio'] = float(xmtx_match.group(1))
            result['retail']['xmtx_ratio_prev'] = float(xmtx_match.group(2))
        
        # 提取VIX指標
        vix_pattern = r"VIX指標\s+(\d+\.\d+)"
        vix_match = re.search(vix_pattern, text)
        if vix_match:
            result['vix'] = float(vix_match.group(1))
        
        return result
    
    except Exception as e:
        logger.error(f"解析富邦期貨報告時出錯: {str(e)}")
        return None

# 測試函數
if __name__ == "__main__":
    result = check_fubon_futures_report()
    print(f"富邦期貨報告: {result}")
    
    if result:
        data = extract_fubon_report_data(result)
        print(f"解析結果: {data}")
