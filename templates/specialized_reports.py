"""
專門針對各類查詢的報告模板
"""

# 期貨籌碼報告模板
FUTURES_REPORT_TEMPLATE = """【期貨籌碼詳細報告】{date}

【期貨指數與成交】
加權指數: {taiex_close} {taiex_change_sign}{taiex_change_abs} ({taiex_change_percent}%)
台指期近月: {tx_close} {tx_change_sign}{tx_change_abs} ({tx_change_percent}%)
台指期現貨價差: {tx_bias:+.2f}
台指期成交量: {tx_volume:,d} 口
台指期未平倉量: {tx_oi:,d} 口 ({tx_oi_change:+d})

【三大法人期貨買賣超】
三大法人: {futures_three_insti_oi:+d} 口 ({futures_three_insti_oi_change:+d})
外資: {futures_foreign_oi:+d} 口 ({futures_foreign_oi_change:+d})
投信: {futures_trust_oi:+d} 口 ({futures_trust_oi_change:+d})
自營商: {futures_dealer_oi:+d} 口 ({futures_dealer_oi_change:+d})
自營商(自行): {futures_dealer_self_oi:+d} 口 ({futures_dealer_self_oi_change:+d})
自營商(避險): {futures_dealer_hedge_oi:+d} 口 ({futures_dealer_hedge_oi_change:+d})

【小台與微台期貨】
小台未平倉量: {mtx_oi:,d} 口 ({mtx_oi_change:+d})
小台散戶多空比: {retail_ratio:.2f}% (前日: {retail_ratio_prev:.2f}%)
小台散戶多單: {retail_long:d} 口
小台散戶空單: {retail_short:d} 口
微台未平倉量: {xmtx_oi:,d} 口 ({xmtx_oi_change:+d})
微台散戶多空比: {xmtx_ratio:.2f}% (前日: {xmtx_ratio_prev:.2f}%)
微台散戶多單: {xmtx_long:d} 口
微台散戶空單: {xmtx_short:d} 口

【期貨技術指標】
台指期20日均線: {tx_ma20:.2f}
台指期60日均線: {tx_ma60:.2f}
相對強弱指標(RSI): {tx_rsi:.2f}
MACD: {tx_macd:.2f}

【資料來源】
{sources}
更新時間: {update_time}"""

# 選擇權籌碼報告模板
OPTIONS_REPORT_TEMPLATE = """【選擇權籌碼詳細報告】{date}

【選擇權交易概況】
選擇權成交量: {options_volume:,d} 口
選擇權未平倉量: {options_oi:,d} 口 ({options_oi_change:+d})
買權成交量: {call_volume:,d} 口
賣權成交量: {put_volume:,d} 口
買權未平倉量: {call_oi:,d} 口 ({call_oi_change:+d})
賣權未平倉量: {put_oi:,d} 口 ({put_oi_change:+d})

【外資選擇權部位】
外資買權未平倉: {foreign_call_oi:+d} 口 ({foreign_call_oi_change:+d})
外資賣權未平倉: {foreign_put_oi:+d} 口 ({foreign_put_oi_change:+d})
外資買買權未平倉: {foreign_buy_call_oi:d} 口 ({foreign_buy_call_oi_change:+d})
外資賣買權未平倉: {foreign_sell_call_oi:d} 口 ({foreign_sell_call_oi_change:+d})
外資買賣權未平倉: {foreign_buy_put_oi:d} 口 ({foreign_buy_put_oi_change:+d})
外資賣賣權未平倉: {foreign_sell_put_oi:d} 口 ({foreign_sell_put_oi_change:+d})

【選擇權壓力支撐區間】
近週選擇權買權最大未平倉: {weekly_max_call_oi_point} 點 ({weekly_max_call_oi:,d} 口)
近週選擇權賣權最大未平倉: {weekly_max_put_oi_point} 點 ({weekly_max_put_oi:,d} 口)
近月選擇權買權最大未平倉: {monthly_max_call_oi_point} 點 ({monthly_max_call_oi:,d} 口)
近月選擇權賣權最大未平倉: {monthly_max_put_oi_point} 點 ({monthly_max_put_oi:,d} 口)

【選擇權指標】
Put/Call Volume Ratio: {pc_vol_ratio:.2f}% (前日: {pc_vol_ratio_prev:.2f}%)
Put/Call OI Ratio: {pc_ratio:.2f}% (前日: {pc_ratio_prev:.2f}%)
隱含波動率: {implied_volatility:.2f}% (前日: {implied_volatility_prev:.2f}%)
VIX指標: {vix:.2f} (前日: {vix_prev:.2f})
選擇權賣/買權溢價率: {premium_ratio:.2f}

【選擇權MAX/MIN分析】
最高買權未平倉履約價: {max_call_oi_strike} (未平倉量: {max_call_oi:,d} 口)
最高賣權未平倉履約價: {max_put_oi_strike} (未平倉量: {max_put_oi:,d} 口)
買權未平倉前三大履約價: {top3_call_strikes}
賣權未平倉前三大履約價: {top3_put_strikes}

【資料來源】
{sources}
更新時間: {update_time}"""

