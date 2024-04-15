from logic import *

if __name__ == "__main__":
    logic = Logic(ping_vs_capture='capture')

    logic.create_camera_array()
    logic.ping_all_cameras()
    logic.ping_all_nvrs()
    while True:
        if logic.is_camera_ping_done and logic.is_nvr_ping_done:
            logic.check_password()
            break
    while True:
        if logic.is_camera_ping_done and logic.is_nvr_ping_done:
            logic.capture_all()
            break

