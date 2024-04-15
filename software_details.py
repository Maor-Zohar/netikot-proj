import os
import threading
import gspread
import pdb

from devices import DahuaDevice
from logic import Logic
import pygsheets

debug_event = threading.Event()


# Define a function to fetch software version and web version for a camera
def get_versions(camera, index, software_to_insert_nvr, model_to_insert_nvr, model_to_insert_cam,
                 software_to_insert_cam):
    try:
        if camera.company == "Dahua" and camera.type != 'כח':
            # check Dahua NVR
            if camera.nvr_status == "Work":
                dahua_device = camera.dahua_device(is_nvr=True)
                software_version = dahua_device.get_software_version()
                model = dahua_device.get_model()
                if software_version != DEFAULT_VALUE:
                    software_to_insert_nvr[index] = [software_version]
                if model != DEFAULT_VALUE:
                    model_to_insert_nvr[index] = [model]

            # check Dahua camera
            if camera.cam_status == "Work":
                dahua_device = camera.dahua_device(is_nvr=False)
                software_version = dahua_device.get_software_version()
                model = dahua_device.get_model()
                # print("----------------------------------------------------------------")
                # print("Camera ip: " + camera.ip + ":" + camera.cam_port + " " + camera.cam_pass + "\nmodel: " + model + "\nsoftware version: " + software_version)
                # print("----------------------------------------------------------------")
                if software_version != DEFAULT_VALUE:
                    software_to_insert_cam[index] = [software_version]
                if model != DEFAULT_VALUE:
                    model_to_insert_cam[index] = [model]

        elif camera.company == "Hikvision" and camera.type != 'כח':
            # check Hikvision NVR
            if camera.nvr_status == "Work":
                hikvision_device = camera.hikvision_device(is_nvr=True)
                firmware_version, model = hikvision_device.get_software_version()
                software_to_insert_nvr[index] = [firmware_version]
                model_to_insert_nvr[index] = [model]
            # check Hikvision Camera
            if camera.cam_status == "Work":
                hikvision_device = camera.hikvision_device(is_nvr=False)
                firmware_version, model = hikvision_device.get_software_version()
                model_to_insert_cam[index] = [model]
                software_to_insert_cam[index] = [firmware_version]

    except Exception as e:
        print(f"Error for camera {camera.to_string()}: {str(e)}")


if __name__ == "__main__":
    logic = Logic(ping_vs_capture='capture')
    path_win = "\\.config\\gspread\\netikot-373709-a9a49409184c.json"
    spreadsheet = "Netikot"
    worksheet_name = "cameras"
    logic.create_camera_array()
    cameras = logic.cameras
    DEFAULT_VALUE = "לא נמצאו פרטים", "לא נמצאו פרטים"
    connection = gspread.service_account(
        filename=os.getcwd() + path_win)
    sh = connection.open("Netikot")
    cs = sh.worksheet("cameras")

    # Create lists to store the software and web versions
    software_to_insert_nvr = [[""] for _ in range(len(cameras))]
    model_to_insert_nvr = [[""] for _ in range(len(cameras))]
    model_to_insert_cam = [[""] for _ in range(len(cameras))]
    software_to_insert_cam = [[""] for _ in range(len(cameras))]

    threads = []

    for index, camera in enumerate(cameras):
        thread = threading.Thread(target=get_versions, args=(
            camera, index, software_to_insert_nvr, model_to_insert_nvr, model_to_insert_cam,
            software_to_insert_cam))
        thread.start()
        threads.append(thread)

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    gc = pygsheets.authorize(service_file=os.getcwd() + path_win)

    # Update the values in one request
    cs.batch_update([
        {
            'range': f'AL2:AL',
            'values': software_to_insert_nvr,
        },
        {
            'range': f'AM2:AM',
            'values': model_to_insert_nvr,
        },
        {
            'range': f'AO2:AO',
            'values': model_to_insert_cam,
        },
        {
            'range': f'AN2:AN',
            'values': software_to_insert_cam,
        }
    ])

    # hik = HikvisionDevice(username="admin", password="942P185!#", port_camera="2081", ip="84.110.163.70", check_time="",
    #                       start_time="", port="2081")
    # hik.get_software_version()
