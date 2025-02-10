from typing import Generator, Dict, Tuple

class MMR_Decoder:
    def __init__(self, content_generator: Generator[bytes, None, None], content_type: str):
        self.content_generator = content_generator
        self.content_type = content_type
        
        # Multipart boundary, without '\r\n--' prefix and '\r\n' suffix.
        self.boundary = content_type.split('boundary=')[-1]
        if self.boundary.startswith('--'): self.boundary = self.boundary[2:]
        self.__next_boundary = f''

        self.buffer = bytearray()

    def iter_part(self) -> Generator[Tuple[Dict[str, str], bytearray | bytes], None, None]:
        for chunk in self.content_generator:
            self.buffer.extend(chunk)

            while self.__part_ready(self.buffer):
                yield self.__get_part_headers(self.buffer), self.__get_part_body(self.buffer)

                self.buffer = self.__remove_part(self.buffer)
        
        if self.__part_headers_ready(self.buffer):
            yield self.__get_part_headers(self.buffer), self.__get_part_body(self.buffer)

    @staticmethod
    def __part_headers_ready(partial_part_content: bytearray | bytes):
        return b'\r\n\r\n' in partial_part_content
    
    @staticmethod
    def __get_part_headers(part_content: bytearray | bytes) -> Dict[str, str]:
        if not (part_content.startswith(b'--')): exit()

        header_bytes = part_content.split(b'\r\n\r\n')[0]
        header_lines = header_bytes.split(b'\r\n')

        headers = {}
        for line in header_lines:
            if b':' not in line: continue
            colon_index = line.index(b':')
            header_key = line[:colon_index].decode()
            header_value = line[colon_index+1:].strip().decode()
            headers[header_key] = header_value

        return headers
    
    '''
    A part is ready if `__part_ready` is True or content reach EOF.
    '''
    @classmethod
    def __part_ready(cls, partial_part_content: bytearray | bytes) -> bool:
        if not cls.__part_headers_ready(partial_part_content): return False

        headers = cls.__get_part_headers(partial_part_content)
        body_start_index = partial_part_content.index(b'\r\n\r\n') + 4

        if 'Content-Length' in headers:
            body_length = int(headers.get('Content-Length'))
            available_body_length = len(partial_part_content) - body_start_index
            return available_body_length >= body_length
        
        boundary = partial_part_content.split(b'\r\n')[0] # with prefix '--'
        next_boundary = b'\r\n' + boundary + b'\r\n'
        return next_boundary in partial_part_content
    
    @classmethod
    def __get_part_body(cls, part_content: bytearray | bytes) -> bytearray | bytes:
        headers = cls.__get_part_headers(part_content)
        body_start_index = part_content.index(b'\r\n\r\n') + 4

        if 'Content-Length' in headers:
            body_length = int(headers.get('Content-Length'))
            return part_content[body_start_index : body_start_index + body_length]
        
        boundary = part_content.split(b'\r\n')[0] # with prefix '--'
        next_boundary = b'\r\n' + boundary + b'\r\n'
        body_end_index = part_content.index(next_boundary.encode())
        return part_content[body_start_index : body_end_index]
    
    @classmethod
    def __remove_part(cls, part_content: bytearray | bytes) -> bytearray | bytes:
        headers = cls.__get_part_headers(part_content)
        body_start_index = part_content.index(b'\r\n\r\n') + 4

        if 'Content-Length' in headers:
            body_length = int(headers.get('Content-Length'))
            body_end_index = body_start_index + body_length
        else:
            boundary = part_content.split(b'\r\n')[0] # with prefix '--'
            next_boundary = b'\r\n' + boundary + b'\r\n'
            body_end_index = part_content.index(next_boundary.encode())

        if part_content[body_end_index : body_end_index+2] == b'\r\n': body_end_index += 2
        return part_content[body_end_index:]