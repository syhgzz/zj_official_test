from datetime import datetime

loc_list = {
    '重庆':[105.782, 108.345, 28.999, 30.147], # 重庆
    '北京':[115.814, 116.816, 39.637, 40.423], # 北京
    '唐山':[117.903, 118.825, 39.185, 40.131], # 唐山
    '天津':[116.919, 117.831, 38.695, 39.525], # 天津
}

minLng_global, maxLng_global, minLat_global, maxLat_global = loc_list['重庆']
startTime_global = int(datetime(2025,1,1,0,0,0).timestamp()) * 1000    
endTime_global = int(datetime(2025,12,31,23,59,59).timestamp()) * 1000

# 