import os
import cv2
import xmltodict
import uuid
import hashlib
from datetime import datetime, timedelta as td
from collections import OrderedDict
import requests
from requests.auth import HTTPDigestAuth
import socket
from capture import Capture

os.environ["FFREPORT"] = "level=quiet"
DEFAULT_TIMEOUT = 180  # seconds
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"timeout;{DEFAULT_TIMEOUT * 1000}"  # microseconds
DEFAULT_DATETIME = datetime(year=1900, month=1, day=1)
NO_ACCESS_CAMERA = 'אין גישה למצלמה'


def ping(ip, port, use_https=False, timeout_secs=30):
    scheme = "http"
    if use_https:
        scheme = "https"

    url = f"{scheme}://{ip}:{port}"
    try:
        response = requests.get(url, timeout=timeout_secs, verify=False)
        # Check if the status code indicates a successful connection
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.ConnectionError as e:
        print(f"Connection Error for ip {ip}: {e}")
        return False
    except requests.Timeout as e:
        print(f"Timeout Error: {e}")
        return False
    except Exception as e:
        print(f"Exception: {e}")
        return False


def ordered_dict_to_dict(d):
    if isinstance(d, OrderedDict):
        d = dict(d)
        for k, v in list(d.items()):
            d[k] = ordered_dict_to_dict(v)
    elif isinstance(d, list):
        for i in range(len(d)):
            d[i] = ordered_dict_to_dict(d[i])
    elif d == "false":
        d = False
    elif d == "True":
        d = True
    return d


