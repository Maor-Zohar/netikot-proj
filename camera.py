import base64
from base64 import b64encode
from datetime import datetime
import threading

import pandas as pd
import requests
import xmltodict
from requests.auth import HTTPBasicAuth

from devices import HikvisionDevice, DahuaDevice


class Camera:
    def __init__(self, index, hatmar, site_name, ip, cam_port, cam_pass, nvr_port, nvr_pass,
                 camera_number, cam_status, nvr_status, company, validate_password_nvr,
                 is_four_hours_captures, is_avira, overall_status="נמוכה", overall_status_priority=3, exe_time=0.0,
                 is_current_time='לא', local_time_camera=f'{datetime(year=1900, month=1, day=1)}', count_pictures="",
                 check_live_view=False, username='admin', type='', prot="http"):
        self.index = index
        self.hatmar = hatmar
        self.site_name = site_name
        self.ip = ip
        self.cam_port = cam_port
        self.cam_pass = cam_pass
        self.nvr_port = nvr_port
        self.nvr_pass = nvr_pass

        self.camera_number = camera_number
        self.cam_status = cam_status
        self.nvr_status = nvr_status
        self.company = company
        self.validate_password_nvr = validate_password_nvr
        self.is_four_hours_captures = is_four_hours_captures
        self.is_avira = is_avira
        self.overall_status = overall_status
        self.overall_status_priority = overall_status_priority
        self.exe_time = exe_time
        self.is_current_time = is_current_time
        self.local_time_camera = local_time_camera
        self.count_pictures = count_pictures
        self.check_live_view = check_live_view
        self.username = username
        self.type = type
        self.prot = prot

    def get_ip_and_port(self):
        return self.ip + ':' + self.cam_port

    def get_data(self, is_one_camera, start, end, number_of_results):
        payload = f"<DataOperation><operationType>search</operationType><searchCond><searchID>CA1BB10B-B920-0001-B243-4171169016F7</searchID><timeSpanList><timeSpan><startTime>" \
                  f"{start}Z</startTime><endTime>{end}Z</endTime></timeSpan></timeSpanList><criteria><dataType>0</dataType><violationType>0</violationType>" \
                  f"{f'<channel>{self.camera_number}' if is_one_camera else ''}<channel/>" \
                  f"<direction/><plate/><speedMin/><speedMax/><vehicleType/><vehicleColor/><laneNo/><surveilType>0</surveilType><romoteHost/><sendFlag/></criteria>" \
                  f"<searchResultPosition>{number_of_results}</searchResultPosition><maxResults>100</maxResults></searchCond></DataOperation>"
        return payload

    def get_headers(self, url):
        headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "accept": "*/*",
            "if-modified-since": "0",
            "x-requested-with": "XMLHttpRequest",
            "referer": url,
            "accept-language": "en-US,en-IL;q=0.8,en;q=0.5,he;q=0.3",
            "accept-encoding": "gzip, deflate",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
            "proxy-connection": "Keep-Alive",
            "pragma": "no-cache",
            # check what to do with this data types
            # "Authorization": f"Basic {base64.b64encode(f'admin:{self.modem_password}'.encode('utf-8'))}"
            "Authorization": base64.b64encode(f"Basic {f'admin:{self.modem_password}'}".encode('utf-8'))

            # "Authorization": "Basic "+("%s:%s" % ("admin", self.modem_password)).encode("base64")
            # "Authorization": "Basic "+("%s:%s" % (base64.b64encode(bytes((f'admin {self.modem_password}'), 'utf-8'))))
        }
        return headers

    def capture(self, cs, camera, is_one_camera, start, end, last_cap_time_column, cap_amount_column,
                is_captured_column):
        # try:

        response = requests.post(url=f'http://{self.get_ip_and_port()}/ISAPI/Traffic/ContentMgmt/dataOperation',
                                 headers=self.get_headers(url=f'http://{self.get_ip_and_port()}/doc/page/traffic.asp'),
                                 data=self.get_data(is_one_camera, start, end, 0))
        xml1 = xmltodict.parse(response.content)
        print("hello: ", xml1)

    # def to_string(self):
    #     return f'index: {self.index}, ' \
    #            f'hatmar: {self.hatmar}, ' \
    #            f'site_name: {self.site_name}, ' \
    #            f'ip: {self.ip}, ' \
    #            f'cam_port: {self.cam_port}, ' \
    #            f'cam_pass: {self.cam_pass}, ' \
    #            f'nvr_port: {self.nvr_port}, ' \
    #            f'nvr_pass: {self.nvr_pass}, ' \
    #            f'camera_number: {self.camera_number}, ' \
    #            f'company: {self.company}, ' \
    #            f'cam_status: {self.cam_status}, ' \
    #            f'nvr_status:  {self.nvr_status}, '

    def define_overall_status_priority(self):
        match self.overall_status:
            case "גבוהה":
                self.overall_status_priority = 1
            case "בינונית":
                self.overall_status_priority = 2
            case "נמוכה":
                self.overall_status_priority = 3
            case "קינפוג פורט":
                self.overall_status_priority = 4
            case "לא נמצא מודל":
                self.overall_status_priority = 5
            case _:
                self.overall_status_priority = 6

    def insert_status_to_camera(self, is_capture):
        if not self.is_avira:
            match is_capture:
                case "כן":
                    if self.cam_status == "Work":
                        self.overall_status = "גבוהה"
                    else:
                        self.overall_status = "קינפוג פורט"
                case "לא":
                    if not self.cam_status == "Work":
                        self.overall_status = "נמוכה"
                    else:
                        self.overall_status = "בינונית"
                case "404":
                    self.overall_status = "לא נמצא מודל"
                case _:
                    self.overall_status = is_capture

        else:
            if self.cam_status == "Work":
                if self.nvr_status == "Work":
                    self.overall_status = "גבוהה"
                else:
                    self.overall_status = "בינונית"
            else:
                self.overall_status = "נמוכה"
        self.define_overall_status_priority()

    def hikvision_device(self, is_nvr):
        return HikvisionDevice(ip=self.ip, password=self.nvr_pass if is_nvr else self.cam_pass, username="admin",
                               port_camera=self.cam_port, port=self.nvr_port if is_nvr else self.cam_port,
                               start_time="",
                               check_time="", verbose=False)

    def dahua_device(self, is_nvr):
        return DahuaDevice(ip=self.ip, password=self.nvr_pass if is_nvr else self.cam_pass, username="admin",
                           port=self.nvr_port if is_nvr else self.cam_port, start_time="", check_time="", verbose=False)

    def cast_to_device(self, is_nvr):
        if self.company == "Dahua" and self.type != "כח":
            return DahuaDevice(ip=self.ip, password=self.nvr_pass if is_nvr else self.cam_pass, username="admin",
                               port=self.nvr_port if is_nvr else self.cam_port, start_time="", check_time="",
                               verbose=False)
        elif self.company == "Hikvision" and self.type != "כח":
            return HikvisionDevice(ip=self.ip, password=self.nvr_pass if is_nvr else self.cam_pass, username="admin",
                                   port_camera=self.cam_port, port=self.nvr_port if is_nvr else self.cam_port,
                                   start_time="",
                                   check_time="", verbose=False)
        else:
            return None

    def to_string(self):
        return f'{self.ip}:{self.nvr_port} {self.nvr_pass} {self.company} cam number: {self.camera_number} '
