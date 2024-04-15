from datetime import timedelta
import gspread
import pytz
from urllib3 import HTTPConnectionPool
from urllib3.exceptions import ConnectTimeoutError

from camera import *
import time

from check_password import process_cameras
from devices import *
import cv2

NO_ACCESS_CAMERA = 'אין גישה למצלמה'


def new_line(log_file):
    log_file.write("\n")


def fix_local_time_array(local_time_array):
    for i, element in enumerate(local_time_array):
        if type(element[0]) is not str:
            local_time_array[i][0] = element[0].strftime("%Y-%m-%d %H:%M:%S")


def print_cameras_into_log_file(log_file, array):
    for camera in array:
        log_file.write(
            f"- {camera.hatmar} {camera.site_name} {camera.ip}:{camera.nvr_port} {camera.camera_number} {camera.nvr_pass} {camera.company} . Executing time is: {camera.exe_time} seconds.")
        new_line(log_file)


def _check_local_time(camera, device):
    camera.local_time_camera = device.get_current_datetime()
    now = datetime.now()
    time_diff = abs(now - camera.local_time_camera)
    camera.is_current_time = "כן" if (time_diff < timedelta(minutes=4)) else "לא"


class Logic:

    def __init__(self, ping_vs_capture):
        path_win = "\\.config\\gspread\\netikot-373709-a9a49409184c.json"
        path_mac = "/.config/gsprea" \
                   "d/netikot-373709-a9a49409184c.json"
        self.start_time = time.time()
        self.connection = gspread.service_account(
            filename=os.getcwd() + path_win)
        self.sh = self.connection.open("Netikot")
        self.cs = self.sh.worksheet("cameras")
        self.cells = self.cs.get_all_values()
        self.rows = len(self.cells)
        self.cameras = []
        self.time_diff = 4
        self.nvr_dict = {}
        self.count_cam_ping = 0
        self.count_nvr_ping = 0
        self.count_modem_ping = 0
        self.ping_vs_capture = ping_vs_capture
        self.captures = []
        self.connection_error = []
        self.is_camera_ping_done = False
        self.is_nvr_ping_done = False
        self.working_hik = 0
        self.working_dahua = 0
        self.count_hik = 0
        self.count_dahua = 0
        self.execution_time = ''
        self.incorrect_password = []

    def create_cam_df(self):
        data = [[self.cameras[index].cam_status] for index in range(self.rows - 1)]
        cam_df = pd.DataFrame(data, columns=['תקינות רשת'])
        self.cam_to_g_sheets(cam_df)

    def create_nvr_df(self):
        data = [[self.cameras[index].nvr_status] for index in range(self.rows - 1)]
        nvr_df = pd.DataFrame(data, columns=['תקינות nvr'])
        self.nvr_to_g_sheets(nvr_df)

    def captures_to_g_sheets(self):
        now = time.time()
        datetime_g_sheets = datetime.now().strftime("%d-%m-%Y , %H:%M")

        # Organize the data to Google Sheets required format
        data = [[self.captures[index].last_cap_time, self.captures[index].cap_amount, self.captures[index].is_captured]
                for index in range(self.rows - 1)]
        local_time_array = [[self.cameras[index].local_time_camera, self.cameras[index].is_current_time] for index in
                            range(self.rows - 1)]
        amount_pictures_array = [[self.cameras[index].count_pictures] for index in range(self.rows - 1)]
        fix_local_time_array(local_time_array)

        update_requests = self.build_batch_update_array(indexes=self.incorrect_password,
                                                        value_to_insert="Wrong Password")
        if len(self.connection_error) > 0:
            connection_indexes = self.build_batch_update_array(indexes=self.connection_error,
                                                               value_to_insert="Low Connection")
            for item in connection_indexes:
                update_requests.append(item)

        # Append captures data  - if existing, last time there was a capture, how many captures were
        update_requests.append({
            'range': f'N2:P{self.rows}',
            'values': data,
        })
        # Append the executing time of the script
        update_requests.append({
            'range': f'Y2:Y2',
            'values': [[datetime_g_sheets]],
        })
        # Append two data -  local time that configured at the camera, and  is the camera time synchronized
        update_requests.append({
            'range': f'AB2:AC{self.rows}',
            'values': local_time_array,
        })
        # Append the amount pictures that camera makes: 1,2 or cannot get this data
        update_requests.append({
            'range': f'AD2:AD',
            'values': amount_pictures_array,
        })

        self.cs.batch_update(update_requests)

        self.execution_time = str(now - self.start_time)
        print("--- %s seconds ---" % (now - self.start_time))

    def cam_to_g_sheets(self, df):
        rows = [[item] for item in df['תקינות רשת']]
        self.cs.batch_update([
            {
                'range': 'E2:E',
                'values': rows,
            },
        ])
        print("--- cam %s seconds ---" % (time.time() - self.start_time))
        self.is_camera_ping_done = True

    def nvr_to_g_sheets(self, df):
        rows = [[item] for item in df['תקינות nvr']]
        self.cs.batch_update([
            {
                'range': 'M2:M',
                'values': rows,
            },
        ])
        print("--- nvr %s seconds ---" % (time.time() - self.start_time))
        self.is_nvr_ping_done = True

    def build_batch_update_array(self, indexes, value_to_insert, column_range='M'):
        """
        Build a batch update array to insert a value into a specific column for the specified rows.

        :param indexes: List of row indexes where the value should be inserted.
        :param value_to_insert: The value to insert into the column.
        :param column_range: The column range (e.g., 'M' for column M).
        :return  List of update requests for batch updating.
        """
        update_requests = []
        for row_index in indexes:
            update_request = {
                'range': f'{column_range}{row_index}:{column_range}{row_index}',
                'values': [[value_to_insert]],
            }
            update_requests.append(update_request)
        return update_requests

    def create_camera_array(self):
        data = self.cells
        for row in range(1, self.rows):
            row_data = data[row]
            # self.count_dict[row_data[1]] = 1 + self.count_dict.get(row_data[1], 0)

            self.cameras.append(
                Camera(index=row + 1,
                       hatmar=row_data[0],
                       site_name=row_data[1],
                       ip=row_data[2],
                       cam_port=row_data[3],
                       cam_pass=row_data[9],
                       company=row_data[5],
                       nvr_port=row_data[10],
                       nvr_pass=row_data[11],
                       camera_number=row_data[17],
                       cam_status=row_data[4],  # if self.ping_vs_capture == 'Work' else row_data[4],
                       nvr_status=row_data[12],  # if self.ping_vs_capture == 'Work' else row_data[12],
                       validate_password_nvr=row_data[20],
                       is_four_hours_captures=row_data[15],
                       is_avira=True if row_data[21] == 'אווירה' else False,
                       count_pictures=row_data[27],
                       type=row_data[22],
                       prot="https" if row_data[33] == '1' else "http"
                       ))
            if self.ping_vs_capture == 'capture':
                self.captures.append(
                    Capture(
                        last_cap_time=row_data[13],
                        cap_amount=row_data[14],
                        is_captured=row_data[15],
                    )
                )

                # if self.ping_vs_capture == 'ping':
            self.nvr_dict[self.cameras[row - 1].ip] = self.cameras[row - 1].nvr_port

    def ping_all_cameras(self):
        threads = []

        for row in range(self.rows - 1):
            try:
                thread = threading.Thread(target=self.ping, args=[self.cameras[row], 'camera'])
                threads.append(thread)
                thread.start()
            except:
                print("ping_all_cameras error")

        # Wait for all threads to finish
        for thread in threads:
            if thread is not None:
                thread.join()

    def ping_all_nvrs(self):
        threads = []

        for ip in self.nvr_dict:
            try:
                all_indexes = self.find_cam(ip)
                thread = self.thread_ping(self.cameras[all_indexes[0]], 'nvr', indexes=all_indexes)
                threads.append(thread)
            except:
                print("ping_all_nvrs error")

        # Wait for all threads to finish
        for thread in threads:
            if thread is not None:
                thread.join()

    def find_cam(self, ip):
        res = []
        for cam in self.cameras:
            if cam.ip == ip:
                res.append(cam.index - 2)
        return res

    def thread_ping(self, camera, camera_vs_nvr_vs_modem, indexes=[]):
        t_ping = threading.Thread(target=self.ping, args=[camera, camera_vs_nvr_vs_modem, indexes])
        t_ping.start()

    def get_ping_url(self, ip, port, prot, timeout):
        if prot == "https":
            return requests.get(f"https://{ip}:{port}", timeout=timeout, verify=False)
        return requests.get(f"http://{ip}:{port}", timeout=timeout, verify=True)

    def ping(self, camera, camera_vs_nvr_vs_modem, indexes=[]):
        try:
            timeout_ping = 30
            match camera_vs_nvr_vs_modem:
                case 'camera':
                    response = self.get_ping_url(camera.ip, camera.cam_port, camera.prot, timeout_ping)
                case 'nvr':
                    response = self.get_ping_url(camera.ip, camera.nvr_port, camera.prot, timeout_ping)

            if response.status_code == 200:
                match camera_vs_nvr_vs_modem:
                    case 'camera':
                        self.cameras[camera.index - 2].cam_status = 'Work'
                    case 'nvr':
                        self.update_nvr_stat(indexes, 'Work')
                    case 'modem':
                        self.cameras[camera.index - 2].modem_status = 'Work'
            else:
                match camera_vs_nvr_vs_modem:
                    case 'camera':
                        self.cameras[camera.index - 2].cam_status = 'Error code'
                    case 'nvr':
                        self.update_nvr_stat(indexes, 'Error code')
                    case 'modem':
                        self.cameras[camera.index - 2].modem_status = 'Error code'

        except Exception as e:
            # camera.cam_status = 'Bad Request'
            match camera_vs_nvr_vs_modem:
                case 'camera':
                    self.cameras[camera.index - 2].cam_status = 'Bad Request'
                case 'nvr':
                    self.update_nvr_stat(indexes, 'Bad Request')
                case 'modem':
                    self.cameras[camera.index - 2].modem_status = 'Bad Request'

        finally:
            match camera_vs_nvr_vs_modem:
                case 'camera':
                    self.count_cam_ping += 1
                    if self.count_cam_ping == self.rows - 1:
                        self.create_cam_df()
                case 'nvr':
                    self.count_nvr_ping += 1
                    if self.count_nvr_ping == len(self.nvr_dict):
                        self.create_nvr_df()
                # case 'modem':
                # self.count_modem_ping += 1
                # if self.count_modem_ping == self.rows - 1:
                #     self.create_cam_df()

    def update_nvr_stat(self, indexes, status):
        for index in indexes:
            self.cameras[index].nvr_status = status

    def capture_all(self):
        current_time = datetime.now(pytz.timezone('Israel')).strftime('%Y-%m-%dT%H:%M:%S')
        print("Starting time checking: " + current_time)
        start = (datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S') - timedelta(hours=self.time_diff)).strftime(
            '%Y-%m-%dT%H:%M:%S')
        self.print_description_before()
        threads = []

        for row in range(self.rows - 1):
            t_cap = threading.Thread(target=self.last_capture, args=[start, current_time, self.cameras[row]])
            threads.append(t_cap)
            t_cap.start()

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        print("finish doing the threads")
        self.captures_to_g_sheets()
        # self.create_log_file()
        print(f"Hikvision: {str(self.count_hik)}/{str(self.working_hik)}")
        print(f"Dahua: {str(self.count_dahua)}/{str(self.working_dahua)}")

    def print_description_before(self):
        bad_cam_amount = 0
        bad_nvr_amount = 0
        bad_both_amount = 0
        bad_nvr_pass_amount = 0
        for cam in self.cameras:
            if cam.nvr_status == 'Bad Request' and cam.cam_status == 'Work':
                bad_nvr_amount += 1
            elif cam.nvr_status == 'Work' and cam.cam_status == 'Bad Request':
                bad_cam_amount += 1
            elif cam.nvr_status == 'Bad Request' and cam.cam_status == 'Bad Request':
                bad_both_amount += 1
            if cam.validate_password_nvr == '0':
                bad_nvr_pass_amount += 1
        print(f'Bad cameras amount is: {bad_cam_amount}.')
        print(f'Bad nvr amount is: {bad_nvr_amount}.')
        print(f'Bad cameras and nvr amount is: {bad_both_amount}.')
        print(f'Bad nvr password amount is: {bad_nvr_pass_amount}.')
        print('----------------------------------------------------------------')
        total = bad_cam_amount + bad_both_amount + bad_nvr_amount + bad_nvr_pass_amount
        print(f'Total failures cameras  is: {total}.')
        print(f'Total working cameras is: {self.rows - total}.')
        print('----------------------------------------------------------------')

    def thread_capture(self, start, current_time, camera):
        t_cap = threading.Thread(target=self.last_capture, args=[start, current_time, camera])
        t_cap.start()

    def last_capture(self, start, current_time, camera):

        try:
            if camera.company == 'Hikvision' and int(camera.camera_number) > 0 \
                    and camera.nvr_status == 'Work' and camera.validate_password_nvr == '1':
                self.count_hik += 1
                print(
                    "Checking site: " + camera.site_name + ", in ip and port: " + camera.get_ip_and_port() + " ." + camera.cam_status + camera.nvr_status)
                hikvision_device = HikvisionDevice(ip=camera.ip, port=int(camera.nvr_port),
                                                   password=camera.nvr_pass,
                                                   start_time=start, check_time=current_time,
                                                   auto_login=True, verbose=False,
                                                   port_camera=int(camera.cam_port))
                if not hikvision_device.flags["password"]:
                    self.incorrect_password.append(camera.index)
                    return

                _check_local_time(camera=camera, device=hikvision_device)
                if not camera.is_avira:
                    capture_hikvision, amount_pictures = hikvision_device.get_lpr(
                        last_capture_time=self.captures[camera.index - 2].last_cap_time,
                        cam_id=camera.camera_number)
                    camera.count_pictures = amount_pictures
                    if capture_hikvision.is_captured == '404':
                        camera.insert_status_to_camera(is_capture='404')
                        print(f"Error {camera.to_string()}")
                    else:
                        capture_hikvision.last_cap_time = capture_hikvision.last_cap_time.replace("T", " ").replace("Z",
                                                                                                                    " ")
                        self.captures[camera.index - 2] = capture_hikvision
                        last_capture_hikvision = capture_hikvision.last_cap_time[11:19]
                        if len(last_capture_hikvision) > 0: self.working_hik += 1
                        print(
                            camera.hatmar + ", ip: " + camera.get_ip_and_port() + ", cap: " + last_capture_hikvision + " hikvision")
                        camera.insert_status_to_camera(is_capture=capture_hikvision.is_captured)
            elif camera.company == 'Dahua' and int(camera.camera_number) > 0 \
                    and camera.nvr_status == 'Work':
                dahua_device = DahuaDevice(ip=camera.ip, port=int(camera.nvr_port), password=camera.nvr_pass,
                                           verbose=False, check_time=current_time.replace('T', ' '),
                                           start_time=start.replace('T', ' '),
                                           auto_login=True)
                _check_local_time(camera=camera, device=dahua_device)
                if not camera.is_avira:
                    capture_dahua = dahua_device.getLPR(cam_id=int(camera.camera_number),
                                                        last_capture_time=self.captures[
                                                            camera.index - 2].last_cap_time)
                    self.count_dahua += 1
                    if camera.count_pictures == '2':
                        capture_dahua.cap_amount = str(int(capture_dahua.cap_amount) // 2)
                    self.captures[camera.index - 2] = capture_dahua
                    last_capture = capture_dahua.last_cap_time[11:19]
                    if len(last_capture) > 0: self.working_dahua += 1
                    print(
                        camera.hatmar + ", ip: " + camera.get_ip_and_port() + ", cap: " + last_capture + " dahua")
                    camera.insert_status_to_camera(capture_dahua.is_captured)
            elif camera.nvr_status == 'Bad Request' and camera.is_four_hours_captures == 'כן' and camera.is_four_hours_captures == 'כן':
                self.captures[camera.index - 2] = Capture(last_cap_time=self.captures[
                    camera.index - 2].last_cap_time, cap_amount='0', is_captured='לא')
        except Exception as e:
            if "HTTPConnectionPool" in str(e):
                self.connection_error.append(camera.index)
            camera.insert_status_to_camera(is_capture=f"${e}, ${camera.to_string()}")
            print(e, camera.to_string())

        else:
            pass
        camera.exe_time = time.thread_time_ns() / 1e9

    def create_log_file(self):
        work = sorted([el for el in self.cameras if el.overall_status_priority == 1], key=lambda x: x.exe_time,
                      reverse=True)
        medium = sorted([el for el in self.cameras if el.overall_status_priority == 2], key=lambda x: x.exe_time,
                        reverse=True)
        bad = sorted([el for el in self.cameras if el.overall_status_priority == 3], key=lambda x: x.exe_time,
                     reverse=True)
        port = sorted([el for el in self.cameras if el.overall_status_priority == 4], key=lambda x: x.exe_time,
                      reverse=True)
        missing_model = sorted([el for el in self.cameras if el.overall_status_priority == 5], key=lambda x: x.exe_time,
                               reverse=True)
        timeout = sorted([el for el in self.cameras if el.overall_status_priority == 6], key=lambda x: x.exe_time,
                         reverse=True)
        now = datetime.now().strftime("%d.%m.%Y  %H-%M-%S")
        self.custom_sort()
        log_file = open(f"logs/Netikot log {now}.txt", "w+")
        log_file.write(f"Netikot Log {now}:")

        log_file.write("מצלמות עם תקינות גבוהה:")
        new_line(log_file)
        print_cameras_into_log_file(log_file, work)
        log_file.write(f" כמות המצלמות בעלות תקינות גבוהה ")
        new_line(log_file)
        log_file.write("----------------------------------------------")
        new_line(log_file)
        log_file.write("מצלמות עם תקינות בינונית:")
        new_line(log_file)
        log_file.write("")
        new_line(log_file)
        log_file.write("-----------------------------------------------")
        log_file.write("מצלמות עם תקינות נמוכה:")
        new_line(log_file)
        print_cameras_into_log_file(log_file, medium)
        log_file.write("")
        new_line(log_file)
        log_file.write("-----------------------------------------------")
        new_line(log_file)
        print_cameras_into_log_file(log_file, bad)
        log_file.write("מצלמות שנדרשות לקינפוג פורט:")
        new_line(log_file)
        log_file.write("-----------------------------------------------")
        new_line(log_file)
        print_cameras_into_log_file(log_file, port)
        log_file.write("מצלמות שיש להם בעיה בהתחברות:")
        new_line(log_file)
        log_file.write("-----------------------------------------------")
        new_line(log_file)
        print_cameras_into_log_file(log_file, missing_model)
        log_file.write("-----------------------------------------------")
        new_line(log_file)
        log_file.write(f"מצלמות שלא מגיבות לבקשות:")
        new_line(log_file)
        print_cameras_into_log_file(log_file, timeout)
        log_file.write("-----------------------------------------------")
        new_line(log_file)
        log_file.write(f"זמן ריצה של התוכנית היא: {self.execution_time} seconds")
        log_file.close()

    def custom_sort(self):
        for i in range(0, len(self.cameras) - 1):
            for j in range(len(self.cameras) - 1):
                if self.cameras[j].overall_status_priority > self.cameras[j + 1].overall_status_priority:
                    temp = self.cameras[j]
                    self.cameras[j] = self.cameras[j + 1]
                    self.cameras[j + 1] = temp

    def check_camera(self, camera):
        try:
            # if int(camera.camera_number) > 0 and camera.nvr_status == 'Work' and camera.validate_password_nvr == '1' and (
            #         camera.type == 'כחול חשאי' or camera.type == 'אווירה'):
                if camera.company == 'Dahua':
                    url = f"rtsp://{camera.username}:{camera.cam_pass}@{camera.ip}:8080/cam/realmonitor?channel=1&subtype=0"
                elif camera.company == 'Hikvision':
                    url = f"rtsp://{camera.username}:{camera.nvr_pass}@{camera.ip}:554/Streaming/Channels/{camera.camera_number}01" \
                          f"/?transportmode=multicast"
                else:
                    url = ''
                    camera.check_live_view = 'X'
                # Open the RTSP stream
                cap = cv2.VideoCapture(url)

                # Check if the stream was successfully opened
                if not cap.isOpened():
                    print(f"Error opening video stream of {camera.ip}")
                    camera.check_live_view = 'X'
                else:
                    print(f"Stream opened successfully of {camera.ip}")
                    camera.check_live_view = 'V'

                # Release the capture object and close any windows
                cap.release()
                cv2.destroyAllWindows()
                print(camera.check_live_view)
        except Exception as e:
            camera.check_live_view = 'X'
            print(f"{e}")

    def checker_live_view_cameras(self):

        # Get the current time and format it
        start_time = datetime.now(pytz.timezone('Israel'))
        print(f"Starting time checking: {start_time.strftime('%Y-%m-%dT%H:%M:%S')}")

        current_time = datetime.now(pytz.timezone('Israel')).strftime('%Y-%m-%dT%H:%M:%S')
        start = (datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S') - timedelta(hours=self.time_diff)).strftime(
            '%Y-%m-%dT%H:%M:%S')

        # Create a list of threads
        threads = []

        for camera in self.cameras:
            # Create a new thread for each camera object
            t = threading.Thread(target=self.check_camera, args=(camera,))
            threads.append(t)
            t.start()
            self.check_camera(camera)

        # Wait for all threads to complete
        for t in threads:
            t.join()

        self.live_view_to_g_sheets()

        # Print the time when the function finishes
        end_time = datetime.now(pytz.timezone('Israel'))
        print(f"Finished time checking: {end_time.strftime('%Y-%m-%dT%H:%M:%S')}")
        print(f"Total time elapsed: {end_time - start_time}")

    def live_view_to_g_sheets(self):
        live_view_array = [[self.cameras[index].check_live_view] for index in range(self.rows - 1)]
        self.cs.batch_update([
            {
                'range': f'AG2:AG',
                'values': live_view_array,
            }
        ])

    def check_number_pictures_of_cameras(self):
        while True:
            # Get the current time and format it
            start_time = datetime.now(pytz.timezone('Israel'))
            print(f"Starting time checking: {start_time.strftime('%Y-%m-%dT%H:%M:%S')}")

            # Calculate the start time based on the time difference
            start = (start_time - timedelta(hours=self.time_diff)).strftime('%Y-%m-%dT%H:%M:%S')

            # Create a list to store the threads
            threads = []

            # Loop through each camera and create a thread to process it
            for camera in self.cameras:
                t = threading.Thread(target=self.process_camera, args=(camera, start, start_time))
                threads.append(t)
                t.start()

            # Wait for all threads to finish
            for t in threads:
                t.join()

            # Update the Google Sheets document with the new picture counts
            self.amount_pictures_to_g_sheets()

            # Print the time when the function finishes
            end_time = datetime.now(pytz.timezone('Israel'))
            print(f"Finished time checking: {end_time.strftime('%Y-%m-%dT%H:%M:%S')}")
            print(f"Total time elapsed: {end_time - start_time}")
            time.sleep(900)  # Sleeps for 15 minutes

    def process_camera(self, camera, start, start_time):
        # If the camera is a Hikvision camera and has a valid configuration
        if camera.company == 'Hikvision' and int(camera.camera_number) > 0 \
                and camera.nvr_status == 'Work' and camera.validate_password_nvr == '1':

            # Create a new HikvisionDevice object to communicate with the camera
            hikvision_device = HikvisionDevice(
                ip=camera.ip,
                port=int(camera.nvr_port),
                password=camera.nvr_pass,
                start_time=start,
                check_time=start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                auto_login=True,
                verbose=False,
                port_camera=int(camera.cam_port)
            )

            try:
                # Get the new picture count for the camera
                camera.count_pictures = hikvision_device.check_amount_pictures(
                    cam_id=camera.camera_number,
                    previous_pic_amount=camera.count_pictures
                )
            except Exception as e:
                print(f"Error getting picture count for camera {camera.ip}: {e}")
                camera.count_pictures = NO_ACCESS_CAMERA

        # If the camera is not a Hikvision camera, or has an invalid configuration
        elif camera.company == 'Hikvision':
            camera.count_pictures = NO_ACCESS_CAMERA
            print(f"Failed to get access to camera: {camera.ip}")

        # Print the new picture count for the camera
        print(f"Camera {camera.ip}: {camera.count_pictures}")

    def amount_pictures_to_g_sheets(self):
        amount_pictures_array = [[self.cameras[index].count_pictures] for index in range(self.rows - 1)]
        self.cs.batch_update([
            {
                'range': f'AD2:AD',
                'values': amount_pictures_array,
            }
        ])

    def                                                                   check_password(self):
        DEFAULT_VALUE = "לא נמצאו פרטים", "לא נמצאו פרטים"

        wrong_passwords_cam = []
        wrong_passwords_nvr = []
        http_bad_connections_cam = []
        process_cameras(self.cameras, 'E', wrong_passwords_cam, http_bad_connections_cam)
        process_cameras(self.cameras, 'M', wrong_passwords_nvr, http_bad_connections_cam)

        arr_cam_wrong_pass = self.build_batch_update_array(indexes=wrong_passwords_cam,
                                                           value_to_insert="Wrong password",
                                                           column_range='E')
        arr_nvr_wrong_pass = self.build_batch_update_array(indexes=wrong_passwords_nvr,
                                                           value_to_insert="Wrong password",
                                                           column_range='M')
        arr_bad_http_connections_cam = self.build_batch_update_array(indexes=wrong_passwords_cam,
                                                                     value_to_insert="Low Connection",
                                                                     column_range='E')
        arr_bad_http_connections_nvr = self.build_batch_update_array(indexes=wrong_passwords_cam,
                                                                     value_to_insert="Low Connection",
                                                                     column_range='M')
        self.cs.batch_update(arr_nvr_wrong_pass)
        self.cs.batch_update(arr_cam_wrong_pass)
        self.cs.batch_update(arr_bad_http_connections_cam)
        self.cs.batch_update(arr_bad_http_connections_nvr)
        print("Wrong passwords have been inserted.")
