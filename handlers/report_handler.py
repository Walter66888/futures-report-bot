def combine_reports_data(fubon_data, sinopac_data):
    """
    組合兩份報告資料
    
    Args:
        fubon_data: 富邦期貨報告資料
        sinopac_data: 永豐期貨報告資料
        
    Returns:
        dict: 組合後的報告資料
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"合併報告 - 富邦數據: {fubon_data}")
    logger.info(f"合併報告 - 永豐數據: {sinopac_data}")
    
    # 檢查輸入數據
    if not fubon_data and not sinopac_data:
        logger.warning("無可用資料進行合併")
        return None
    
    # 如果只有一份報告可用，直接返回
    if not fubon_data:
        logger.info("僅使用永豐期貨數據")
        return sinopac_data
    
    if not sinopac_data:
        logger.info("僅使用富邦期貨數據")
        return fubon_data
    
    # 優先選擇數據較完整的一份作為基礎
    base_data = fubon_data.copy()
    logger.info(f"使用富邦期貨數據作為基礎，進行合併")
    
    # 組合統一日期
    base_data['date'] = fubon_data.get('date', sinopac_data.get('date', datetime.now(TW_TIMEZONE).strftime('%Y/%m/%d')))
    
    # 組合加權指數數據
    # 如果兩份報告的加權指數都為0，優先使用富邦的數據
    if fubon_data.get('taiex', {}).get('close') == 0 and sinopac_data.get('taiex', {}).get('close') > 0:
        logger.info(f"使用永豐期貨的加權指數數據: {sinopac_data['taiex']}")
        base_data['taiex'] = sinopac_data['taiex']
    
    # 組合三大法人資料
    # 如果富邦的資料是0，而永豐有資料，則使用永豐的數據
    if fubon_data.get('institutional', {}).get('total') == 0 and sinopac_data.get('institutional', {}).get('total') != 0:
        logger.info(f"使用永豐期貨的三大法人數據: {sinopac_data['institutional']}")
        base_data['institutional'] = sinopac_data['institutional']
    
    # 組合期貨未平倉資料
    if fubon_data.get('futures', {}).get('foreign_oi') == 0 and sinopac_data.get('futures', {}).get('foreign_oi') != 0:
        logger.info(f"使用永豐期貨的期貨未平倉數據: {sinopac_data['futures']}")
        base_data['futures'] = sinopac_data['futures']
    
    # 組合選擇權資料
    if fubon_data.get('options', {}).get('foreign_call_oi') == 0 and sinopac_data.get('options', {}).get('foreign_call_oi') != 0:
        logger.info(f"使用永豐期貨的選擇權數據: {sinopac_data['options']}")
        base_data['options'] = sinopac_data['options']
    
    # 組合散戶指標資料
    # 如果富邦的散戶數據更完整，優先使用富邦的數據
    retail_fubon_count = sum(1 for k, v in fubon_data.get('retail', {}).items() if v != 0)
    retail_sinopac_count = sum(1 for k, v in sinopac_data.get('retail', {}).items() if v != 0)
    
    if retail_sinopac_count > retail_fubon_count:
        logger.info(f"使用永豐期貨的散戶指標數據: {sinopac_data['retail']}")
        base_data['retail'] = sinopac_data['retail']
    
    # 合併VIX數據 (誰有用誰的)
    if fubon_data.get('vix', 0) == 0 and sinopac_data.get('vix', 0) != 0:
        base_data['vix'] = sinopac_data['vix']
        logger.info(f"使用永豐期貨的VIX數據: {sinopac_data['vix']}")
    
    # 組合來源資訊
    base_data['sources'] = ['富邦期貨', '永豐期貨']
    logger.info(f"合併完成，結果: {base_data}")
    
    return base_data
