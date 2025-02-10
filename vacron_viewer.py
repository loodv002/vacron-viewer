import requests
import cv2
import sys

from vacron_frame_parser import FrameParser

if len(sys.argv) != 5:
    print('Usage: vacron_viewer.py <ip> <channel> <username> <password>')
    exit(1)

ip, channel, *auth = sys.argv[1:]

response = requests.get(f'http://{ip}/video{channel}.m4v', stream=True, auth=tuple(auth))
frame_parser = FrameParser(response)

sleep_time = 1000 / frame_parser.fps
sleep_displacement = 0.1

while True:
    try:
        frame, buffer_status = frame_parser.get_frame()
        if buffer_status == FrameParser.BUFFER_SIZE_STATUS.TOO_EMPTY: 
            sleep_time += sleep_displacement
        elif buffer_status == FrameParser.BUFFER_SIZE_STATUS.TOO_FULL: 
            sleep_time = max(0, sleep_time - sleep_displacement)

        cv2.imshow('', frame)
        cv2.waitKey(round(sleep_time))

    except KeyboardInterrupt:
        break