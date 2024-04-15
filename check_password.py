import threading


class PasswordCheckerThread(threading.Thread):
    def __init__(self, camera, column_range, wrong_passwords_list, http_bad_connections):
        threading.Thread.__init__(self)
        self.camera = camera
        self.column_range = column_range
        self.wrong_passwords_list = wrong_passwords_list
        self.http_bad_connections = http_bad_connections

    def run(self):
        try:
            if self.camera.cam_status == "Work":
                device_cam = self.camera.cast_to_device(is_nvr=False)
                if device_cam.check_validation_password():
                    self.wrong_passwords_list.append(self.camera.index)
                    self.camera.cam_status = "Wrong password"
            if self.camera.nvr_status == "Work":
                device_nvr = self.camera.cast_to_device(is_nvr=True)
                if device_nvr.check_validation_password():
                    self.wrong_passwords_list.append(self.camera.index)
                    self.camera.nvr_status = "Wrong password"
        except Exception as e:
            if self.camera.type != 'כח':
                if "HTTPConnectionPool" in str(e):
                    self.http_bad_connections.append(self.camera.index)


def process_cameras(cameras, column_range, wrong_passwords_list, http_bad_connections):
    threads = []
    for camera in cameras:
        if camera.company in ["Dahua", "Hikvision"]:
            thread = PasswordCheckerThread(camera, column_range, wrong_passwords_list, http_bad_connections)
            threads.append(thread)
            thread.start()

    for thread in threads:
        thread.join()
