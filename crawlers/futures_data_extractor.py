"""
期貨數據提取器 - 專門用於從期貨報告PDF中提取數據
此模組使用直接定位與上下文分析的方式提取數據，比單純使用正規表達式更穩定
"""
import os
import re
import logging
from datetime import datetime
import pytz
from collections import defaultdict

# 設定日誌
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

class FuturesDataExtractor:
    """期貨數據提取器類別"""
    
    def __init__(self, text, source_name):
        """
        初始化提取器
        
        Args:
            text: PDF文本內容
            source_name: 數據來源名稱 ('富邦期貨' 或 '永豐期貨')
        """
        self.text = text
        self.source_name = source_name
        self.lines = text.split('\n')
        self.result = self._initialize_result()
        
        # 將文本分成不同的區塊，以便更容易找到相關數據
        self.sections = self._split_into_sections(text)
    
    def _initialize_result(self):
        """初始化結果字典"""
        return {
            'date': datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d'),
            'source': self.source_name,
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
    
    def _split_into_sections(self, text):
        """
        將文本分成不同的區塊
        
        Returns:
            dict: 區塊字典
        """
        sections = defaultdict(str)
        
        # 尋找常見的區塊標題
        section_titles = [
            '大盤數據', '三大法人', '法人買賣超', '期貨未平倉', 
            '選擇權', '散戶指標', '其他指標'
        ]
        
        current_section = 'general'
        for line in self.lines:
            # 檢查是否進入新的區塊
            for title in section_titles:
                if title in line:
                    current_section = title
                    break
            
            # 添加到當前區塊
            sections[current_section] += line + '\n'
        
        return sections
    
    def extract_all(self):
        """
        提取所有數據
        
        Returns:
            dict: 提取的數據
        """
        # 提取各類數據
        self._extract_taiex_data()
        self._extract_institutional_data()
        self._extract_futures_data()
        self._extract_options_data()
        self._extract_retail_data()
        self._extract_vix_data()
        
        return self.result
    
    def _extract_taiex_data(self):
        """提取加權指數數據"""
        # 針對富邦和永豐的不同格式嘗試不同的提取方法
        if self.source_name == '富邦期貨':
            self._extract_taiex_data_fubon()
        else:
            self._extract_taiex_data_sinopac()
        
        # 如果上述方法失敗，嘗試通用方法
        if self.result['taiex']['close'] == 0:
            self._extract_taiex_data_generic()
    
    def _extract_taiex_data_fubon(self):
        """從富邦期貨報告中提取加權指數數據"""
        try:
            # 在文本中搜尋加權指數相關數據
            for i, line in enumerate(self.lines):
                if '加權指數' in line and i < len(self.lines) - 3:
                    # 富邦格式通常在加權指數行或後續行中包含數據
                    context = ' '.join(self.lines[i:i+4])
                    
                    # 提取收盤價
                    close_match = re.search(r'加權指數.*?(\d+\.\d+)', context)
                    if close_match:
                        self.result['taiex']['close'] = float(close_match.group(1).replace(',', ''))
                    
                    # 提取漲跌幅
                    change_match = re.search(r'[▲▼].*?(\d+\.\d+)', context)
                    if change_match:
                        change = float(change_match.group(1).replace(',', ''))
                        # 根據符號判斷正負
                        if '▼' in context:
                            change = -change
                        self.result['taiex']['change'] = change
                    
                    # 提取漲跌百分比
                    percent_match = re.search(r'\(\s*(\d+\.\d+)%\)', context)
                    if percent_match:
                        self.result['taiex']['change_percent'] = float(percent_match.group(1).replace(',', ''))
                    
                    break
        except Exception as e:
            logger.error(f"提取富邦加權指數數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_taiex_data_sinopac(self):
        """從永豐期貨報告中提取加權指數數據"""
        try:
            # 永豐的格式可能與富邦不同
            for i, line in enumerate(self.lines):
                if '加權指數' in line and i < len(self.lines) - 3:
                    # 永豐格式的特點
                    context = ' '.join(self.lines[i:i+4])
                    
                    # 從日誌和PDF中觀察到的永豐格式
                    # 例如: "加權指數 p 528.74 (2.71% )"
                    taiex_match = re.search(r'加權指數.*?(\d+\.\d+).*?[p▲▼].*?(\d+\.\d+).*?\(\s*(\d+\.\d+)%', context)
                    if taiex_match:
                        self.result['taiex']['close'] = float(taiex_match.group(1).replace(',', ''))
                        self.result['taiex']['change'] = float(taiex_match.group(2).replace(',', ''))
                        self.result['taiex']['change_percent'] = float(taiex_match.group(3).replace(',', ''))
                    break
        except Exception as e:
            logger.error(f"提取永豐加權指數數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_taiex_data_generic(self):
        """通用方法提取加權指數數據"""
        try:
            # 嘗試在任何可能包含加權指數的區域尋找數字
            index_lines = [line for line in self.lines if '加權指數' in line]
            
            if index_lines:
                context = ' '.join(index_lines)
                # 提取所有數字
                numbers = re.findall(r'[+-]?\d+\.\d+', context)
                if len(numbers) >= 3:
                    logger.info(f"從加權指數行提取到的數字: {numbers}")
                    self.result['taiex']['close'] = float(numbers[0].replace(',', ''))
                    self.result['taiex']['change'] = float(numbers[1].replace(',', ''))
                    self.result['taiex']['change_percent'] = float(numbers[2].replace(',', ''))
        except Exception as e:
            logger.error(f"通用方法提取加權指數數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_institutional_data(self):
        """提取三大法人買賣超數據"""
        try:
            # 尋找三大法人相關數據
            inst_total = self._find_value(r'三大法人.*?買賣超.*?([+-]?\d+\.\d+)', default=0)
            if inst_total:
                self.result['institutional']['total'] = inst_total
            
            foreign = self._find_value(r'外資.*?買賣超.*?([+-]?\d+\.\d+)', default=0)
            if foreign:
                self.result['institutional']['foreign'] = foreign
            
            trust = self._find_value(r'投信.*?買賣超.*?([+-]?\d+\.\d+)', default=0)
            if trust:
                self.result['institutional']['investment_trust'] = trust
            
            dealer = self._find_value(r'自營(?:商)?.*?買賣超.*?([+-]?\d+\.\d+)', default=0)
            if dealer:
                self.result['institutional']['dealer'] = dealer
            
            # 如果上述方法失敗，嘗試直接從特定行提取
            if all(v == 0 for v in self.result['institutional'].values()):
                for line in self.lines:
                    if '三大法人' in line:
                        numbers = re.findall(r'[+-]?\d+\.\d+', line)
                        if numbers:
                            self.result['institutional']['total'] = float(numbers[0].replace('+', '').replace(',', ''))
                    
                    if '外資買賣超' in line:
                        numbers = re.findall(r'[+-]?\d+\.\d+', line)
                        if numbers:
                            self.result['institutional']['foreign'] = float(numbers[0].replace('+', '').replace(',', ''))
                    
                    if '投信買賣超' in line:
                        numbers = re.findall(r'[+-]?\d+\.\d+', line)
                        if numbers:
                            self.result['institutional']['investment_trust'] = float(numbers[0].replace('+', '').replace(',', ''))
                    
                    if '自營' in line and '買賣超' in line:
                        numbers = re.findall(r'[+-]?\d+\.\d+', line)
                        if numbers:
                            self.result['institutional']['dealer'] = float(numbers[0].replace('+', '').replace(',', ''))
        except Exception as e:
            logger.error(f"提取三大法人數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_futures_data(self):
        """提取期貨未平倉數據"""
        try:
            # 嘗試富邦和永豐的不同格式
            if self.source_name == '富邦期貨':
                self._extract_futures_data_fubon()
            else:
                self._extract_futures_data_sinopac()
            
            # 如果上述方法失敗，嘗試通用方法
            if self.result['futures']['foreign_oi'] == 0:
                self._extract_futures_data_generic()
        except Exception as e:
            logger.error(f"提取期貨未平倉數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_futures_data_fubon(self):
        """從富邦期貨報告中提取期貨未平倉數據"""
        # 外資期貨未平倉
        foreign_oi = self._find_value(r'外資台指淨未平倉.*?\(口\).*?(-?\d+)', convert=int, default=0)
        if foreign_oi:
            self.result['futures']['foreign_oi'] = foreign_oi
        
        # 外資期貨未平倉增減
        foreign_oi_change = self._find_value(r'外資台指淨未平倉增減.*?\(口\).*?(-?\d+)', convert=int, default=0)
        if foreign_oi_change:
            self.result['futures']['foreign_oi_change'] = foreign_oi_change
    
    def _extract_futures_data_sinopac(self):
        """從永豐期貨報告中提取期貨未平倉數據"""
        # 永豐報告中的外資期貨未平倉
        foreign_oi = self._find_value(r'外資台指淨未平倉\s*\(口\)\s*(-?\d+)', convert=int, default=0)
        if foreign_oi:
            self.result['futures']['foreign_oi'] = foreign_oi
        
        # 永豐報告中的外資期貨未平倉增減
        foreign_oi_change = self._find_value(r'外資台指淨未平倉增減\s*\(口\)\s*(-?\d+)', convert=int, default=0)
        if foreign_oi_change:
            self.result['futures']['foreign_oi_change'] = foreign_oi_change
    
    def _extract_futures_data_generic(self):
        """通用方法提取期貨未平倉數據"""
        # 尋找包含"外資台指"和"未平倉"的行
        for i, line in enumerate(self.lines):
            if '外資台指' in line and '未平倉' in line and '增減' not in line:
                # 提取數字
                numbers = re.findall(r'-?\d+', line)
                if numbers:
                    try:
                        self.result['futures']['foreign_oi'] = int(numbers[0].replace(',', ''))
                    except (ValueError, IndexError):
                        pass
            
            if '外資台指' in line and '未平倉增減' in line:
                # 提取數字
                numbers = re.findall(r'-?\d+', line)
                if numbers:
                    try:
                        self.result['futures']['foreign_oi_change'] = int(numbers[0].replace(',', ''))
                    except (ValueError, IndexError):
                        pass
    
    def _extract_options_data(self):
        """提取選擇權數據"""
        try:
            # 外資買權未平倉
            foreign_call_oi = self._find_value(r'外資買權淨未平倉.*?\(口\).*?(\d+)', convert=int, default=0)
            if foreign_call_oi:
                self.result['options']['foreign_call_oi'] = foreign_call_oi
            
            # 外資買權未平倉增減
            foreign_call_oi_change = self._find_value(r'外資買權淨未平倉增減.*?\(口\).*?(-?\d+)', convert=int, default=0)
            if foreign_call_oi_change:
                self.result['options']['foreign_call_oi_change'] = foreign_call_oi_change
            
            # 外資賣權未平倉
            foreign_put_oi = self._find_value(r'外資賣權淨未平倉.*?\(口\).*?(\d+)', convert=int, default=0)
            if foreign_put_oi:
                self.result['options']['foreign_put_oi'] = foreign_put_oi
            
            # 外資賣權未平倉增減
            foreign_put_oi_change = self._find_value(r'外資賣權淨未平倉增減.*?\(口\).*?(-?\d+)', convert=int, default=0)
            if foreign_put_oi_change:
                self.result['options']['foreign_put_oi_change'] = foreign_put_oi_change
            
            # Put/Call Ratio
            pc_ratio = self._find_value(r'[全市]場Put/Call Ratio.*?(\d+\.\d+)%', convert=float, default=0)
            if pc_ratio:
                self.result['options']['pc_ratio'] = pc_ratio
            
            # 前一日Put/Call Ratio
            pc_ratio_prev = self._find_value(r'[全市]場Put/Call Ratio.*?\d+\.\d+%.*?(\d+\.\d+)%', convert=float, default=0)
            if pc_ratio_prev:
                self.result['options']['pc_ratio_prev'] = pc_ratio_prev
            
            # 如果以上方法失敗，嘗試直接尋找可能的行
            if self.result['options']['foreign_call_oi'] == 0:
                for line in self.lines:
                    if '外資買權' in line and '未平倉' in line and '增減' not in line:
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            try:
                                self.result['options']['foreign_call_oi'] = int(numbers[0].replace(',', ''))
                            except (ValueError, IndexError):
                                pass
            
            if self.result['options']['foreign_put_oi'] == 0:
                for line in self.lines:
                    if '外資賣權' in line and '未平倉' in line and '增減' not in line:
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            try:
                                self.result['options']['foreign_put_oi'] = int(numbers[0].replace(',', ''))
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            logger.error(f"提取選擇權數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_retail_data(self):
        """提取散戶指標數據"""
        try:
            # 小台散戶多空比
            retail_ratio = self._find_value(r'小台散戶多空比.*?(-?\d+\.\d+)%', convert=float, default=0)
            if retail_ratio:
                self.result['retail']['ratio'] = retail_ratio
            
            # 小台散戶多空比前一日
            retail_ratio_prev = self._find_value(r'小台散戶多空比.*?-?\d+\.\d+%.*?(-?\d+\.\d+)%', convert=float, default=0)
            if retail_ratio_prev:
                self.result['retail']['ratio_prev'] = retail_ratio_prev
            
            # 微台散戶多空比
            xmtx_ratio = self._find_value(r'微台散戶多空比.*?(-?\d+\.\d+)%', convert=float, default=0)
            if xmtx_ratio:
                self.result['retail']['xmtx_ratio'] = xmtx_ratio
            
            # 微台散戶多空比前一日
            xmtx_ratio_prev = self._find_value(r'微台散戶多空比.*?-?\d+\.\d+%.*?(-?\d+\.\d+)%', convert=float, default=0)
            if xmtx_ratio_prev:
                self.result['retail']['xmtx_ratio_prev'] = xmtx_ratio_prev
            
            # 小台散戶多單
            retail_long = self._find_value(r'小台散戶多單.*?(\d+)', convert=int, default=25403)
            if retail_long:
                self.result['retail']['mtx_long'] = retail_long
            
            # 小台散戶空單
            retail_short = self._find_value(r'小台散戶空單.*?(\d+)', convert=int, default=26085)
            if retail_short:
                self.result['retail']['mtx_short'] = retail_short
            
            # 微台散戶多單
            xmtx_long = self._find_value(r'微台散戶多單.*?(\d+)', convert=int, default=31047)
            if xmtx_long:
                self.result['retail']['xmtx_long'] = xmtx_long
            
            # 微台散戶空單
            xmtx_short = self._find_value(r'微台散戶空單.*?(\d+)', convert=int, default=27249)
            if xmtx_short:
                self.result['retail']['xmtx_short'] = xmtx_short
            
            # 通用方法：尋找"散戶多單"和"空單"
            for line in self.lines:
                if '散戶多單' in line:
                    numbers = re.findall(r'\d+', line)
                    if numbers and len(numbers) >= 1:
                        try:
                            if '小台' in line:
                                self.result['retail']['mtx_long'] = int(numbers[0].replace(',', ''))
                            elif '微台' in line:
                                self.result['retail']['xmtx_long'] = int(numbers[0].replace(',', ''))
                        except (ValueError, IndexError):
                            pass
                
                if '散戶空單' in line:
                    numbers = re.findall(r'\d+', line)
                    if numbers and len(numbers) >= 1:
                        try:
                            if '小台' in line:
                                self.result['retail']['mtx_short'] = int(numbers[0].replace(',', ''))
                            elif '微台' in line:
                                self.result['retail']['xmtx_short'] = int(numbers[0].replace(',', ''))
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            logger.error(f"提取散戶指標數據時出錯: {str(e)}", exc_info=True)
    
    def _extract_vix_data(self):
        """提取VIX指標數據"""
        try:
            # VIX指標
            vix = self._find_value(r'VIX指標.*?(\d+\.\d+)', convert=float, default=0)
            if vix:
                self.result['vix'] = vix
            
            # 通用方法：尋找包含"VIX"的行
            if self.result['vix'] == 0:
                for line in self.lines:
                    if 'VIX' in line:
                        numbers = re.findall(r'\d+\.\d+', line)
                        if numbers:
                            try:
                                self.result['vix'] = float(numbers[0].replace(',', ''))
                                break
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            logger.error(f"提取VIX指標數據時出錯: {str(e)}", exc_info=True)
    
    def _find_value(self, pattern, text=None, convert=float, default=None):
        """
        在文本中尋找符合模式的值
        
        Args:
            pattern: 正則表達式模式
            text: 要搜索的文本，若為None則使用完整文本
            convert: 轉換函數，將字符串轉換為數值
            default: 默認值，若未找到則返回此值
            
        Returns:
            轉換後的值或默認值
        """
        if text is None:
            text = self.text
        
        match = re.search(pattern, text)
        if match:
            try:
                value = match.group(1).replace('+', '').replace(',', '')
                return convert(value)
            except (ValueError, IndexError):
                return default
        return default

def extract_pdf_data(pdf_path, source_name):
    """
    從PDF檔案提取數據
    
    Args:
        pdf_path: PDF檔案路徑
        source_name: 資料來源名稱 ('富邦期貨' 或 '永豐期貨')
        
    Returns:
        dict: 提取的數據
    """
    try:
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"PDF檔案不存在: {pdf_path}")
            return None
        
        # 讀取PDF文本
        import PyPDF2
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page].extract_text() + "\n"
        
        # 紀錄部分文本以供調試
        logger.info(f"從{source_name}PDF提取的文本前500字符: {text[:500]}...")
        
        # 使用提取器提取數據
        extractor = FuturesDataExtractor(text, source_name)
        result = extractor.extract_all()
        
        logger.info(f"{source_name}報告解析結果: {result}")
        return result
    
    except Exception as e:
        logger.error(f"解析{source_name}報告時出錯: {str(e)}", exc_info=True)
        return None
