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
        
        # 记录提取的文本（前1000字符）用于调试
        logger.info(f"從永豐PDF提取的文本前1000字符: {text[:1000]}...")
        
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
        
        # 提取加權指數數據 - 尝试多种模式
        taiex_patterns = [
            r"加權指數\s*(\d+\.\d+)\s*\S\s*(\d+\.\d+)\s*\(\s*(\d+\.\d+)%\)",
            r"加權指數[:\s]+(\d+[\.,]\d+)\s*[▲▼]*\s*(\d+[\.,]\d+)\s*\(\s*([+-]?\d+[\.,]\d+)%\)",
            r"加權指數.*?(\d+\.\d+).*?(\d+\.\d+).*?(\d+\.\d+)%"
        ]
        
        for pattern in taiex_patterns:
            taiex_match = re.search(pattern, text)
            if taiex_match:
                logger.info(f"匹配到加權指數模式: {pattern}")
                logger.info(f"加權指數匹配值: {taiex_match.groups()}")
                result['taiex']['close'] = float(taiex_match.group(1).replace(',', ''))
                result['taiex']['change'] = float(taiex_match.group(2).replace(',', ''))
                result['taiex']['change_percent'] = float(taiex_match.group(3).replace(',', ''))
                break
        
        # 提取三大法人買賣超 - 尝试多种模式
        total_patterns = [
            r"三大法人.*?(\+?-?\d+\.\d+)",
            r"三大法人買賣超.*?(\+?-?\d+\.\d+)"
        ]
        
        foreign_patterns = [
            r"外資買賣超.*?(\+?-?\d+\.\d+)",
            r"外資.*?買賣超.*?(\+?-?\d+\.\d+)"
        ]
        
        trust_patterns = [
            r"投信買賣超.*?(\+?-?\d+\.\d+)",
            r"投信.*?買賣超.*?(\+?-?\d+\.\d+)"
        ]
        
        dealer_patterns = [
            r"自營買賣超.*?(\+?-?\d+\.\d+)",
            r"自營(商)?.*?買賣超.*?(\+?-?\d+\.\d+)"
        ]
        
        for pattern in total_patterns:
            total_match = re.search(pattern, text)
            if total_match:
                logger.info(f"匹配到三大法人總計模式: {pattern}")
                logger.info(f"三大法人總計匹配值: {total_match.groups()}")
                result['institutional']['total'] = float(total_match.group(1).replace('+', '').replace(',', ''))
                break
        
        for pattern in foreign_patterns:
            foreign_match = re.search(pattern, text)
            if foreign_match:
                logger.info(f"匹配到外資模式: {pattern}")
                logger.info(f"外資匹配值: {foreign_match.groups()}")
                result['institutional']['foreign'] = float(foreign_match.group(1).replace('+', '').replace(',', ''))
                break
        
        for pattern in trust_patterns:
            trust_match = re.search(pattern, text)
            if trust_match:
                logger.info(f"匹配到投信模式: {pattern}")
                logger.info(f"投信匹配值: {trust_match.groups()}")
                result['institutional']['investment_trust'] = float(trust_match.group(1).replace('+', '').replace(',', ''))
                break
        
        for pattern in dealer_patterns:
            dealer_match = re.search(pattern, text)
            if dealer_match:
                logger.info(f"匹配到自營商模式: {pattern}")
                val_index = 1 if len(dealer_match.groups()) == 1 else 2
                logger.info(f"自營商匹配值: {dealer_match.groups()}")
                result['institutional']['dealer'] = float(dealer_match.group(val_index).replace('+', '').replace(',', ''))
                break
        
        # 提取期貨未平倉 - 尝试多种模式
        foreign_oi_patterns = [
            r"外資台指淨未平倉.*?(-?\d+)",
            r"外資.*?未平倉.*?(-?\d+)"
        ]
        
        foreign_oi_change_patterns = [
            r"外資台指淨未平倉增減.*?(-?\d+)",
            r"外資.*?未平倉增減.*?(-?\d+)"
        ]
        
        for pattern in foreign_oi_patterns:
            foreign_oi_match = re.search(pattern, text)
            if foreign_oi_match:
                logger.info(f"匹配到外資期貨未平倉模式: {pattern}")
                logger.info(f"外資期貨未平倉匹配值: {foreign_oi_match.groups()}")
                result['futures']['foreign_oi'] = int(foreign_oi_match.group(1).replace(',', ''))
                break
        
        for pattern in foreign_oi_change_patterns:
            foreign_oi_change_match = re.search(pattern, text)
            if foreign_oi_change_match:
                logger.info(f"匹配到外資期貨未平倉增減模式: {pattern}")
                logger.info(f"外資期貨未平倉增減匹配值: {foreign_oi_change_match.groups()}")
                result['futures']['foreign_oi_change'] = int(foreign_oi_change_match.group(1).replace(',', ''))
                break
        
        # 提取選擇權資料 - 尝试多种模式
        call_oi_patterns = [
            r"外資買權淨未平倉.*?(\d+)",
            r"外資買權.*?未平倉.*?(\d+)"
        ]
        
        call_oi_change_patterns = [
            r"外資買權淨未平倉增減.*?(-?\d+)",
            r"外資買權.*?未平倉增減.*?(-?\d+)"
        ]
        
        put_oi_patterns = [
            r"外資賣權淨未平倉.*?(\d+)",
            r"外資賣權.*?未平倉.*?(\d+)"
        ]
        
        put_oi_change_patterns = [
            r"外資賣權淨未平倉增減.*?(-?\d+)",
            r"外資賣權.*?未平倉增減.*?(-?\d+)"
        ]
        
        for pattern in call_oi_patterns:
            call_oi_match = re.search(pattern, text)
            if call_oi_match:
                logger.info(f"匹配到外資買權未平倉模式: {pattern}")
                logger.info(f"外資買權未平倉匹配值: {call_oi_match.groups()}")
                result['options']['foreign_call_oi'] = int(call_oi_match.group(1).replace(',', ''))
                break
        
        for pattern in call_oi_change_patterns:
            call_oi_change_match = re.search(pattern, text)
            if call_oi_change_match:
                logger.info(f"匹配到外資買權未平倉增減模式: {pattern}")
                logger.info(f"外資買權未平倉增減匹配值: {call_oi_change_match.groups()}")
                result['options']['foreign_call_oi_change'] = int(call_oi_change_match.group(1).replace(',', ''))
                break
        
        for pattern in put_oi_patterns:
            put_oi_match = re.search(pattern, text)
            if put_oi_match:
                logger.info(f"匹配到外資賣權未平倉模式: {pattern}")
                logger.info(f"外資賣權未平倉匹配值: {put_oi_match.groups()}")
                result['options']['foreign_put_oi'] = int(put_oi_match.group(1).replace(',', ''))
                break
        
        for pattern in put_oi_change_patterns:
            put_oi_change_match = re.search(pattern, text)
            if put_oi_change_match:
                logger.info(f"匹配到外資賣權未平倉增減模式: {pattern}")
                logger.info(f"外資賣權未平倉增減匹配值: {put_oi_change_match.groups()}")
                result['options']['foreign_put_oi_change'] = int(put_oi_change_match.group(1).replace(',', ''))
                break
        
        # 提取PC Ratio - 尝试多种模式
        pc_ratio_patterns = [
            r"全市場Put/Call Ratio\s+(\d+\.\d+)%.*?(\d+\.\d+)%",
            r"全市場Put/Call Ratio.*?(\d+\.\d+)%.*?(\d+\.\d+)%",
            r"Put/Call Ratio.*?(\d+\.\d+)%.*?(\d+\.\d+)%"
        ]
        
        for pattern in pc_ratio_patterns:
            pc_ratio_match = re.search(pattern, text)
            if pc_ratio_match:
                logger.info(f"匹配到PC Ratio模式: {pattern}")
                logger.info(f"PC Ratio匹配值: {pc_ratio_match.groups()}")
                result['options']['pc_ratio'] = float(pc_ratio_match.group(1).replace(',', ''))
                result['options']['pc_ratio_prev'] = float(pc_ratio_match.group(2).replace(',', ''))
                break
        
        # 提取散戶多空比 - 尝试多种模式
        retail_patterns = [
            r"小台散戶多空比\s+(-?\d+\.\d+)%.*?(-?\d+\.\d+)%",
            r"小台散戶多空比.*?(\+?-?\d+\.\d+)%.*?(\+?-?\d+\.\d+)%",
            r"小台散戶.*?(\+?-?\d+\.\d+)%.*?(\+?-?\d+\.\d+)%"
        ]
        
        for pattern in retail_patterns:
            retail_match = re.search(pattern, text)
            if retail_match:
                logger.info(f"匹配到散戶多空比模式: {pattern}")
                logger.info(f"散戶多空比匹配值: {retail_match.groups()}")
                result['retail']['ratio'] = float(retail_match.group(1).replace('+', '').replace(',', ''))
                result['retail']['ratio_prev'] = float(retail_match.group(2).replace('+', '').replace(',', ''))
                break
        
        # 提取微台散戶多空比 - 尝试多种模式
        xmtx_patterns = [
            r"微台散戶多空比\s+(\+?-?\d+\.\d+)%.*?(\+?-?\d+\.\d+)%",
            r"微台散戶多空比.*?(\+?-?\d+\.\d+)%.*?(\+?-?\d+\.\d+)%",
            r"微台散戶.*?(\+?-?\d+\.\d+)%.*?(\+?-?\d+\.\d+)%"
        ]
        
        for pattern in xmtx_patterns:
            xmtx_match = re.search(pattern, text)
            if xmtx_match:
                logger.info(f"匹配到微台散戶多空比模式: {pattern}")
                logger.info(f"微台散戶多空比匹配值: {xmtx_match.groups()}")
                result['retail']['xmtx_ratio'] = float(xmtx_match.group(1).replace('+', '').replace(',', ''))
                result['retail']['xmtx_ratio_prev'] = float(xmtx_match.group(2).replace('+', '').replace(',', ''))
                break
        
        # 提取VIX指標 - 尝试多种模式
        vix_patterns = [
            r"VIX指標\s+(\d+\.\d+)",
            r"VIX指標.*?(\d+\.\d+)",
            r"VIX.*?(\d+\.\d+)"
        ]
        
        for pattern in vix_patterns:
            vix_match = re.search(pattern, text)
            if vix_match:
                logger.info(f"匹配到VIX指標模式: {pattern}")
                logger.info(f"VIX指標匹配值: {vix_match.groups()}")
                result['vix'] = float(vix_match.group(1).replace(',', ''))
                break
        
        # 尝试提取小台和微台的多空数量
        retail_qty_patterns = [
            r"小台散戶多單.*?(\d+).*?小台散戶空單.*?(\d+)",
            r"小台.*?多單.*?(\d+).*?空單.*?(\d+)"
        ]
        
        for pattern in retail_qty_patterns:
            retail_qty_match = re.search(pattern, text)
            if retail_qty_match:
                logger.info(f"匹配到小台多空數量模式: {pattern}")
                logger.info(f"小台多空數量匹配值: {retail_qty_match.groups()}")
                result['retail']['mtx_long'] = int(retail_qty_match.group(1).replace(',', ''))
                result['retail']['mtx_short'] = int(retail_qty_match.group(2).replace(',', ''))
                break
        
        xmtx_qty_patterns = [
            r"微台散戶多單.*?(\d+).*?微台散戶空單.*?(\d+)",
            r"微台.*?多單.*?(\d+).*?空單.*?(\d+)"
        ]
        
        for pattern in xmtx_qty_patterns:
            xmtx_qty_match = re.search(pattern, text)
            if xmtx_qty_match:
                logger.info(f"匹配到微台多空數量模式: {pattern}")
                logger.info(f"微台多空數量匹配值: {xmtx_qty_match.groups()}")
                result['retail']['xmtx_long'] = int(xmtx_qty_match.group(1).replace(',', ''))
                result['retail']['xmtx_short'] = int(xmtx_qty_match.group(2).replace(',', ''))
                break
        
        # 检查是否成功提取关键数据
        if (result['taiex']['close'] == 0 and result['futures']['foreign_oi'] == 0 and 
            result['options']['foreign_call_oi'] == 0):
            logger.warning("未能成功提取关键数据，可能模式匹配失败")
            logger.warning("尝试使用替代方法解析PDF")
            
            # 尝试查找可能包含数据的行
            lines = text.split('\n')
            for line in lines:
                # 查找加权指数行
                if '加權指數' in line:
                    logger.info(f"加權指數行: {line}")
                    # 尝试提取数字
                    numbers = re.findall(r'[+-]?\d+\.\d+', line)
                    if len(numbers) >= 3:
                        logger.info(f"從加權指數行提取到的數字: {numbers}")
                        result['taiex']['close'] = float(numbers[0])
                        result['taiex']['change'] = float(numbers[1])
                        result['taiex']['change_percent'] = float(numbers[2])
                
                # 查找三大法人行
                if '三大法人買賣超' in line:
                    logger.info(f"三大法人行: {line}")
                    # 尝试提取数字
                    numbers = re.findall(r'[+-]?\d+\.\d+', line)
                    if len(numbers) >= 1:
                        logger.info(f"從三大法人行提取到的數字: {numbers}")
                        result['institutional']['total'] = float(numbers[0])
        
        logger.info(f"永豐期貨報告解析結果: {result}")
        return result
    
    except Exception as e:
        logger.error(f"解析永豐期貨報告時出錯: {str(e)}", exc_info=True)
        return None

# 測試函數
if __name__ == "__main__":
    result = check_sinopac_futures_report()
    print(f"永豐期貨報告: {result}")
    
    if result:
        data = extract_sinopac_report_data(result)
        print(f"解析結果: {data}")