# 三大法人籌碼報告模板
INSTITUTIONAL_REPORT_TEMPLATE = """【三大法人籌碼詳細報告】{date}

【三大法人現貨買賣超】
三大法人: {inst_total:+.2f} 億元 ({inst_total_change:+.2f})
外資: {inst_foreign:+.2f} 億元 ({inst_foreign_change:+.2f})
投信: {inst_trust:+.2f} 億元 ({inst_trust_change:+.2f})
自營商: {inst_dealer:+.2f} 億元 ({inst_dealer_change:+.2f})
自營商(自行): {inst_dealer_self:+.2f} 億元 ({inst_dealer_self_change:+.2f})
自營商(避險): {inst_dealer_hedge:+.2f} 億元 ({inst_dealer_hedge_change:+.2f})

【三大法人期貨部位】
三大法人台指期未平倉: {futures_three_insti_oi:+d} 口 ({futures_three_insti_oi_change:+d})
外資台指期未平倉: {futures_foreign_oi:+d} 口 ({futures_foreign_oi_change:+d})
投信台指期未平倉: {futures_trust_oi:+d} 口 ({futures_trust_oi_change:+d})
自營商台指期未平倉: {futures_dealer_oi:+d} 口 ({futures_dealer_oi_change:+d})

【三大法人選擇權部位】
外資買權未平倉: {foreign_call_oi:+d} 口 ({foreign_call_oi_change:+d})
外資賣權未平倉: {foreign_put_oi:+d} 口 ({foreign_put_oi_change:+d})
投信買權未平倉: {it_call_oi:+d} 口 ({it_call_oi_change:+d})
投信賣權未平倉: {it_put_oi:+d} 口 ({it_put_oi_change:+d})
自營商買權未平倉: {dealer_call_oi:+d} 口 ({dealer_call_oi_change:+d})
自營商賣權未平倉: {dealer_put_oi:+d} 口 ({dealer_put_oi_change:+d})

【三大法人期現貨策略】
外資現貨期貨一致性: {foreign_consistency}
外資現貨買超/賣超:計算比例: {foreign_futures_cash_ratio:.2f}
投信現貨期貨一致性: {it_consistency}
投信現貨買超/賣超:計算比例: {it_futures_cash_ratio:.2f}
自營商避險比例: {dealer_hedge_ratio:.2f}

【資料來源】
{sources}
更新時間: {update_time}"""

# 散戶籌碼報告模板
RETAIL_REPORT_TEMPLATE = """【散戶籌碼詳細報告】{date}

【散戶期貨指標】
小台散戶多空比: {retail_ratio:.2f}% (前日: {retail_ratio_prev:.2f}%)
小台散戶多單: {retail_long:d} 口
小台散戶空單: {retail_short:d} 口
微台散戶多空比: {xmtx_ratio:.2f}% (前日: {xmtx_ratio_prev:.2f}%)
微台散戶多單: {xmtx_long:d} 口
微台散戶空單: {xmtx_short:d} 口

【散戶選擇權指標】
散戶選擇權多空比: {retail_options_ratio:.2f}% (前日: {retail_options_ratio_prev:.2f}%)
散戶買權未平倉量: {retail_call_oi:d} 口 ({retail_call_oi_change:+d})
散戶賣權未平倉量: {retail_put_oi:d} 口 ({retail_put_oi_change:+d})
散戶選擇權SKEW指標: {retail_skew:.2f}

【散戶籌碼變化趨勢】
小台散戶多空比5日均線: {retail_ratio_ma5:.2f}%
小台散戶多空比20日均線: {retail_ratio_ma20:.2f}%
微台散戶多空比5日均線: {xmtx_ratio_ma5:.2f}%
微台散戶多空比20日均線: {xmtx_ratio_ma20:.2f}%
小台散戶信心指標: {retail_confidence:.2f}
微台散戶信心指標: {xmtx_confidence:.2f}

【散戶籌碼情緒指標】
散戶多空情緒指數: {retail_sentiment:.2f}
散戶恐慌/貪婪指數: {retail_fear_greed:.2f}
散戶超買/超賣指標: {retail_overbought_oversold}

【資料來源】
{sources}
更新時間: {update_time}"""

