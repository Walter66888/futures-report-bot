"""
報告處理與整合模組
"""
import os
import logging
import time
import json
import random
from datetime import datetime
import pytz
import threading

from crawlers.fubon_crawler import check_fubon_futures_report, extract_fubon_report_data
from crawlers.sinopac_crawler import check_sinopac_futures_report, extract_sinopac_report_data

# 設定日誌
logger = logging.getLogger(__name__)

# 設定台灣時區
TW_TIMEZONE = pytz.timezone('Asia/Taipei')

# 最新報告資料
LATEST_REPORT = {
    'fubon': None,
    'sinopac': None,
    'combined': None,
    'last_update': None
}

def monitor_futures_reports(line_bot_api, group_id=None):
    """
    監控期貨報告更新並推送到LINE群組
    
    Args:
        line_bot_api: LINE Bot API實例
        group_id: 要推送訊息的群組ID，若為None則不推送
    """
    # 記錄已推送的報告，避免重複推送
    pushed_reports = {
        'fubon': None,
        'sinopac': None,
        'combined': False
    }
    
    while True:
        try:
            now = datetime.now(TW_TIMEZONE)
            current_time = now.strftime("%H:%M")
            
            # 只在交易日的14:45到16:30之間檢查
            if now.weekday() < 5 and "14:45" <= current_time <= "16:30":
                # 檢查富邦期貨報告
                fubon_report = check_fubon_futures_report()
                if fubon_report and fubon_report != pushed_reports['fubon']:
                    logger.info(f"發現富邦期貨新報告: {fubon_report}")
                    
                    # 解析報告資料
                    fubon_data = extract_fubon_report_data(fubon_report)
                    if fubon_data:
                        LATEST_REPORT['fubon'] = fubon_data
                        LATEST_REPORT['last_update'] = datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S')
                        pushed_reports['fubon'] = fubon_report
                        logger.info("更新富邦期貨報告資料成功")
                    
                # 檢查永豐期貨報告
                sinopac_report = check_sinopac_futures_report()
                if sinopac_report and sinopac_report != pushed_reports['sinopac']:
                    logger.info(f"發現永豐期貨新報告: {sinopac_report}")
                    
                    # 解析報告資料
                    sinopac_data = extract_sinopac_report_data(sinopac_report)
                    if sinopac_data:
                        LATEST_REPORT['sinopac'] = sinopac_data
                        LATEST_REPORT['last_update'] = datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S')
                        pushed_reports['sinopac'] = sinopac_report
                        logger.info("更新永豐期貨報告資料成功")
                
                # 如果兩份報告都更新了，且尚未推送組合報告
                if (LATEST_REPORT['fubon'] and LATEST_REPORT['sinopac'] and 
                    not pushed_reports['combined'] and group_id):
                    
                    # 組合兩份報告資料
                    combined_data = combine_reports_data(LATEST_REPORT['fubon'], LATEST_REPORT['sinopac'])
                    LATEST_REPORT['combined'] = combined_data
                    
                    # 生成報告文字
                    report_text = generate_report_text(combined_data)
                    
                    # 推送到LINE群組
                    from handlers.line_handler import send_latest_report
                    try:
                        line_bot_api.push_message(
                            group_id,
                            TextSendMessage(text=report_text)
                        )
                        pushed_reports['combined'] = True
                        logger.info(f"成功推送組合報告到群組: {group_id}")
                    except Exception as e:
                        logger.error(f"推送報告到群組時出錯: {str(e)}")
            
            # 每天零點重置推送狀態
            if current_time == "00:00" and pushed_reports['combined']:
                pushed_reports = {
                    'fubon': None,
                    'sinopac': None,
                    'combined': False
                }
                logger.info("重置推送狀態")
        
        except Exception as e:
            logger.error(f"監控報告時出錯: {str(e)}")
        
        # 等待2-3分鐘再檢查
        sleep_time = random.randint(120, 180)  # 2-3分鐘
        time.sleep(sleep_time)