class NVRDevice(object):
    def __init__(self, ip, password, start_time, check_time, port=90, username="admin", verbose=True, prot="http",
                 auto_login=True):
        self.ip = ip
        self.port = int(port)
        self.password = password
        self.username = username
        self.session = requests.Session()
        self.credentials = HTTPDigestAuth(self.username, self.password)
        self.verbose = verbose
        self.device_info = None
        self.cameras = []
        self.timeout_flags = {"Electricity": self.checkHTTPConnection(prot == 'https'),
                              "Remote": self.checkHTTPConnection(prot == 'https'),
                              "Login OK": None, "Camera Count": None, "password": True,
                              "Clock Synced": None, "Model Name": None,
                              "All": {"LPR": None, "LPR COUNT": None, "Playback": None, "Live": False}}
        self.start_time = start_time
        self.check_time = check_time
        self.prot = prot
        if auto_login:
            self.resetFlags()

    def resetFlags(self):
        self.flags = self.timeout_flags.copy()

        if not self.flags["Electricity"]:
            self.flags["Electricity"] = self.checkHTTPConnection(self.prot == 'https')

        if not self.flags["Remote"]:
            self.flags["Remote"] = self.checkHTTPConnection(self.prot == 'https')

        self.try_login()

        self.get_device_info()
        if isinstance(self.device_info, tuple):
            self.flags["Model Name"] = self.device_info[0]
        elif isinstance(self.device_info, str):
            self.flags["Model Name"] = self.device_info

        self.get_connected_cameras()
        self.flags["Camera Count"] = self.camera_count

    @property
    def camera_count(self):
        if self.flags["Login OK"]:
            if len(self.cameras) == 0:
                self.get_connected_cameras()

            return len(self.cameras)
        else:
            None

    def __str__(self):
        return f"NVR Device at {self.ip}:{self.port}"

    def __repr__(self):
        print(self.__str__())

    def checkHTTPConnection(self, use_https):
        return ping(self.ip, 90, use_https=use_https)

    def check_nvrConnection(self, ):
        return ping(self.ip, self.port)

    def checkLiveView(self, cam_id):
        live_works = self.tryLiveView(cam_id, max_retries=200, max_frames_count=1)
        if self.verbose and live_works:
            print(f"Live view is working for IP {self.ip}, camera {cam_id}")

        return live_works

    def baseLiveView(self, stream, cam_id, max_retries=None, max_frames_count=-1):
        try:
            if not stream.isOpened() and self.verbose:
                print(f"Couldn't connect to RTSP of IP {self.ip}")

            frames_count = 0
            while stream.isOpened():
                obtained_frame = False

                if isinstance(max_retries, int) and max_retries >= 0:
                    for i in range(max_retries):
                        # Read the input live stream
                        ret, frame = stream.read()
                        if frame is not None and frame.shape != (120, 176, 3):
                            obtained_frame = True
                            frames_count += 1
                            break
                elif max_retries is None:
                    while True:
                        # Read the input live stream
                        ret, frame = stream.read()
                        if frame is not None and frame.shape != (120, 176, 3):
                            obtained_frame = True
                            frames_count += 1
                            break

                if not obtained_frame:
                    break

                if frames_count == max_frames_count:
                    break

                height, width, layers = frame.shape
                frame = cv2.resize(frame, (width // 2, height // 2))

                # Show video frame
                cv2.imshow(f"{self.ip}, Camera {cam_id}", frame)

                # Quit when 'x' is pressed
                if cv2.waitKey(1) & 0xFF == ord('x'):
                    break
        except:
            if self.verbose:
                print(f"No live view for ip {self.ip} cam {cam_id}")
        finally:
            # Release and close stream
            stream.release()
            cv2.destroyAllWindows()

        return frames_count > 0

    def checkLPR(self, cam_id):
        lpr_results = self.getLPR(cam_id)
        lpr_works = len(lpr_results) > 0
        if lpr_works and self.verbose:
            print(
                f"Found at least one LPR ({lpr_results[0][1]}) from IP {self.ip}. From camera {cam_id} at {lpr_results[0][0]}")
        if lpr_works:
            print("good " + str(cam_id))
        return lpr_works, lpr_results

    def set_datetime(self, new_datetime):
        return

    def get_software_version(self):
        return


class HikvisionDevice(NVRDevice):
    def __init__(self, ip: object, password: object, check_time: object, start_time: object, port: object = 90,
                 username: object = "admin", verbose: object = True, prot: object = "http",
                 auto_login: object = True, port_camera: object = '') -> object:
        NVRDevice.__init__(self, ip, password, port=port, check_time=check_time, start_time=start_time,
                           username=username, verbose=verbose, prot=prot,
                           auto_login=auto_login)
        self.port_camera = port_camera

    def get_device_info(self):
        if self.flags["Login OK"] is None:
            self.flags["Login OK"] = self.try_login()

        if self.flags["Login OK"]:
            try:
                r = self.session.get(f"{self.prot}://{self.ip}:{self.port}/ISAPI/System/deviceInfo",
                                     auth=self.credentials,
                                     timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                if r.ok:
                    r = ordered_dict_to_dict(xmltodict.parse(r.text))["DeviceInfo"]
                    self.device_info = (r["model"], int(r["firmwareVersion"][1:].split('.')[0]))
                else:
                    r = self.session.get(f"{self.prot}://{self.ip}:{self.port}/PSIA/System/deviceInfo",
                                         auth=self.credentials,
                                         timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                    if r.ok:
                        r = ordered_dict_to_dict(xmltodict.parse(r.text))["DeviceInfo"]
                        self.device_info = (r["model"], int(r["firmwareVersion"][1:].split('.')[0]))

                if self.device_info in [('TS-5012-F', 4)]:  # some models don't support Digest Auth
                    self.credentials = (self.username, self.password)

                return self.device_info
            except requests.exceptions.Timeout:
                return None

    def get_connected_cameras(self):
        try:
            if self.flags["Remote"]:
                if self.device_info in [('TS-5012-F', 4), ("DS-TP50-12DT", 4)]:
                    cams = requests.get(
                        f"{self.prot}://{self.ip}:{self.port}/PSIA/Custom/SelfExt/ContentMgmt/DynVideo/inputs/channels",
                        auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")  # seconds

                    if cams.ok:
                        cams = ordered_dict_to_dict(xmltodict.parse(cams.text))["DynVideoInputChannelList"][
                            'DynVideoInputChannel']
                        if not isinstance(cams, list):
                            cams = [cams]

                        cams = list(sorted([int(cam["id"]) for cam in cams]))
                        cams = [(id, cams.index(id) + 1) for id in cams]
                else:
                    cams = requests.get(
                        f"{self.prot}://{self.ip}:{self.port}/ISAPI/ContentMgmt/InputProxy/channels/status",
                        auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")  # seconds

                    if cams.ok:
                        cams = ordered_dict_to_dict(xmltodict.parse(cams.text))["InputProxyChannelStatusList"][
                            'InputProxyChannelStatus']
                        if not isinstance(cams, list):
                            cams = [cams]

                        cams = list(sorted([int(cam["id"]) for cam in cams]))
                        cams = [(id, cams.index(id) + 1) for id in cams]

                if self.verbose:
                    print(f"Found {len(cams)} connected cameras for Hikvision IP {self.ip}")
                try:
                    if len(cams) > 0:
                        self.cameras = cams
                except:
                    self.cameras = []

            else:
                self.cameras = []

            return self.cameras
        except Exception as e:
            print(f'Connection error to ip {e} {self.ip}:{self.port} {self.password}')
            return []

    def check_validation_password(self):
        res = requests.get(f"{self.prot}://{self.ip}:{self.port}/ISAPI/System/status", auth=self.credentials,
                           timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
        if res.status_code == 401:
            print('x')
        return res.status_code == 401

    def try_login(self):
        if self.flags["Remote"]:
            res = requests.get(f"{self.prot}://{self.ip}:{self.port}/ISAPI/System/status", auth=self.credentials,
                               timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
            if res.ok:
                self.flags["Login OK"] = True
                return self.flags["Login OK"]
            else:
                res = requests.get(f"{self.prot}://{self.ip}:{self.port}/PSIA/System/status", auth=self.credentials,
                                   timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

                if res.status_code == 401:  # old models don't support Digest Auth
                    self.credentials = (self.username, self.password)
                    res = requests.get(f"{self.prot}://{self.ip}:{self.port}/PSIA/System/status", auth=self.credentials,
                                       timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                    if res.status_code == 401:
                        self.flags['password'] = False

                self.flags["Login OK"] = res.ok

                return self.flags["Login OK"]

            self.flags["Login OK"] = False

        self.flags["Login OK"] = None
        return self.flags["Login OK"]

    def check_nvr(self, mins=30):
        try:
            self.resetFlags()
            if self.flags["Login OK"]:
                self.flags["Clock Synced"] = self.set_datetime(datetime.now())
                if self.flags["Camera Count"] > 0:
                    self.flags.pop("All")

                    for (orig_cam_id, cam_id) in self.cameras:
                        lpr_works, lpr_results = self.checkLPR(cam_id, mins=mins)
                        self.flags[cam_id] = {"LPR": lpr_works, "LPR COUNT": len(lpr_results),
                                              "Playback": self.checkPlayback(orig_cam_id, mins=mins),
                                              "Live": self.checkLiveView(orig_cam_id)}

            return self.flags
        except (requests.ReadTimeout, requests.exceptions.ConnectionError):
            return self.timeout_flags

    def get_lpr(self, last_capture_time, cam_id):
        if self.device_info is None:
            self.get_device_info()

        # LPR check
        if self.device_info in [("DS-TP50-16E", 4), ("DS-TP50-16E", 5), ("DS-TP50-12DT", 4),
                                ('DS-TP50-12DT', 5), ('DS-TP50-04H', 5), ('DS-TP50-08H', 5)]:  # model index 1
            try:
                response = self.get_data_from_hikvision_model_1(camera_num=0, cam_id=cam_id)
                num_of_results = int(response[1])
                amount_pictures = response[2]
                if num_of_results > 0:
                    capture = self.get_data_from_hikvision_model_1(camera_num=int(num_of_results) - 1,
                                                                   cam_id=cam_id)
                    return Capture(last_cap_time=capture[0], cap_amount=capture[1],
                                   is_captured='כן'), amount_pictures
                else:
                    return Capture(last_cap_time=last_capture_time, cap_amount='0', is_captured='לא'), amount_pictures
            except:
                return Capture(last_cap_time=last_capture_time, cap_amount="0", is_captured='לא'), 0

        elif self.device_info in [("DS-7604NI-E1/A", 3), ("DS-7608NI-G2/4P", 3),
                                  ('DS-7608NI-E2/A', 3)]:  # model index 2
            position = 0
            data = self.get_data_from_hikvision_model_2(cam_id=cam_id, position=position)
            if data.ok:
                data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                if int(data["numOfMatches"]) > 0:
                    status_str = data['responseStatusStrg']
                    if status_str == 'MORE':
                        position += 50
                        data = self.get_data_from_hikvision_model_2(position=position, cam_id=cam_id)
                        data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                        status_str = data['responseStatusStrg']
                    count_matches = int(data["numOfMatches"]) + position
                    last_capture_time = data["matchList"]["searchMatchItem"][-1]['timeSpan']['endTime']
                    print("model 2 hik: ", last_capture_time, count_matches, self.ip, ':', self.port, ' ',
                          self.password)
                    return Capture(last_cap_time=last_capture_time, cap_amount=str(count_matches), is_captured='כן'), 0
                else:
                    return Capture(last_cap_time=last_capture_time, cap_amount="0", is_captured='לא'), 0

        elif self.device_info in [('DS-M5504HNI', 5), ('DS-7608NXI-K2', 4),('DS-7604NI-K1', 4)]:  # model index 3
            position = 0
            data = self.get_data_from_hikvision_model_3(position=position, cam_id=cam_id)
            if data.ok:
                data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                if int(data["numOfMatches"]) > 0 and len(data["matchList"]["searchMatchItem"]) > 0:
                    status_str = data['responseStatusStrg']
                    while status_str == 'MORE' and position < 5000:
                        position += 50
                        data = self.get_data_from_hikvision_model_3(position=position, cam_id=cam_id)
                        data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                        status_str = data['responseStatusStrg']
                    count_matches = int(data["numOfMatches"]) + position
                    last_capture_time = data["matchList"]["searchMatchItem"][-1]['timeSpan']['endTime']
                    print("model 3 hik: ", last_capture_time, count_matches)
                    return Capture(last_cap_time=last_capture_time, cap_amount=str(count_matches), is_captured='כן'), 0

            return Capture(last_cap_time=last_capture_time, cap_amount="0", is_captured='לא')
        elif self.device_info in [("DS-TP50-12DT", 4), ("TS-5012-F", 4)]:  # model index 4
            position = 0
            data = self.get_data_from_hikvision_model_4(cam_id=cam_id, position=position)

            if data.ok:
                data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                pic_amount = int(self.get_amount_pictures(cam_number=cam_id, data=data, model=4))
                if int(data["numOfMatches"]) > 0:
                    data = self.get_data_from_hikvision_model_4(cam_id=cam_id, position=int(data["totalMatches"]) - 1)
                    data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                    last_capture_time = data["matchList"]["matchElement"]["trafficData"]["captureTime"]
                    count_matches = data["totalMatches"]
                    print("model 4 hik: ", last_capture_time, count_matches)
                    return Capture(last_cap_time=last_capture_time, cap_amount=count_matches,
                                   is_captured='כן'), pic_amount
                else:
                    return Capture(last_cap_time=last_capture_time, cap_amount='0', is_captured='לא'), pic_amount
        else:
            return Capture(last_cap_time=last_capture_time, cap_amount='0', is_captured=''), 0

    def checkPlayback(self, cam_id, mins=30):
        if self.flags["Login OK"]:
            cap_at_start, cap_at_end = None, None

            if self.device_info in [("TS-5012-F", 4)]:
                data_request_xml_base = '''
                    <CMSearchDescription>
                        <searchID>{}</searchID>
                            <trackList>
                                <trackID>{}01</trackID>
                            </trackList>
                        <timeSpanList>
                            <timeSpan>
                                <startTime>{}</startTime>
                                <endTime>{}</endTime>
                            </timeSpan>
                        </timeSpanList>
                        <maxResults>5</maxResults>
                        <metadataList>
                            <metadataDescriptor>//metadata.psia.org/VideoMotion</metadataDescriptor>
                        </metadataList>
                    </CMSearchDescription>'''

                data = self.session.post(f"{self.prot}://{self.ip}:{self.port}/PSIA/ContentMgmt/search/",
                                         auth=self.credentials,
                                         data=data_request_xml_base.format(str(uuid.uuid4()),
                                                                           cam_id,
                                                                           self.datetime_to_str(
                                                                               self.check_time - td(minutes=mins + 1)),
                                                                           self.datetime_to_str(self.check_time)),
                                         timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                if data.ok:
                    data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                    if int(data["numOfMatches"]) > 0:
                        if int(data["numOfMatches"]) == 1:
                            data["matchList"]["searchMatchItem"] = [data["matchList"]["searchMatchItem"]]

                        cap_at_start, cap_at_end = data["matchList"]["searchMatchItem"][0]["timeSpan"].values()


            else:
                data_request_xml_base = '''
                    <CMSearchDescription>
                        <searchID>{}</searchID>
                        <trackList>
                            <trackID>{}01</trackID>
                        </trackList>
                        <timeSpanList>
                            <timeSpan>
                                <startTime>{}</startTime>
                                <endTime>{}</endTime>
                            </timeSpan>
                        </timeSpanList>
                        <maxResults>5</maxResults>
                        <metadataList>
                            <metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor>
                        </metadataList>
                    </CMSearchDescription>'''

                data = self.session.post(f"{self.prot}://{self.ip}:{self.port}/ISAPI/ContentMgmt/search",
                                         auth=self.credentials,
                                         data=data_request_xml_base.format(str(uuid.uuid4()),
                                                                           cam_id,
                                                                           self.datetime_to_str(
                                                                               self.check_time - td(minutes=mins + 1)),
                                                                           self.datetime_to_str(self.check_time)),
                                         timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                if data.ok:
                    data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                    if int(data["numOfMatches"]) > 0:
                        if int(data["numOfMatches"]) == 1:
                            data["matchList"]["searchMatchItem"] = [data["matchList"]["searchMatchItem"]]

                        cap_at_start, cap_at_end = data["matchList"]["searchMatchItem"][0]["timeSpan"].values()

            if None not in (cap_at_start, cap_at_end):
                if self.verbose:
                    print(
                        f"Found at least one playback video from Hikvision IP {self.ip}. From camera {cam_id} start: {cap_at_start} end: {cap_at_end}")

                return True

        return False

    def tryLiveView(self, cam_id, stream_type=2, max_retries=None, max_frames_count=-1):
        if self.device_info is None:
            self.get_device_info()

        if not ping(self.ip, 554, timeout_secs=10):
            return False

        stream = None
        if self.device_info in [('DS-7604NI-E1/A', 3), ('DS-TP50-12DT', 4), ('DS-TP50-16E', 5)] or stream is None:
            stream = cv2.VideoCapture(
                f'rtsp://{self.username}:{self.password}@{self.ip}:554/Streaming/channels/{cam_id}0{stream_type}')
        if self.device_info in [("TS-5012-F", 4)] or not stream.isOpened():
            stream = cv2.VideoCapture(
                f'rtsp://{self.username}:{self.password}@{self.ip}:554/PSIA/Streaming/channels/{cam_id}0{stream_type}')
            if stream.isOpened():
                print(f"2 {self.device_info}")

        return self.baseLiveView(stream, cam_id, max_frames_count=max_frames_count, max_retries=max_retries)

    # def set_datetime(self, new_datetime):
    #     if self.flags["Login OK"]:
    #         request_xml_base = '''<Time xmlns="http://www.isapi.org/ver20/XMLSchema" version="2.0">
    #                                 <timeMode>manual</timeMode>
    #                                 <localTime>{}</localTime>
    #                                 <timeZone>CST-2:00:00DST01:00:00,M3.5.4/02:00:00,M10.5.0/02:00:00</timeZone>
    #                             </Time>'''
    #
    #         if self.device_info in [('TS-5012-F', 4), ("DS-TP50-12DT", 4)]:
    #             r = self.session.put(f"http://{self.ip}:{self.port}/PSIA/System/time", auth=self.credentials,
    #                                  data=request_xml_base.format(self.datetime_to_str(new_datetime)[:-1]))
    #
    #             return r.status_code == 200
    #         else:
    #             r = self.session.put(f"http://{self.ip}:{self.port}/ISAPI/System/time", auth=self.credentials,
    #                                  data=request_xml_base.format(self.datetime_to_str(new_datetime)[:-1]))
    #
    #             return r.status_code == 200
    #
    #     return False

    def get_current_datetime(self):
        if self.flags["Login OK"]:
            y = DEFAULT_DATETIME
            if self.device_info in [('TS-5012-F', 4), ("DS-TP50-12DT", 4)]:
                r = self.session.get(f"{self.prot}://{self.ip}:{self.port}/PSIA/System/time", auth=self.credentials,
                                     timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                return self.get_date_from_response(response=r)
            else:
                r = self.session.get(f"{self.prot}://{self.ip}:{self.port}/ISAPI/System/time", auth=self.credentials,
                                     timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                return self.get_date_from_response(response=r)
        return DEFAULT_DATETIME

    def get_amount_pictures(self, cam_number, data, model):
        if self.flags["Login OK"]:
            try:
                if model == 1:

                    y = data['matchList']['matchElement']
                    if isinstance(y, list): y = y[0]
                    y = y['trafficData']
                    data_request_xml_base = f'''
                        <PicRecInfoSearchDescription>
                            <searchID>{data['searchID']}</searchID>
                            <VehicleList>
                                <Vehicle>
                                    <vehicleID>CA4009CB-7B60-0001-19F1-8450455078B0</vehicleID>
                                    <channel>{cam_number}</channel>
                                    <ctrl>{y['ctrl']}</ctrl>
                                    <drive>{y['drive']}</drive>
                                    <part>{y['part']}</part>
                                    <fileNo>{y['fileNo']}</fileNo>
                                    <startOffset>{y['startOffset']}</startOffset>
                                    <picLen>{y['picLen']}</picLen>
                                    <captureTime>{y['captureTime']}</captureTime>
                                    <violationType>{y['violationType']}</violationType>
                                </Vehicle>
                            </VehicleList>
                        </PicRecInfoSearchDescription>'''
                    r = self.session.post(f"{self.prot}://{self.ip}:{self.port}/ISAPI/Traffic/ContentMgmt/picRecInfo",
                                          data=data_request_xml_base, auth=self.credentials, timeout=DEFAULT_TIMEOUT,
                                          verify={self.prot} == "http")

                    xml_response = r.text
                    result = xml_response.count('fileName')
                    if isinstance(result, int) or isinstance(result, str):
                        return 2 if result == 6 else 1
                    return 1
                elif model == 4:
                    search_id = data['searchID']
                    data = data['matchList']['matchElement']['trafficData']
                    picture_amount_request_xml = '''<?xml version='1.0' encoding='utf-8'?>
                                <CMSearchDescription>
                                    <searchID>{}</searchID>
                                    <VehicleList>
                                        <Vehicle>
                                            <vehicleID>1682208259634546</vehicleID>
                                            <channel>{}</channel>
                                            <ctrl>{}</ctrl>
                                            <drive>{}</drive>
                                            <part>{}</part>
                                            <fileNo>{}</fileNo>
                                            <startOffset>{}</startOffset>
                                            <picLen>{}</picLen>
                                            <captureTime>{}</captureTime>
                                            <violationType>{}</violationType>
                                        </Vehicle>
                                    </VehicleList>
                                </CMSearchDescription>'''
                    cam_amount_request = self.session.post(
                        f"{self.prot}://{self.ip}:{self.port}/PSIA/Custom/SelfExt/ContentMgmt/Traffic/picRecInfo",
                        auth=self.credentials,
                        data=picture_amount_request_xml.format(search_id,
                                                               cam_number,
                                                               data['ctrl'],
                                                               data['drive'],
                                                               data['part'],
                                                               data['fileNo'],
                                                               data['startOffset'],
                                                               data['picLen'],
                                                               data['captureTime'],
                                                               data['violationType']),
                        timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                    return int(cam_amount_request.text.count('</picture>'))
            except Exception as e:
                print(f'Amount bug in {self.ip}:{self.port}')
                print(e)
                return NO_ACCESS_CAMERA
        return NO_ACCESS_CAMERA

    def get_data_from_hikvision_model_1(self, camera_num, cam_id):
        data_request_xml_base = '''
                            <DataOperation>
                                <operationType>search</operationType>
                                <searchCond>
                                    <searchID>{searchid}</searchID>
                                    <timeSpanList>
                                        <timeSpan>
                                            <startTime>{start_t}</startTime>
                                            <endTime>{end_t}</endTime>
                                        </timeSpan>
                                    </timeSpanList>
                                    <criteria>
                                        <dataType>0</dataType>
                                        <channel>{camid}</channel>
                                        <violationType>0</violationType>
                                        <surveilType>0</surveilType>
                                        <analysised>true</analysised>
                                    </criteria>
                                    <searchResultPosition>{camera_number}</searchResultPosition>                                    
                                </searchCond>
                            </DataOperation>'''

        data = self.session.post(f"{self.prot}://{self.ip}:{self.port}/ISAPI/Traffic/ContentMgmt/dataOperation",
                                 auth=self.credentials,
                                 data=data_request_xml_base.format(searchid=str(uuid.uuid4()),
                                                                   start_t=self.start_time,
                                                                   end_t=self.check_time,
                                                                   camid=cam_id,
                                                                   camera_number=str(camera_num)),
                                 timeout=DEFAULT_TIMEOUT, verify=False)
        if data.status_code == 503:
            data_request_xml_base = f""""1.0" encoding="utf-8"?><DataOperation><operationType>search</operationType><searchCond><searchID>{str(uuid.uuid4())}</searchID><timeSpanList><timeSpan><startTime>{self.start_time}</startTime><endTime>{self.check_time}</endTime></timeSpan></timeSpanList><criteria><dataType>0</dataType><violationType>0</violationType><channel>{cam_id}</channel><plateType/><plateColor/><direction/><incidentCorrect/><plate/><speedMin/><speedMax/><vehicleType/><vehicleColor/><laneNo/><surveilType>0</surveilType><romoteHost/><analysised>true</analysised><sendFlag/></criteria><searchResultPosition>{str(camera_num)}</searchResultPosition><maxResults>100</maxResults><vehicleSubTypeList/></searchCond></DataOperation>"""
            data = self.session.post(f"{self.prot}://{self.ip}:{self.port}/ISAPI/Traffic/ContentMgmt/dataOperation",
                                     auth=self.credentials,data=data_request_xml_base,timeout=DEFAULT_TIMEOUT,verify=False)
        if data.ok:
            data = ordered_dict_to_dict(xmltodict.parse(data.text))["TrafficSearchResult"]
            pic_amount = self.get_amount_pictures(cam_number=cam_id, model=1, data=data)
            if int(data["numOfMatches"]) > 0:
                if len(data['matchList']['matchElement']) > 1:
                    return data['matchList']['matchElement'][-1]['trafficData']['captureTime'], data[
                        'totalMatches'], pic_amount
                return data['matchList']['matchElement']['trafficData']['captureTime'], data['totalMatches'], pic_amount


    def get_data_from_hikvision_model_2(self, position, cam_id):
        data_request_xml_base = '''
            <CMSearchDescription>
                <searchID>{searchid}</searchID>
                <trackList>
                    <trackID>{camid}03</trackID>
                </trackList>
                <timeSpanList>
                    <timeSpan>
                        <startTime>{start_t}</startTime>
                        <endTime>{end_t}</endTime>
                    </timeSpan>
                </timeSpanList>
                <contentTypeList>
                    <contentType>metadata</contentType>
                </contentTypeList>                
                <maxResults>50</maxResults>
                <searchResultPostion>100</searchResultPostion>                
                <metadataList>
                    <metadataDescriptor>//recordType.meta.std-cgi.com/vehicleDetection</metadataDescriptor>
                    <SearchProperity>
                        <country>255</country>
                    </SearchProperity>                  
                </metadataList>
            </CMSearchDescription>'''
        x = data_request_xml_base.format(searchid=str(uuid.uuid4()),
                                         camid=cam_id,
                                         start_t=self.start_time,
                                         end_t=self.check_time,
                                         pos=position)
        return self.session.post(f"{self.prot}://{self.ip}:{self.port}/ISAPI/ContentMgmt/search", auth=self.credentials,
                                 data=data_request_xml_base.format(searchid=str(uuid.uuid4()),
                                                                   camid=cam_id,
                                                                   start_t=self.start_time,
                                                                   end_t=self.check_time
                                                                   # pos=position
                                                                   ),
                                 timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

    def get_data_from_hikvision_model_3(self, position, cam_id):
        data_request_xml_base = '''
            <CMSearchDescription>
                <searchID>{searchid}</searchID>
                <trackList>
                    <trackID>{camid}03</trackID>
                </trackList>
                <timeSpanList>
                    <timeSpan>
                        <startTime>{start_t}</startTime>
                        <endTime>{end_t}</endTime>
                    </timeSpan>
                </timeSpanList>
                <contentTypeList>
                    <contentType>metadata</contentType>
                </contentTypeList>
                <maxResults>5000</maxResults>                
                <searchResultPostion>{position}</searchResultPostion>
                <metadataList>
                    <metadataDescriptor>//recordType.meta.std-cgi.com/allPic</metadataDescriptor>
                </metadataList>

            </CMSearchDescription>'''.format(searchid=str(uuid.uuid4()),
                                              camid=cam_id,
                                              start_t=self.start_time,
                                              end_t=self.check_time,
                                              timeout=DEFAULT_TIMEOUT,
                                              verify={self.prot} == "http",
                                              position=position)
        return self.session.post(f"{self.prot}://{self.ip}:{self.port}/ISAPI/ContentMgmt/search", auth=self.credentials,
                                 data=data_request_xml_base.format(searchid=str(uuid.uuid4()),
                                                                   camid=cam_id,
                                                                   start_t=self.start_time,
                                                                   end_t=self.check_time,
                                                                   timeout=DEFAULT_TIMEOUT,
                                                                   verify={self.prot} == "http",
                                                                   position=position))

    def get_data_from_hikvision_model_4(self, cam_id, position):
        data_request_xml_base = '''<CMSearchDescription>
                        <searchID>{}</searchID>
                        <timeSpanList>
                            <timeSpan>
                                <startTime>{}</startTime>
                                <endTime>{}</endTime>
                            </timeSpan>
                        </timeSpanList>
                        <critera>
                            <channel>{}</channel>
                            <surveilType>0</surveilType>
                            <dataType>0</dataType>
                            <violationType>0</violationType>
                        </critera>
                        <searchResultPostion>{}</searchResultPostion>
                        <maxResults>5000</maxResults>
                    </CMSearchDescription>'''
        res = self.session.post(f"{self.prot}://{self.ip}:{self.port}/PSIA/Custom/SelfExt/ContentMgmt/Traffic/Search",
                                auth=self.credentials,
                                data=data_request_xml_base.format(str(uuid.uuid4()),
                                                                  self.start_time,
                                                                  self.check_time,
                                                                  cam_id,
                                                                  position),
                                timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

        return res

    def get_date_from_response(self, response):
        if response.status_code != 200:
            return DEFAULT_DATETIME
        data = response.text
        local_time = ordered_dict_to_dict(xmltodict.parse(data))["Time"]["localTime"].replace('T', ' ')[:-6]
        return datetime.strptime(local_time, '%Y-%m-%d %H:%M:%S')

    # TODO:
    def check_amount_pictures(self, cam_id, previous_pic_amount):
        if self.device_info is None:
            self.get_device_info()
        try:
            # LPR check
            if self.device_info in [("DS-TP50-16E", 4), ("DS-TP50-16E", 5), ("DS-TP50-12DT", 4),
                                    ('DS-TP50-12DT', 5), ('DS-TP50-04H', 5), ('DS-TP50-08H', 5)]:  # model index 1
                response = self.get_data_from_hikvision_model_1(camera_num=0, cam_id=cam_id)
                amount_pictures = response[2]
                return amount_pictures
            elif self.device_info in [("DS-7604NI-E1/A", 3), ("DS-7608NI-G2/4P", 3),
                                      ('DS-7608NI-E2/A', 3)] or self.device_info in [
                ('DS-M5504HNI', 5)]:  # model indexes 2 or 3
                return '1'
            elif self.device_info in [("DS-TP50-12DT", 4), ("TS-5012-F", 4)]:  # model index 4
                position = 0
                data = self.get_data_from_hikvision_model_4(cam_id=cam_id, position=position)

                if data.ok:
                    data = ordered_dict_to_dict(xmltodict.parse(data.text))['CMSearchResult']
                    pic_amount = self.get_amount_pictures(cam_number=cam_id, data=data, model=4)
                    return pic_amount
            return previous_pic_amount

        except:
            return previous_pic_amount

    def get_software_version(self):
        url = f"{self.prot}://{self.ip}:{self.port}/ISAPI/System/deviceInfo/capabilities"
        res = self.session.get(url=url, auth=self.credentials, timeout=180, verify={self.prot} == "http")
        # Parse the XML response
        device_info = ordered_dict_to_dict(xmltodict.parse(res.text))['DeviceInfo']
        if self.port == 90:
            model = device_info['model']
            firmware_version = device_info['firmwareVersion']
        else:
            model = device_info['model']['#text']
            firmware_version = device_info['firmwareVersion']['#text']
        return firmware_version, model


class DahuaDevice(NVRDevice):
    def __init__(self, ip, password, port=90, check_time=datetime.now(), start_time=datetime.now(), username="admin",
                 verbose=True, prot="http",
                 auto_login=True):
        self.session_id = None
        self.mediaFindObjectId = None
        self.rpc_request_id = 0
        self.prot = prot
        NVRDevice.__init__(self, ip, password, port=port, check_time=check_time, username=username, verbose=verbose,
                           auto_login=auto_login, start_time=start_time, prot=prot)

    def datetime_to_str(self, dt):
        return dt.strftime("%Y-%m-%d%%20%H:%M:%S")

    def rpc_request(self, url, method, params, add_data={}):
        # Make a RPC request
        data = {'method': method, 'id': self.rpc_request_id, 'params': params} | add_data
        if self.session_id is not None:
            data['session'] = self.session_id

        self.rpc_request_id += 1
        r = self.session.post(url, json=data, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

        if r.ok:
            return r.json()
        else:
            return None

    def check_live_stream(self):
        # Build the RTSP URL
        rtsp_url = f"rtsp://{self.username}:{self.password}@{self.url}:8080/cam/realmonitor?channel=1&subtype=0"

        # Create a VideoCapture object
        cap = cv2.VideoCapture(rtsp_url)

        if cap.isOpened():
            print("Live stream is working.")
            # Release the VideoCapture object
            cap.release()
            return 'V'
        else:
            print("Unable to connect to the live stream.")
            # Release the VideoCapture object
            cap.release()
            return 'X'

    def get_device_info(self):
        if self.flags["Login OK"] is None:
            self.flags["Login OK"] = self.try_login()

        if self.flags["Login OK"]:
            r = self.rpc_request(f"{self.prot}://{self.ip}:{self.port}/RPC2", method="magicBox.getDeviceType",
                                 params="")
            if r is not None:
                self.device_info = r["params"]["type"]

        return self.device_info

    def try_login(self):
        if self.flags["Remote"]:
            url = f'{self.prot}://{self.ip}:{self.port}/RPC2_Login'

            r = self.rpc_request(url, method="global.login",
                                 params={'userName': self.username, 'password': "", 'clientType': "Dahua3.0-Web3.0"})

            self.session_id = r["session"]
            realm = r['params']['realm']
            random = r['params']['random']

            # Password encryption algorithm
            # Reversed from rpcCore.getAuthByType
            pwd_phrase = f"{self.username}:{realm}:{self.password}".encode('utf-8')
            pwd_hash = hashlib.md5(pwd_phrase).hexdigest().upper()

            pass_phrase = f'{self.username}:{random}:{pwd_hash}'.encode('utf-8')
            pass_hash = hashlib.md5(pass_phrase).hexdigest().upper()

            # login2: the real login
            params = {'userName': self.username,
                      'password': pass_hash,
                      'clientType': "Dahua3.0-Web3.0",
                      'authorityType': "Default",
                      'passwordType': "Default"}
            r = self.rpc_request(url, method="global.login", params=params)

            self.flags["Login OK"] = bool(r['result'])
        else:
            self.flags["Login OK"] = None

        return self.flags["Login OK"]

    def tryLogout(self):
        self.rpc_request(f"{self.prot}://{self.ip}:{self.port}/RPC2", method="global.logout",
                         params=None)
        self.session.close()

    def check_validation_password(self):
        url = f'{self.prot}://{self.ip}:{self.port}/RPC2_Login'

        r = self.rpc_request(url, method="global.login",
                             params={'userName': self.username, 'password': "", 'clientType': "Dahua3.0-Web3.0"})

        self.session_id = r["session"]
        realm = r['params']['realm']
        random = r['params']['random']

        # Password encryption algorithm
        # Reversed from rpcCore.getAuthByType
        pwd_phrase = f"{self.username}:{realm}:{self.password}".encode('utf-8')
        pwd_hash = hashlib.md5(pwd_phrase).hexdigest().upper()

        pass_phrase = f'{self.username}:{random}:{pwd_hash}'.encode('utf-8')
        pass_hash = hashlib.md5(pass_phrase).hexdigest().upper()

        # login2: the real login
        params = {'userName': self.username,
                  'password': pass_hash,
                  'clientType': "Dahua3.0-Web3.0",
                  'authorityType': "Default",
                  'passwordType': "Default"}
        r = self.rpc_request(url, method="global.login", params=params)
        if r.status_code == 401:
            print('x')
        return r.status_code == 401

    def get_connected_cameras(self):
        if self.flags["Login OK"]:
            ch_count = 0
            if self.device_info in ["ITSE0804-GN5B-D"]:
                r = self.rpc_request(f"{self.prot}://{self.ip}:{self.port}/RPC2", method="eventManager.getEventData",
                                     params={"code": "NetDevicesInfo", "index": 0, "name": ""})
                if r is not None and r["result"] and r["params"]["data"][0]["Devices"] is not None:
                    ch_count = len(r["params"]["data"][0]["Devices"])
            elif self.device_info in ["ITC952-AF3F-IR7"]:  # this is a single camera
                ch_count = 1
            elif self.device_info in ["DH-XVR5104HS-4KL-X-1TB"]:
                r = self.rpc_request(f"{self.prot}://{self.ip}:{self.port}/RPC2",
                                     method="LogicDeviceManager.getCameraState",
                                     params={"uniqueChannels": [-1]})
                ch_count = len([c for c in r["params"]["states"] if c['connectionState'] == 'Connected'])
            else:
                print(self.device_info)

            if self.verbose:
                print(f"Found {ch_count} connected cameras for Dahua IP {self.ip}")

            self.cameras = range(1, ch_count + 1)
            return self.cameras

        self.cameras = []
        return self.cameras

    def check_nvr(self, mins=30):
        try:
            self.resetFlags()
            if self.flags["Login OK"]:
                self.flags["Clock Synced"] = self.set_datetime(datetime.now())
                if self.flags["Camera Count"] > 0:
                    self.flags.pop("All")

                    for cam in self.cameras:
                        lpr_works, lpr_results = self.checkLPR(cam)
                        self.flags[cam] = {"LPR": lpr_works, "LPR COUNT": len(lpr_results),
                                           "Playback": self.checkPlayback(cam, mins=mins),
                                           "Live": self.checkLiveView(cam)}

                    self.destroy_media_find_object()

                self.tryLogout()

            return self.flags
        except (requests.ReadTimeout, requests.exceptions.ConnectionError):
            return self.timeout_flags

    def create_media_find_object(self):
        if self.mediaFindObjectId is None:
            r = self.session.get(f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=factory.create",
                                 auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
            if r.ok:
                self.mediaFindObjectId = r.text.split('=')[-1].strip("\x0a\x0d")
                return True
            else:
                return False
        else:
            return True

    def close_media_find_object(self):
        if self.mediaFindObjectId is not None:
            self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=close&object={self.mediaFindObjectId}",
                auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

    def destroy_media_find_object(self):
        if self.mediaFindObjectId is not None:
            self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=destroy&object={self.mediaFindObjectId}",
                auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

            self.mediaFindObjectId = None

    def parse_media_file_find(self, result_entry):
        entry_split = result_entry.split('\r\n')
        if not entry_split[0].startswith("found="):
            return []

        if int(entry_split[0].split('=')[-1]) == 0:
            return []

        items = {}
        for entry in entry_split[1:]:
            if entry.startswith("items["):
                entry = entry[len("items["):]
                ind = int(entry[:entry.index("]")])
                if ind not in items:
                    items[ind] = {}

                entry = entry[entry.index("]") + 2:]
                if entry.startswith("Type"):
                    items[ind]["type"] = entry[len("Type="):]
                elif entry.startswith("Summary.TrafficCar.PlateNumber"):
                    items[ind]["plate"] = entry[len("Summary.TrafficCar.PlateNumber="):]
                elif entry.startswith("StartTime"):
                    items[ind]["time"] = entry[len("StartTime="):]
                elif entry.startswith("EndTime"):
                    items[ind]["end"] = entry[len("EndTime="):]

        if len(items) == 0:
            return []

        return list(items.values())

    def getLPR(self, cam_id, last_capture_time):
        if self.create_media_find_object():
            length_captures = 0
            self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=findFile&object={self.mediaFindObjectId}&condition.Channel={cam_id}&condition.StartTime={self.start_time}&condition.EndTime={self.check_time}&condition.Types[0]=jpg",
                auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

            r = self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=findNextFile&object={self.mediaFindObjectId}&count=5000",
                # no limit
                auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
            items = self.parse_media_file_find(r.text)
            items = [i for i in items if len(i["plate"]) > 0 and i["plate"].lower() != "unknown"]
            length_captures += len(items)
            if length_captures == 0:
                self.close_media_find_object()
                return Capture(last_cap_time=last_capture_time, cap_amount='0', is_captured='לא')
            last_capture = items[-1]['end']
            while len(items) != 0:
                r = self.session.get(
                    f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=findNextFile&object={self.mediaFindObjectId}&count=5000",
                    # no limit
                    auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")
                items = self.parse_media_file_find(r.text)
                # items = [i for i in items if len(i["plate"]) > 0 and i["plate"].lower() != "unknown"]
                if len(items) > 0: last_capture = items[-1]['end']
                length_captures += len(items)
            # items = [i for i in items if len(i["plate"]) > 0 and i["plate"].lower() != "unknown"]
            self.close_media_find_object()
            return Capture(last_cap_time=last_capture, cap_amount=length_captures, is_captured='כן')

        return Capture(last_cap_time=last_capture_time, cap_amount='0', is_captured='לא')

    def checkPlayback(self, cam_id, mins=30):
        if self.create_media_find_object():
            self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=findFile&object={self.mediaFindObjectId}&condition.Channel={cam_id}&condition.StartTime={self.datetime_to_str(self.check_time - td(minutes=mins + 1))}&condition.EndTime={self.datetime_to_str(self.check_time)}&condition.Types[0]=dav0&condition.Types[1]=mp4",
                auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

            r = self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/mediaFileFind.cgi?action=findNextFile&object={self.mediaFindObjectId}&count=5",
                auth=self.credentials, timeout=DEFAULT_TIMEOUT, verify={self.prot} == "http")

            items = self.parse_media_file_find(r.text)
            if len(items) > 0:
                cap_at_start, cap_at_end = items[0]["time"], items[0]["end"]

                if self.verbose:
                    print(
                        f"Found Playback video from Dahua IP {self.ip}. From camera {cam_id} start: {cap_at_start} end: {cap_at_end}")

                return True

        return False

    def tryLiveView(self, cam_id, stream_type=1, max_retries=None, max_frames_count=-1):
        if not ping(self.ip, 554, timeout_secs=10):
            return False

        stream = cv2.VideoCapture(
            f'rtsp://{self.username}:{self.password}@{self.ip}:554/cam/realmonitor?channel={cam_id}&subtype={stream_type}')
        return self.baseLiveView(stream, cam_id, max_retries=max_retries, max_frames_count=max_frames_count)

    def set_datetime(self, new_datetime):
        if self.flags["Login OK"]:
            r = self.session.get(
                f"{self.prot}://{self.ip}:{self.port}/cgi-bin/global.cgi?action=setCurrentTime&time={self.datetime_to_str(new_datetime)}",
                auth=self.credentials, verify={self.prot} == "http")

            return r.status_code == 200

        return False

    def get_current_datetime(self):
        if self.flags["Login OK"]:
            url = f"{self.prot}://{self.ip}:{self.port}/RPC2"
            r = self.rpc_request(url=url, method='global.getCurrentTime', params=None)
            if r['result']:
                current_time = r['params']['time']
                current_time = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
                return current_time
        return DEFAULT_DATETIME

    def get_software_version(self):
        DEFAULT_VALUE = "לא נמצאו פרטים", "לא נמצאו פרטים"

        try:

            url = f"{self.prot}://{self.ip}:{self.port}/RPC2"
            response = self.rpc_request(url=url, method='magicBox.getSoftwareVersion', params=None)
            if response['result']:
                data = response['params']['version']
                return data['Version']
            else:
                return DEFAULT_VALUE
        except:
            return DEFAULT_VALUE

    def get_model(self):
        DEFAULT_VALUE = "לא נמצאו פרטים", "לא נמצאו פרטים"
        try:
            url = f"{self.prot}://{self.ip}:{self.port}/RPC2"
            response = self.rpc_request(url=url, method="magicBox.getDeviceType", params=None)
            if response['result']:
                return response['params']['type']

        except Exception as e:
            print(e)
            return DEFAULT_VALUE