# 完整分析報告模板
FULL_ANALYSIS_TEMPLATE = """【期貨市場完整分析報告】{date}

【大盤數據】
加權指數: {taiex_close} {taiex_change_sign}{taiex_change_abs} ({taiex_change_percent}%)
台指期近月: {tx_close} {tx_change_sign}{tx_change_abs} ({tx_change_percent}%)
台指期現貨價差: {tx_bias:+.2f}
成交金額: {volume} 億元

【三大法人買賣超】
三大法人: {inst_total:+.2f} 億元 ({inst_total_change:+.2f})
外資: {inst_foreign:+.2f} 億元 ({inst_foreign_change:+.2f})
投信: {inst_trust:+.2f} 億元 ({inst_trust_change:+.2f})
自營商: {inst_dealer:+.2f} 億元 ({inst_dealer_change:+.2f})

【期貨未平倉】
三大法人台指期未平倉: {futures_three_insti_oi:+d} 口 ({futures_three_insti_oi_change:+d})
外資台指期未平倉: {futures_foreign_oi:+d} 口 ({futures_foreign_oi_change:+d})
投信台指期未平倉: {futures_trust_oi:+d} 口 ({futures_trust_oi_change:+d})
自營商台指期未平倉: {futures_dealer_oi:+d} 口 ({futures_dealer_oi_change:+d})

【選擇權數據】
Put/Call Ratio: {pc_ratio:.2f}% (前日: {pc_ratio_prev:.2f}%)
選擇權買權最大未平倉: {max_call_oi_point} 點 ({max_call_oi:,d} 口)
選擇權賣權最大未平倉: {max_put_oi_point} 點 ({max_put_oi:,d} 口)
外資買權未平倉: {foreign_call_oi:+d} 口 ({foreign_call_oi_change:+d})
外資賣權未平倉: {foreign_put_oi:+d} 口 ({foreign_put_oi_change:+d})

【散戶指標】
小台散戶多空比: {retail_ratio:.2f}% (前日: {retail_ratio_prev:.2f}%)
微台散戶多空比: {xmtx_ratio:.2f}% (前日: {xmtx_ratio_prev:.2f}%)

【市場恐慌指標】
VIX指標: {vix:.2f} (前日: {vix_prev:.2f})
隱含波動率: {implied_volatility:.2f}%

【市場關鍵壓力支撐】
近週壓力: {weekly_resistance}
近週支撐: {weekly_support}
近月壓力: {monthly_resistance}
近月支撐: {monthly_support}

【技術分析】
短期趨勢: {short_term_trend}
中期趨勢: {medium_term_trend}
長期趨勢: {long_term_trend}
目前市場位置: {market_position}
預期目標區間: {target_range}

【資料來源】
{sources}
更新時間: {update_time}"""

# 報告類型與對應模板
REPORT_TYPES = {
    'futures': FUTURES_REPORT_TEMPLATE,
    'options': OPTIONS_REPORT_TEMPLATE, 
    'institutional': INSTITUTIONAL_REPORT_TEMPLATE,
    'retail': RETAIL_REPORT_TEMPLATE,
    'full': FULL_ANALYSIS_TEMPLATE
}

# 報告類型與關鍵字對應
REPORT_KEYWORDS = {
    'futures': ['期貨', '台指期', '小台', '微台'],
    'options': ['選擇權', '買權', '賣權', 'call', 'put', '選擇權籌碼', '壓力支撐'],
    'institutional': ['三大法人', '外資', '投信', '自營商', '法人'],
    'retail': ['散戶', '散戶籌碼', '散戶多空比'],
    'full': ['完整報告', '完整分析', '全部資料', '市場分析']
}
