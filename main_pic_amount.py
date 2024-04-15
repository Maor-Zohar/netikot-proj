from logic import *

if __name__ == "__main__":
    logic = Logic(ping_vs_capture='capture')

    logic.create_camera_array()

    logic.check_number_pictures_of_cameras()

