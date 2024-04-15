import os
import threading
import time
from datetime import datetime, timedelta

import gspread

from devices import HikvisionDevice, DahuaDevice
from logic import Logic

DEFAULT_VALUE = "בעיית התחברות"
logic = Logic(ping_vs_capture='capture')

logic.create_camera_array()

path_win = "../.config/gspread/netikot-373709-a9a49409184c.json"
connection = gspread.service_account(
    filename=os.getcwd() + path_win)
sh = connection.open("Netikot")
cs = sh.worksheet("cameras")

cameras = logic.cameras


def get_camera_time(index, camera, array_times):
    try:
        if camera.company == "Hikvision":
            device = HikvisionDevice(ip=camera.ip, password=camera.nvr_pass, username="admin",
                                     port_camera=camera.cam_port, port=camera.nvr_port, start_time="",
                                     check_time="")
        elif camera.company == "Dahua":
            device = camera.dahua_device(is_nvr=True)

        else:
            return
        datetime_camera = device.get_current_datetime()
        time_camera = datetime_camera.strftime("%H:%M")
        date_camera = datetime_camera.strftime('%d-%m-%Y')
        if time_camera == '00:00': time_camera = DEFAULT_VALUE
        if current_datetime - interval <= datetime_camera <= current_datetime + interval:
            is_set_time[index] = ["כן"]
        array_times[index] = [time_camera]
        dates_array[index] = [date_camera]
    except:
        pass


while True:
    array_times = [[DEFAULT_VALUE] for _ in range(len(cameras))]
    dates_array = [["01-01-1900"] for _ in range(len(cameras))]
    is_set_time = [["לא"] for _ in range(len(cameras))]
    current_datetime = datetime.now()
    interval = timedelta(minutes=5)
    threads = []

    for index, camera in enumerate(cameras):
        if index < len(cameras) - 1:
            thread = threading.Thread(target=get_camera_time, args=(index, camera, array_times))
            threads.append(thread)
            thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()
    last_row = len(cameras) + 1
    cs.batch_update([
        {
            'range': f'AK2:AK{last_row}',
            'values': array_times,
        },
        {
            'range': f'AB2:AB{last_row}',
            'values': dates_array,
        },
        {
            'range': f'AC2:AC{last_row}',
            'values': is_set_time,
        }
    ])
    print('x')
    time.sleep(60)
