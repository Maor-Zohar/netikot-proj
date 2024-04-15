from datetime import timedelta

import pytz

from camera import Camera
from check_password import PasswordCheckerThread
from devices import *
from logic import Logic
import logging
import cv2

logic = Logic(ping_vs_capture='capture')
logic.create_camera_array()

cameras = logic.cameras
# device = cameras[4].dahua_device(is_nvr=False)
# software = device.get_software_version()
indexes_cam__wrong_password = []

for camera in cameras:
    if camera.ip == '46.210.119.171':
        hikvision_device = DahuaDevice(ip=camera.ip, port=int(camera.nvr_port),
                                           password=camera.nvr_pass,
                                           start_time='2023-12-17T00:00:00Z', check_time='2023-12-17T23:59:59Z',
                                           auto_login=True, verbose=False,
                                          prot=camera.prot)
        capture_hikvision, amount_pictures = hikvision_device.getLPR(
            last_capture_time='',
            cam_id=camera.camera_number)