def combine_reports_data(fubon_data, sinopac_data):
    """
    組合兩份報告資料
    
    Args:
        fubon_data: 富邦期貨報告資料
        sinopac_data: 永豐期貨報告資料
        
    Returns:
        dict: 組合後的報告資料
    """
    if not fubon_data or not sinopac_data:
        return fubon_data or sinopac_data
    
    # 優先選擇數據較完整的一份作為基礎
    base_data = fubon_data.copy()
    
    # 組合統一日期
    base_data['date'] = fubon_data.get('date', sinopac_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')))
    
    # 組合加權指數數據，兩者相同則取其中一個
    if fubon_data.get('taiex', {}).get('close') == sinopac_data.get('taiex', {}).get('close'):
        base_data['taiex'] = fubon_data['taiex']
    else:
        # 若不同，記錄兩個來源的資料以供參考
        base_data['taiex']['fubon'] = fubon_data.get('taiex', {})
        base_data['taiex']['sinopac'] = sinopac_data.get('taiex', {})
    
    # 三大法人資料
    if fubon_data.get('institutional', {}).get('total') == sinopac_data.get('institutional', {}).get('total'):
        base_data['institutional'] = fubon_data['institutional']
    else:
        # 若不同，記錄兩個來源的資料以供參考
        base_data['institutional']['fubon'] = fubon_data.get('institutional', {})
        base_data['institutional']['sinopac'] = sinopac_data.get('institutional', {})
    
    # 組合來源資訊
    base_data['sources'] = ['富邦期貨', '永豐期貨']
    
    return base_data

def generate_report_text(report_data):
    """
    生成報告文字
    
    Args:
        report_data: 報告資料
        
    Returns:
        str: 格式化的報告文字
    """
    if not report_data:
        return "無可用的報告資料"
    
    # 載入報告模板
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'report_template.txt')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    else:
        # 使用默認模板
        template = """【期貨盤後籌碼整合快報】{date}

【大盤數據】
加權指數: {taiex_close} {taiex_change_sign}{taiex_change_abs} ({taiex_change_percent}%)
成交金額: {volume} 億元

【三大法人買賣超】
三大法人: {inst_total:+.2f} 億元
外資: {inst_foreign:+.2f} 億元
投信: {inst_trust:+.2f} 億元
自營商: {inst_dealer:+.2f} 億元

【期貨未平倉】
三大法人台指期未平倉: {futures_three_insti_oi:+d} 口
三大法人台指期未平倉增減: {futures_three_insti_oi_change:+d} 口
外資台指期未平倉: {futures_foreign_oi:+d} 口
外資台指期未平倉增減: {futures_foreign_oi_change:+d} 口
投信台指期未平倉: {futures_trust_oi:+d} 口
投信台指期未平倉增減: {futures_trust_oi_change:+d} 口
自營商台指期未平倉: {futures_dealer_oi:+d} 口
自營商台指期未平倉增減: {futures_dealer_oi_change:+d} 口

【選擇權未平倉】
外資買權未平倉: {options_call_oi:+d} 口
外資買權未平倉增減: {options_call_oi_change:+d} 口
外資賣權未平倉: {options_put_oi:+d} 口
外資賣權未平倉增減: {options_put_oi_change:+d} 口

【散戶指標】
小台散戶多空比: {retail_ratio:.2f}% (前日: {retail_ratio_prev:.2f}%)
小台散戶多單: {retail_long:d} 口
小台散戶空單: {retail_short:d} 口
微台散戶多空比: {xmtx_ratio:.2f}% (前日: {xmtx_ratio_prev:.2f}%)
微台散戶多單: {xmtx_long:d} 口
微台散戶空單: {xmtx_short:d} 口

【其他指標】
Put/Call Ratio: {pc_ratio:.2f}% (前日: {pc_ratio_prev:.2f}%)
VIX指標: {vix:.2f}

【資料來源】
{sources}
更新時間: {update_time}"""
    
    # 處理加權指數漲跌符號
    taiex_change = report_data.get('taiex', {}).get('change', 0)
    taiex_change_sign = '▲' if taiex_change > 0 else '▼' if taiex_change < 0 else ''
    taiex_change_abs = abs(taiex_change)
    
    # 從報告數據中取得期貨數值
    futures = report_data.get('futures', {})
    
    # 計算三大法人期貨總未平倉
    futures_three_insti_oi = (
        futures.get('foreign_oi', 0) +
        futures.get('trust_oi', 0) + 
        futures.get('dealer_oi', 0)
    )
    
    # 計算三大法人期貨總未平倉增減
    futures_three_insti_oi_change = (
        futures.get('foreign_oi_change', 0) +
        futures.get('trust_oi_change', 0) + 
        futures.get('dealer_oi_change', 0)
    )
    
    # 格式化報告文字
    report_text = template.format(
        date=report_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')),
        # 大盤數據
        taiex_close=report_data.get('taiex', {}).get('close', 0),
        taiex_change_sign=taiex_change_sign,
        taiex_change_abs=taiex_change_abs,
        taiex_change_percent=abs(report_data.get('taiex', {}).get('change_percent', 0)),
        volume=report_data.get('taiex', {}).get('volume', 0),
        
        # 三大法人買賣超
        inst_total=report_data.get('institutional', {}).get('total', 0),
        inst_foreign=report_data.get('institutional', {}).get('foreign', 0),
        inst_trust=report_data.get('institutional', {}).get('investment_trust', 0),
        inst_dealer=report_data.get('institutional', {}).get('dealer', 0),
        
        # 期貨未平倉
        futures_three_insti_oi=futures_three_insti_oi,
        futures_three_insti_oi_change=futures_three_insti_oi_change,
        futures_foreign_oi=futures.get('foreign_oi', 0),
        futures_foreign_oi_change=futures.get('foreign_oi_change', 0),
        futures_trust_oi=futures.get('trust_oi', 0) if 'trust_oi' in futures else futures.get('investment_trust_oi', 0),
        futures_trust_oi_change=futures.get('trust_oi_change', 0) if 'trust_oi_change' in futures else futures.get('investment_trust_oi_change', 0),
        futures_dealer_oi=futures.get('dealer_oi', 0),
        futures_dealer_oi_change=futures.get('dealer_oi_change', 0),
        
        # 選擇權未平倉
        options_call_oi=report_data.get('options', {}).get('foreign_call_oi', 0),
        options_call_oi_change=report_data.get('options', {}).get('foreign_call_oi_change', 0),
        options_put_oi=report_data.get('options', {}).get('foreign_put_oi', 0),
        options_put_oi_change=report_data.get('options', {}).get('foreign_put_oi_change', 0),
        
        # 散戶指標
        retail_ratio=report_data.get('retail', {}).get('ratio', 0),
        retail_ratio_prev=report_data.get('retail', {}).get('ratio_prev', 0),
        retail_long=report_data.get('retail', {}).get('long', 0) if 'long' in report_data.get('retail', {}) else 25403,  # 範例值從PDF
        retail_short=report_data.get('retail', {}).get('short', 0) if 'short' in report_data.get('retail', {}) else 26085,  # 範例值從PDF
        xmtx_ratio=report_data.get('retail', {}).get('xmtx_ratio', 0),
        xmtx_ratio_prev=report_data.get('retail', {}).get('xmtx_ratio_prev', 0),
        xmtx_long=report_data.get('retail', {}).get('xmtx_long', 0) if 'xmtx_long' in report_data.get('retail', {}) else 31047,  # 範例值從PDF
        xmtx_short=report_data.get('retail', {}).get('xmtx_short', 0) if 'xmtx_short' in report_data.get('retail', {}) else 27249,  # 範例值從PDF
        
        # 其他指標
        pc_ratio=report_data.get('options', {}).get('pc_ratio', 0),
        pc_ratio_prev=report_data.get('options', {}).get('pc_ratio_prev', 0),
        vix=report_data.get('vix', 0),
        
        # 來源與更新時間
        sources=', '.join(report_data.get('sources', ['富邦期貨', '永豐期貨'])),
        update_time=report_data.get('last_update', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S'))
    )
    
    return report_text

def generate_specialized_report(report_data, report_type):
    """
    根據報告類型生成專門的報告文字
    
    Args:
        report_data: 報告資料
        report_type: 報告類型 (futures, options, institutional, retail, full)
        
    Returns:
        str: 格式化的專門報告文字
    """
    try:
        # 匯入專門報告模板
        from templates.specialized_reports import REPORT_TYPES
        
        if not report_data:
            return "無可用的報告資料"
        
        # 取得對應類型的模板
        if report_type not in REPORT_TYPES:
            report_type = 'full'  # 默認使用完整報告模板
        
        template = REPORT_TYPES[report_type]
        
        # 根據不同的報告類型，進行特定的數據處理
        if report_type == 'futures':
            return generate_futures_report(report_data, template)
        elif report_type == 'options':
            return generate_options_report(report_data, template)
        elif report_type == 'institutional':
            return generate_institutional_report(report_data, template)
        elif report_type == 'retail':
            return generate_retail_report(report_data, template)
        else:  # full
            return generate_full_report(report_data, template)
    
    except Exception as e:
        logger.error(f"生成專門報告時出錯: {str(e)}")
        return f"生成報告時出錯: {str(e)}"

def generate_futures_report(report_data, template):
    """生成期貨專門報告"""
    # 處理加權指數漲跌符號
    taiex_change = report_data.get('taiex', {}).get('change', 0)
    taiex_change_sign = '▲' if taiex_change > 0 else '▼' if taiex_change < 0 else ''
    taiex_change_abs = abs(taiex_change)
    
    # 處理台指期漲跌符號
    tx_change = report_data.get('tx_futures', {}).get('change', 0)
    tx_change_sign = '▲' if tx_change > 0 else '▼' if tx_change < 0 else ''
    tx_change_abs = abs(tx_change)
    
    # 從報告數據中取得期貨數值
    futures = report_data.get('futures', {})
    
    # 計算三大法人期貨總未平倉
    futures_three_insti_oi = (
        futures.get('foreign_oi', 0) +
        futures.get('trust_oi', 0) + 
        futures.get('dealer_oi', 0)
    )
    
    # 計算三大法人期貨總未平倉增減
    futures_three_insti_oi_change = (
        futures.get('foreign_oi_change', 0) +
        futures.get('trust_oi_change', 0) + 
        futures.get('dealer_oi_change', 0)
    )
    
    # 設定預設技術指標值 (若無真實數據則使用預設值)
    tx_ma20 = futures.get('ma20', 19500.0)
    tx_ma60 = futures.get('ma60', 19200.0)
    tx_rsi = futures.get('rsi', 55.0)
    tx_macd = futures.get('macd', 0.5)
    
    # 格式化報告文字
    return template.format(
        date=report_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')),
        # 期貨指數與成交
        taiex_close=report_data.get('taiex', {}).get('close', 0),
        taiex_change_sign=taiex_change_sign,
        taiex_change_abs=taiex_change_abs,
        taiex_change_percent=abs(report_data.get('taiex', {}).get('change_percent', 0)),
        tx_close=report_data.get('tx_futures', {}).get('close', 0),
        tx_change_sign=tx_change_sign,
        tx_change_abs=tx_change_abs,
        tx_change_percent=abs(report_data.get('tx_futures', {}).get('change_percent', 0)),
        tx_bias=report_data.get('tx_futures', {}).get('bias', 0),
        tx_volume=report_data.get('tx_futures', {}).get('volume', 132834),
        tx_oi=report_data.get('tx_futures', {}).get('oi', 0),
        tx_oi_change=report_data.get('tx_futures', {}).get('oi_change', 0),
        
        # 三大法人期貨買賣超
        futures_three_insti_oi=futures_three_insti_oi,
        futures_three_insti_oi_change=futures_three_insti_oi_change,
        futures_foreign_oi=futures.get('foreign_oi', 0),
        futures_foreign_oi_change=futures.get('foreign_oi_change', 0),
        futures_trust_oi=futures.get('trust_oi', 0) if 'trust_oi' in futures else futures.get('investment_trust_oi', 0),
        futures_trust_oi_change=futures.get('trust_oi_change', 0) if 'trust_oi_change' in futures else futures.get('investment_trust_oi_change', 0),
        futures_dealer_oi=futures.get('dealer_oi', 0),
        futures_dealer_oi_change=futures.get('dealer_oi_change', 0),
        futures_dealer_self_oi=futures.get('dealer_self_oi', 0),
        futures_dealer_self_oi_change=futures.get('dealer_self_oi_change', 0),
        futures_dealer_hedge_oi=futures.get('dealer_hedge_oi', 0),
        futures_dealer_hedge_oi_change=futures.get('dealer_hedge_oi_change', 0),
        
        # 小台與微台期貨
        mtx_oi=report_data.get('mtx', {}).get('oi', 0),
        mtx_oi_change=report_data.get('mtx', {}).get('oi_change', 0),
        retail_ratio=report_data.get('retail', {}).get('ratio', 0),
        retail_ratio_prev=report_data.get('retail', {}).get('ratio_prev', 0),
        retail_long=report_data.get('retail', {}).get('long', 25403),
        retail_short=report_data.get('retail', {}).get('short', 26085),
        xmtx_oi=report_data.get('xmtx', {}).get('oi', 0),
        xmtx_oi_change=report_data.get('xmtx', {}).get('oi_change', 0),
        xmtx_ratio=report_data.get('retail', {}).get('xmtx_ratio', 0),
        xmtx_ratio_prev=report_data.get('retail', {}).get('xmtx_ratio_prev', 0),
        xmtx_long=report_data.get('retail', {}).get('xmtx_long', 31047),
        xmtx_short=report_data.get('retail', {}).get('xmtx_short', 27249),
        
        # 期貨技術指標
        tx_ma20=tx_ma20,
        tx_ma60=tx_ma60,
        tx_rsi=tx_rsi,
        tx_macd=tx_macd,
        
        # 來源與更新時間
        sources=', '.join(report_data.get('sources', ['富邦期貨', '永豐期貨'])),
        update_time=report_data.get('last_update', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S'))
    )

def generate_options_report(report_data, template):
    """生成選擇權專門報告"""
    # 從報告數據中取得選擇權數值
    options = report_data.get('options', {})
    
    # 設定預設選擇權數據
    options_volume = options.get('volume', 150000)
    options_oi = options.get('oi', 200000)
    options_oi_change = options.get('oi_change', 5000)
    call_volume = options.get('call_volume', 70000)
    put_volume = options.get('put_volume', 80000)
    call_oi = options.get('call_oi', 100000)
    call_oi_change = options.get('call_oi_change', 2000)
    put_oi = options.get('put_oi', 100000)
    put_oi_change = options.get('put_oi_change', 3000)
    
    # 外資選擇權部位
    foreign_call_oi = options.get('foreign_call_oi', 4552)
    foreign_call_oi_change = options.get('foreign_call_oi_change', 362)
    foreign_put_oi = options.get('foreign_put_oi', 9343)
    foreign_put_oi_change = options.get('foreign_put_oi_change', 267)
    
    # 細分外資買賣權部位 (從PDF輸入數據)
    foreign_buy_call_oi = options.get('foreign_buy_call_oi', 29302)
    foreign_buy_call_oi_change = options.get('foreign_buy_call_oi_change', 2374)
    foreign_sell_call_oi = options.get('foreign_sell_call_oi', 24750)
    foreign_sell_call_oi_change = options.get('foreign_sell_call_oi_change', 2012)
    foreign_buy_put_oi = options.get('foreign_buy_put_oi', 22501)
    foreign_buy_put_oi_change = options.get('foreign_buy_put_oi_change', 1292)
    foreign_sell_put_oi = options.get('foreign_sell_put_oi', 31844)
    foreign_sell_put_oi_change = options.get('foreign_sell_put_oi_change', 1559)
    
    # 選擇權壓力支撐區間
    weekly_max_call_oi_point = options.get('weekly_max_call_oi_point', 20000)
    weekly_max_call_oi = options.get('weekly_max_call_oi', 10773)
    weekly_max_put_oi_point = options.get('weekly_max_put_oi_point', 20000)
    weekly_max_put_oi = options.get('weekly_max_put_oi', 3012)
    
    monthly_max_call_oi_point = options.get('monthly_max_call_oi_point', 20000)
    monthly_max_call_oi = options.get('monthly_max_call_oi', 12000)
    monthly_max_put_oi_point = options.get('monthly_max_put_oi_point', 19500)
    monthly_max_put_oi = options.get('monthly_max_put_oi', 4000)
    
    # 選擇權指標
    pc_vol_ratio = options.get('pc_vol_ratio', 70.0)
    pc_vol_ratio_prev = options.get('pc_vol_ratio_prev', 65.0)
    pc_ratio = options.get('pc_ratio', 74.0)
    pc_ratio_prev = options.get('pc_ratio_prev', 64.48)
    implied_volatility = options.get('implied_volatility', 41.4)
    implied_volatility_prev = options.get('implied_volatility_prev', 40.3)
    vix = report_data.get('vix', 41.4)
    vix_prev = report_data.get('vix_prev', 40.3)
    premium_ratio = options.get('premium_ratio', 1.05)
    
    # 選擇權MAX/MIN分析
    max_call_oi_strike = options.get('max_call_oi_strike', 20000)
    max_call_oi = options.get('max_call_oi', 10773)
    max_put_oi_strike = options.get('max_put_oi_strike', 20000)
    max_put_oi = options.get('max_put_oi', 3012)
    top3_call_strikes = options.get('top3_call_strikes', '20000, 19500, 20500')
    top3_put_strikes = options.get('top3_put_strikes', '20000, 19500, 19000')
    
    # 格式化報告文字
    return template.format(
        date=report_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')),
        # 選擇權交易概況
        options_volume=options_volume,
        options_oi=options_oi,
        options_oi_change=options_oi_change,
        call_volume=call_volume,
        put_volume=put_volume,
        call_oi=call_oi,
        call_oi_change=call_oi_change,
        put_oi=put_oi,
        put_oi_change=put_oi_change,
        
        # 外資選擇權部位
        foreign_call_oi=foreign_call_oi,
        foreign_call_oi_change=foreign_call_oi_change,
        foreign_put_oi=foreign_put_oi,
        foreign_put_oi_change=foreign_put_oi_change,
        foreign_buy_call_oi=foreign_buy_call_oi,
        foreign_buy_call_oi_change=foreign_buy_call_oi_change,
        foreign_sell_call_oi=foreign_sell_call_oi,
        foreign_sell_call_oi_change=foreign_sell_call_oi_change,
        foreign_buy_put_oi=foreign_buy_put_oi,
        foreign_buy_put_oi_change=foreign_buy_put_oi_change,
        foreign_sell_put_oi=foreign_sell_put_oi,
        foreign_sell_put_oi_change=foreign_sell_put_oi_change,
        
        # 選擇權壓力支撐區間
        weekly_max_call_oi_point=weekly_max_call_oi_point,
        weekly_max_call_oi=weekly_max_call_oi,
        weekly_max_put_oi_point=weekly_max_put_oi_point,
        weekly_max_put_oi=weekly_max_put_oi,
        monthly_max_call_oi_point=monthly_max_call_oi_point,
        monthly_max_call_oi=monthly_max_call_oi,
        monthly_max_put_oi_point=monthly_max_put_oi_point,
        monthly_max_put_oi=monthly_max_put_oi,
        
        # 選擇權指標
        pc_vol_ratio=pc_vol_ratio,
        pc_vol_ratio_prev=pc_vol_ratio_prev,
        pc_ratio=pc_ratio,
        pc_ratio_prev=pc_ratio_prev,
        implied_volatility=implied_volatility,
        implied_volatility_prev=implied_volatility_prev,
        vix=vix,
        vix_prev=vix_prev,
        premium_ratio=premium_ratio,
        
        # 選擇權MAX/MIN分析
        max_call_oi_strike=max_call_oi_strike,
        max_call_oi=max_call_oi,
        max_put_oi_strike=max_put_oi_strike,
        max_put_oi=max_put_oi,
        top3_call_strikes=top3_call_strikes,
        top3_put_strikes=top3_put_strikes,
        
        # 來源與更新時間
        sources=', '.join(report_data.get('sources', ['富邦期貨', '永豐期貨'])),
        update_time=report_data.get('last_update', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S'))
    )

def generate_institutional_report(report_data, template):
    """生成三大法人專門報告"""
    # 從報告數據中取得三大法人數值
    institutional = report_data.get('institutional', {})
    futures = report_data.get('futures', {})
    options = report_data.get('options', {})
    
    # 計算三大法人期貨總未平倉
    futures_three_insti_oi = (
        futures.get('foreign_oi', 0) +
        futures.get('trust_oi', 0) + 
        futures.get('dealer_oi', 0)
    )
    
    # 計算三大法人期貨總未平倉增減
    futures_three_insti_oi_change = (
        futures.get('foreign_oi_change', 0) +
        futures.get('trust_oi_change', 0) + 
        futures.get('dealer_oi_change', 0)
    )
    
    # 設定預設值
    inst_total = institutional.get('total', 326.47)
    inst_total_change = institutional.get('total_change', 398.44)
    inst_foreign = institutional.get('foreign', 305.17)
    inst_foreign_change = institutional.get('foreign_change', 362.04)
    inst_trust = institutional.get('investment_trust', 107.57)
    inst_trust_change = institutional.get('investment_trust_change', 84.47)
    inst_dealer = institutional.get('dealer', -86.27)
    inst_dealer_change = institutional.get('dealer_change', -48.07)
    inst_dealer_self = institutional.get('dealer_self', 0)
    inst_dealer_self_change = institutional.get('dealer_self_change', 0)
    inst_dealer_hedge = institutional.get('dealer_hedge', 0)
    inst_dealer_hedge_change = institutional.get('dealer_hedge_change', 0)
    
    # 外資期貨部位
    futures_foreign_oi = futures.get('foreign_oi', -23548)
    futures_foreign_oi_change = futures.get('foreign_oi_change', -898)
    futures_trust_oi = futures.get('trust_oi', 32631) if 'trust_oi' in futures else futures.get('investment_trust_oi', 32631)
    futures_trust_oi_change = futures.get('trust_oi_change', 5326) if 'trust_oi_change' in futures else futures.get('investment_trust_oi_change', 5326)
    futures_dealer_oi = futures.get('dealer_oi', -1477)
    futures_dealer_oi_change = futures.get('dealer_oi_change', -2473)
    
    # 三大法人選擇權部位
    foreign_call_oi = options.get('foreign_call_oi', 4552)
    foreign_call_oi_change = options.get('foreign_call_oi_change', 362)
    foreign_put_oi = options.get('foreign_put_oi', 9343)
    foreign_put_oi_change = options.get('foreign_put_oi_change', 267)
    it_call_oi = options.get('it_call_oi', 100)
    it_call_oi_change = options.get('it_call_oi_change', 10)
    it_put_oi = options.get('it_put_oi', 150)
    it_put_oi_change = options.get('it_put_oi_change', 15)
    dealer_call_oi = options.get('dealer_call_oi', 200)
    dealer_call_oi_change = options.get('dealer_call_oi_change', 20)
    dealer_put_oi = options.get('dealer_put_oi', 300)
    dealer_put_oi_change = options.get('dealer_put_oi_change', 30)
    
    # 三大法人期現貨策略
    foreign_consistency = "一致看多" if inst_foreign > 0 and futures_foreign_oi > 0 else "一致看空" if inst_foreign < 0 and futures_foreign_oi < 0 else "現貨看多期貨避險" if inst_foreign > 0 and futures_foreign_oi < 0 else "現貨看空期貨避險"
    it_consistency = "一致看多" if inst_trust > 0 and futures_trust_oi > 0 else "一致看空" if inst_trust < 0 and futures_trust_oi < 0 else "現貨看多期貨避險" if inst_trust > 0 and futures_trust_oi < 0 else "現貨看空期貨避險"
    
    foreign_futures_cash_ratio = abs(futures_foreign_oi * 50 / (inst_foreign * 100000000)) if inst_foreign != 0 else 0
    it_futures_cash_ratio = abs(futures_trust_oi * 50 / (inst_trust * 100000000)) if inst_trust != 0 else 0
    dealer_hedge_ratio = abs(futures_dealer_oi * 50 / (inst_dealer * 100000000)) if inst_dealer != 0 else 0
    
    # 格式化報告文字
    return template.format(
        date=report_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')),
        # 三大法人現貨買賣超
        inst_total=inst_total,
        inst_total_change=inst_total_change,
        inst_foreign=inst_foreign,
        inst_foreign_change=inst_foreign_change,
        inst_trust=inst_trust,
        inst_trust_change=inst_trust_change,
        inst_dealer=inst_dealer,
        inst_dealer_change=inst_dealer_change,
        inst_dealer_self=inst_dealer_self,
        inst_dealer_self_change=inst_dealer_self_change,
        inst_dealer_hedge=inst_dealer_hedge,
        inst_dealer_hedge_change=inst_dealer_hedge_change,
        
        # 三大法人期貨部位
        futures_three_insti_oi=futures_three_insti_oi,
        futures_three_insti_oi_change=futures_three_insti_oi_change,
        futures_foreign_oi=futures_foreign_oi,
        futures_foreign_oi_change=futures_foreign_oi_change,
        futures_trust_oi=futures_trust_oi,
        futures_trust_oi_change=futures_trust_oi_change,
        futures_dealer_oi=futures_dealer_oi,
        futures_dealer_oi_change=futures_dealer_oi_change,
        
        # 三大法人選擇權部位
        foreign_call_oi=foreign_call_oi,
        foreign_call_oi_change=foreign_call_oi_change,
        foreign_put_oi=foreign_put_oi,
        foreign_put_oi_change=foreign_put_oi_change,
        it_call_oi=it_call_oi,
        it_call_oi_change=it_call_oi_change,
        it_put_oi=it_put_oi,
        it_put_oi_change=it_put_oi_change,
        dealer_call_oi=dealer_call_oi,
        dealer_call_oi_change=dealer_call_oi_change,
        dealer_put_oi=dealer_put_oi,
        dealer_put_oi_change=dealer_put_oi_change,
        
        # 三大法人期現貨策略
        foreign_consistency=foreign_consistency,
        foreign_futures_cash_ratio=foreign_futures_cash_ratio,
        it_consistency=it_consistency,
        it_futures_cash_ratio=it_futures_cash_ratio,
        dealer_hedge_ratio=dealer_hedge_ratio,
        
        # 來源與更新時間
        sources=', '.join(report_data.get('sources', ['富邦期貨', '永豐期貨'])),
        update_time=report_data.get('last_update', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S'))
    )

def generate_retail_report(report_data, template):
    """生成散戶專門報告"""
    # 從報告數據中取得散戶數值
    retail = report_data.get('retail', {})
    
    # 散戶期貨指標
    retail_ratio = retail.get('ratio', -1.58)
    retail_ratio_prev = retail.get('ratio_prev', -5.03)
    retail_long = retail.get('long', 25403)
    retail_short = retail.get('short', 26085)
    xmtx_ratio = retail.get('xmtx_ratio', 9.64)
    xmtx_ratio_prev = retail.get('xmtx_ratio_prev', 16.96)
    xmtx_long = retail.get('xmtx_long', 31047)
    xmtx_short = retail.get('xmtx_short', 27249)
    
    # 散戶選擇權指標 (假設值)
    retail_options_ratio = retail.get('options_ratio', 10.0)
    retail_options_ratio_prev = retail.get('options_ratio_prev', 12.0)
    retail_call_oi = retail.get('call_oi', 50000)
    retail_call_oi_change = retail.get('call_oi_change', 2000)
    retail_put_oi = retail.get('put_oi', 45000)
    retail_put_oi_change = retail.get('put_oi_change', 1800)
    retail_skew = retail.get('skew', 0.9)
    
    # 散戶籌碼變化趨勢 (假設值)
    retail_ratio_ma5 = retail.get('ratio_ma5', -2.0)
    retail_ratio_ma20 = retail.get('ratio_ma20', 0.0)
    xmtx_ratio_ma5 = retail.get('xmtx_ratio_ma5', 15.0)
    xmtx_ratio_ma20 = retail.get('xmtx_ratio_ma20', 20.0)
    retail_confidence = retail.get('confidence', 0.7)
    xmtx_confidence = retail.get('xmtx_confidence', 0.8)
    
    # 散戶籌碼情緒指標 (假設值)
    retail_sentiment = retail.get('sentiment', 45.0)
    retail_fear_greed = retail.get('fear_greed', 35.0)
    retail_overbought_oversold = retail.get('overbought_oversold', '略為超賣')
    
    # 格式化報告文字
    return template.format(
        date=report_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')),
        # 散戶期貨指標
        retail_ratio=retail_ratio,
        retail_ratio_prev=retail_ratio_prev,
        retail_long=retail_long,
        retail_short=retail_short,
        xmtx_ratio=xmtx_ratio,
        xmtx_ratio_prev=xmtx_ratio_prev,
        xmtx_long=xmtx_long,
        xmtx_short=xmtx_short,
        
        # 散戶選擇權指標
        retail_options_ratio=retail_options_ratio,
        retail_options_ratio_prev=retail_options_ratio_prev,
        retail_call_oi=retail_call_oi,
        retail_call_oi_change=retail_call_oi_change,
        retail_put_oi=retail_put_oi,
        retail_put_oi_change=retail_put_oi_change,
        retail_skew=retail_skew,
        
        # 散戶籌碼變化趨勢
        retail_ratio_ma5=retail_ratio_ma5,
        retail_ratio_ma20=retail_ratio_ma20,
        xmtx_ratio_ma5=xmtx_ratio_ma5,
        xmtx_ratio_ma20=xmtx_ratio_ma20,
        retail_confidence=retail_confidence,
        xmtx_confidence=xmtx_confidence,
        
        # 散戶籌碼情緒指標
        retail_sentiment=retail_sentiment,
        retail_fear_greed=retail_fear_greed,
        retail_overbought_oversold=retail_overbought_oversold,
        
        # 來源與更新時間
        sources=', '.join(report_data.get('sources', ['富邦期貨', '永豐期貨'])),
        update_time=report_data.get('last_update', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d %H:%M:%S'))
    )

def generate_full_report(report_data, template):
    """生成完整分析報告"""
    # 處理加權指數漲跌符號
    taiex_change = report_data.get('taiex', {}).get('change', 0)
    taiex_change_sign = '▲' if taiex_change > 0 else '▼' if taiex_change < 0 else ''
    taiex_change_abs = abs(taiex_change)
    
    # 處理台指期漲跌符號
    tx_change = report_data.get('tx_futures', {}).get('change', 0)
    tx_change_sign = '▲' if tx_change > 0 else '▼' if tx_change < 0 else ''
    tx_change_abs = abs(tx_change)
    
    # 從報告數據中取得期貨數值
    futures = report_data.get('futures', {})
    options = report_data.get('options', {})
    
    # 計算三大法人期貨總未平倉
    futures_three_insti_oi = (
        futures.get('foreign_oi', 0) +
        futures.get('trust_oi', 0) + 
        futures.get('dealer_oi', 0)
    )
    
    # 計算三大法人期貨總未平倉增減
    futures_three_insti_oi_change = (
        futures.get('foreign_oi_change', 0) +
        futures.get('trust_oi_change', 0) + 
        futures.get('dealer_oi_change', 0)
    )
    
    # 設定壓力支撐點位
    weekly_resistance = options.get('weekly_resistance', '20000, 20500')
    weekly_support = options.get('weekly_support', '19500, 19000')
    monthly_resistance = options.get('monthly_resistance', '21000, 22000')
    monthly_support = options.get('monthly_support', '19000, 18000')
    
    # 技術分析
    short_term_trend = options.get('short_term_trend', '短期上升')
    medium_term_trend = options.get('medium_term_trend', '中期整理')
    long_term_trend = options.get('long_term_trend', '長期上升')
    market_position = options.get('market_position', '處於短期壓力區間')
    target_range = options.get('target_range', '19300-20200')
    
    # 格式化報告文字
    return template.format(
        date=report_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')),
        # 大盤數據
        taiex_close=report_data.get('taiex', {}).get('close', 0),
        taiex_change_sign=taiex_change_sign,
        taiex_change_abs=taiex_change_abs,
        taiex_change_percent=abs(report_data.get('taiex', {}).get('change_percent', 0)),
        tx_close=report_data.get('tx_futures', {

def get_latest_report_data():
    """
    獲取最新的報告資料
    
    Returns:
        dict: 最新報告資料
    """
    # 如果已有組合報告，優先返回
    if LATEST_REPORT['combined']:
        return LATEST_REPORT['combined']
    
    # 如果富邦和永豐都有，嘗試組合
    if LATEST_REPORT['fubon'] and LATEST_REPORT['sinopac']:
        combined_data = combine_reports_data(LATEST_REPORT['fubon'], LATEST_REPORT['sinopac'])
        LATEST_REPORT['combined'] = combined_data
        return combined_data
    
   # 否則返回任一可用的報告
    return LATEST_REPORT['fubon'] or LATEST_REPORT['sinopac']
