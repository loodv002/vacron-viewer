from queue import Queue
from collections import deque
import io
import imageio
import threading
import requests
import cv2
import numpy as np
import time

from typing import Deque, Tuple

from multipart_mix_replace_decoder import MMR_Decoder

class FrameParser:
    def __init__(self, video_stream_response: requests.Response):
        self.frame_buffer = Queue()
        self.__multipart_decoder = MMR_Decoder(
            content_generator=video_stream_response.iter_content(1024),
            content_type=video_stream_response.headers.get('Content-Type')
        )
        self.fps = 0
        
        self.BUFFER_TIME_SEC = 5
        self.MP4_HEADERS_UPDATE_INTERVAL = 25

        self.run = True
        self.receiver_thread = threading.Thread(target=self.__stream_receiver, daemon=True)
        self.receiver_thread.start()
        while not self.fps: time.sleep(0.1)

    class BUFFER_SIZE_STATUS:
        TOO_FULL = 1
        TOO_EMPTY = 2
        MODERATE = 3

    def get_frame(self) -> Tuple[np.ndarray, BUFFER_SIZE_STATUS]:
        frame = self.frame_buffer.get()
        half_buffer_size = self.fps * self.BUFFER_TIME_SEC / 2
        queue_size = self.frame_buffer.qsize()

        if queue_size < half_buffer_size - 0.5 * self.fps:      buffer_size_status = self.BUFFER_SIZE_STATUS.TOO_EMPTY
        elif queue_size > half_buffer_size + 0.5 * self.fps:    buffer_size_status = self.BUFFER_SIZE_STATUS.TOO_FULL
        else:                                                   buffer_size_status = self.BUFFER_SIZE_STATUS.MODERATE
        
        return frame, buffer_size_status

    def __stream_receiver(self):
        stream_buffer: Deque[bytearray] = deque()
        stream_buffer.append(bytearray())

        for headers, body in self.__multipart_decoder.iter_part():
            if not self.run: break
            if headers.get('Content-Type') != 'video/h265': continue

            self.fps = int(headers.get('X-Framerate'))
            x_tag = int(headers.get('X-Tag'))
            
            stream_buffer[-1].extend(body)

            if x_tag % self.MP4_HEADERS_UPDATE_INTERVAL == 0:
                self.__update_frames(b''.join(stream_buffer))
                while len(stream_buffer) > 1: stream_buffer.popleft()
                stream_buffer.append(bytearray())

    def __update_frames(self, stream_buffer: bytearray):
        byte_stream = io.BytesIO(stream_buffer)

        video_reader = imageio.get_reader(byte_stream, format='mp4')
        frames = [frame for frame in video_reader]
        video_reader.close()

        for frame in frames[self.MP4_HEADERS_UPDATE_INTERVAL:]:
            frame = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
            self.frame_buffer.put(frame)

        while self.frame_buffer.qsize() > self.fps * self.BUFFER_TIME_SEC:
            self.frame_buffer.get()

    def stop(self):
        self.run = False
    
    def __del__(self):
        self.run = False
        