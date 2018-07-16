import re
import numpy as np
import matplotlib.pyplot as plt
import sys
import glob
import os.path
import json

list_month = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
max_temperature = 50 #描画する温度範囲の上限（℃）下限は0℃。凍る場合、式が大幅に変化する
max_abs_moist = 30 #描画する重量絶対湿度範囲の上限（g/kg）

"""
緯度、経度の値を GeoJSON 互換に変換
"""
re_dmformat = re.compile("(\d+)d\s*(\d+)m\s*(\w)$")
def conv_latlong(_dmformat):
    if re_dmformat.search(_dmformat):
        _val = float(re_dmformat.search(_dmformat).group(1))+float(re_dmformat.search(_dmformat).group(2))/60
        if re_dmformat.search(_dmformat).group(3) == "S" or re_dmformat.search(_dmformat).group(3) == "W":
            _val = _val * -1
        return round(_val,2)
    else:
        log_error("latlong: "+_dmformat)
        raise ValueError

"""
atdd.noaa.gov のデータから必要なデータを抜き出し、月ごとのデータとしてJSON化する
"""
# :  Dry Bulb Temperature
re_drybulbtemp_title = re.compile(":\s+Dry Bulb Temperature")
# :  Relative Humidity
re_relhum_title = re.compile(":\s+Relative Humidity")
#   Element 14:  Vapor Pressure (hPa)
re_vaporp_title = re.compile(":\s+Vapor Pressure")
#    Jan         2.5      14
re_permonth = re.compile("(\w{3})\s+([\d\.\-]+)")
# head
re_head = re.compile("^([^:]+)\:(.*)$")

def get_data(_path):
    with open(_path) as f:
        contents = f.read()
    _dict_of_month = {}
    _metadata = {}
    for month in list_month:
        _dict_of_month[month] = {}
    current_type = "head"
    for l in contents.splitlines():
        if current_type == "head":
            if re_head.match(l):
                _metadata[re_head.match(l).group(1).strip()] = re_head.match(l).group(2).strip()
            else:
                current_type = ""
        elif current_type != "":
            if re_permonth.search(l): #合計欄などこれに当てはまらない部分はたくさんある
                if re_permonth.search(l).group(1) in list_month:
                    _dict_of_month[re_permonth.search(l).group(1)][current_type] = float(re_permonth.search(l).group(2))
                if re_permonth.search(l).group(1) == "Dec":
                    current_type = ""
        else:
            if re_drybulbtemp_title.search(l):
                current_type = "drybulbtemp"
            if re_relhum_title.search(l):
                current_type = "relhum"
            if re_vaporp_title.search(l):
                current_type = "vaporp"
    _metadata["Latitude"] = conv_latlong(_metadata["Latitude"])
    _metadata["Longitude"] = conv_latlong(_metadata["Longitude"])
    return _dict_of_month, _metadata

"""
温度と相対湿度から、重量絶対湿度を算出
max_vapor_pressure : 乾球温度から算出した飽和水蒸気圧
abs_moist_max : 飽和水蒸気圧から算出した飽和重量絶対湿度（g/kg）
出力 : それに相対湿度を掛けたもの
"""
def abs_moist_relhum(_t, _relhum):
    max_vapor_pressure = 6.1078*np.power(10,(7.5*(_t))/(237.3+(_t)))
    abs_moist_max = 622*max_vapor_pressure/(1013.25-max_vapor_pressure)
    return abs_moist_max * _relhum / 100

"""
蒸気圧から、重量絶対湿度を算出
"""
def abs_moist_vaporp(_vaporp):
    return 622*_vaporp/(1013.25-_vaporp)

"""
湿り空気図の描画
等相対湿度線と等湿球温度線を描画
飽和（相対湿度=1) 以上の重量絶対湿度領域を灰色で塗りつぶし
"""
def draw_bg(_plt):
    x_values = np.arange(0, max_temperature+1, 1)
    vapor_pressure = 6.1078*np.power(10,(7.5*(x_values))/(237.3+(x_values)))
    abs_moist_max = 622*vapor_pressure/(1013.25-vapor_pressure)

    _plt.plot(x_values, abs_moist_max*1.0, "-", color="black", linewidth=1)
    for i in range(1,10):
        _plt.plot(x_values, abs_moist_max*i/10, "-", color="black", linewidth=0.3)
    for i in range(0,max_temperature,5):
        _plt.plot(np.arange(i, max_temperature+1, 1),-(np.arange(i, max_temperature+1, 1)-i)/((2501-1.805*24) / 1000)+abs_moist_max[i], "-", color="black", linewidth=0.3)
    _plt.fill_between(x_values,abs_moist_max,max_abs_moist,facecolor='grey')

"""
得られたデータを元にクライモグラフを描画
"""
def draw_climograph(_dict_of_month):
    for i, thismonth in enumerate(list_month):
        if i==len(list_month)-1:
            nextmonth = "Jan"
        else:
            nextmonth = list_month[i+1]
        if "drybulbtemp" not in _dict_of_month[thismonth]:
            raise ValueError("Dry Bulb Temperature missing.")
        if "relhum" in _dict_of_month[thismonth]:
            plt.plot([_dict_of_month[thismonth]["drybulbtemp"], _dict_of_month[nextmonth]["drybulbtemp"]], [abs_moist_relhum(_dict_of_month[thismonth]["drybulbtemp"],_dict_of_month[thismonth]["relhum"]), abs_moist_relhum(_dict_of_month[nextmonth]["drybulbtemp"],_dict_of_month[nextmonth]["relhum"])], '-', color="green", linewidth=2)
        elif "vaporp" in _dict_of_month[thismonth]:
            plt.plot([_dict_of_month[thismonth]["drybulbtemp"], _dict_of_month[nextmonth]["drybulbtemp"]], [abs_moist_vaporp(_dict_of_month[thismonth]["vaporp"]), abs_moist_vaporp(_dict_of_month[nextmonth]["vaporp"])], '-', color="green", linewidth=2)
        else:
            raise ValueError("Moisture clue missing.")

def log_error(_any):
    with open("error.log","a",encoding="utf8") as f:
        f.write(str(_any)+"\n")

def main(_path):
    dict_of_month, metadata = get_data(_path)
    print(metadata)
    print(dict_of_month)
    fjson = open(_path[:-4]+".json","w")
    json.dump(dict_of_month, fjson)

    draw_bg(plt)
    draw_climograph(dict_of_month)

    plt.xlim(0, max_temperature)
    plt.ylim(0, max_abs_moist)
    plt.xlabel("Dry Bulb Temperature (℃)")
    plt.ylabel("Absolute Humidity (g/kg)")
    plt.tick_params(axis='y', which='both', labelleft='off', labelright='on')
    plt.grid()
    # plt.show()
    plt.savefig(_path[:-4]+".png")
    plt.clf()

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        if os.path.isdir(sys.argv[1]):
            for txt in glob.glob(sys.argv[1]+"/**/*.TXT",recursive=True):
                try:
                    main(txt)
                except Exception as e:
                    log_error(txt)
                    log_error(e)
                    pass # not raise
        elif os.path.isfile(sys.argv[1]):
            main(sys.argv[1]) #e.g. "./data/42027.TXT"
        else:
            raise ValueError("Argument should be directory path or file path.")
    else:
        raise ValueError("Gimme data path!")
