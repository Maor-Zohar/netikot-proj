from datetime import timedelta

import pytz

from camera import Camera
from devices import *
from logic import Logic
import logging
import cv2

# if __name__ == "__main__":
# now = datetime.now().strftime("%d.%m.%Y  %H-%M-%S")
# log_file = open(f"logs/Netikot log {now}.txt", encoding="utf8", mode="w+")
# log_file.write(f"Netikot Log {now}:")
# log_file.write("מצלמות עם תקינות גבוהה:")
# log_file.write("-----------------------------------------------")
# log_file.close()
# current_time = datetime.now(pytz.timezone('Israel')).strftime('%Y-%m-%dT%H:%M:%S')
# start = (datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S') - timedelta(hours=4)).strftime(
#     '%Y-%m-%dT%H:%M:%S')
logic = Logic(ping_vs_capture='capture')
logic.create_camera_array()

# capture = HikvisionDevice(ip='82.102.164.193', password='barak0555',check_time=current_time,start_time=start)
cameras = logic.cameras

# cameras[0].exe_time = 1
# cameras[1].exe_time = 2
# arr = [cameras[0], cameras[2], cameras[1]]
# arr_2 = sorted(arr,key=lambda x:x.exe_time,reverse=True)
# y=1
# for camera in cameras:
#     if camera.is_avira:
#         print(camera.site_name)
# array = [HikvisionDevice(ip='82.102.164.193', password='barak0555',check_time=current_time,start_time=start),
x = HikvisionDevice(ip='188.64.203.125', username='admin', password='942Mlli!#', check_time="2024-04-08T23:59:59Z",
                    start_time="2024-04-08T00:00:00Z", port=90).get_lpr(cam_id='1', last_capture_time="")
print(x)
# y = DahuaDevice(ip='46.210.119.171', port="2081", password='942Metz!#', check_time="", start_time="", prot="https").getLPR(cam_id="1",
#                                                                                                              last_capture_time='')

# cam = Camera(ip='95.35.29.223', username='live', nvr_pass='Hors@223', camera_number='1', nvr_status='Work',
#              validate_password_nvr='1', )
# x = DahuaDevice(ip='95.35.29.223', username='live', password='Hors@223',
#                     check_time=current_time, start_time=start, port=8080)
# logic.check_camera(cam)
# urld = "rtsp://live:Hors@001@80.250.156.1:554/cam/realmonitor?channel=1&subtype=0"
# urlh = "rtsp://admin:asela890!@95.35.55.11:554/Streaming/Channels/101/?transportmode=multicast"
# # url = 'rtsp://admin:panorama890!@46.210.100.115:554/Streaming/Channels/201/?transportmode=multicast'
# # Open the RTSP stream
# cap = cv2.VideoCapture(urlh)

# # Check if the stream was successfully opened
# if not cap.isOpened():
#     print("Error opening video stream")
# else:
#     print("Stream opened successfully")
#
# # Release the capture object and close any windows
# cap.release()
# cv2.destroyAllWindows()
#          HikvisionDevice(ip='85.159.161.114', password='phillil890',check_time=current_time,start_time=start),
#          HikvisionDevice(ip='85.159.162.191', password='focus890!',check_time=current_time,start_time=start),
#          HikvisionDevice(ip='109.253.4.96', password='yaniv318',check_time=current_time,start_time=start),
#          HikvisionDevice(ip='185.196.126.224', password='tapuhW890!',check_time=current_time,start_time=start),]
# for device in array:
#     device.get_lpr('','1')
