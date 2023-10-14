import math
import os


class PagedLog:
    def __init__(self, log_file, page_size=10 * 1024):
        with open(log_file, 'r', encoding='utf-8') as f:
            size = f.seek(0, os.SEEK_END)
            self.page_num = math.ceil(size / page_size)
        self.log_file = log_file
        self.page_size = page_size
        self.page_range = range(1, self.page_num + 1)
        self.current = 1
        self.max_display_page = 10

    @property
    def right_offset(self):
        return max(self.current + self.max_display_page // 2, self.max_display_page)

    @property
    def left_offset(self):
        offset = self.current - self.max_display_page // 2
        if offset < 0:
            offset = 0
        return offset

    @property
    def max_offset(self):
        return self.page_num - self.max_display_page

    @property
    def real_page_size(self):
        return self.page_size // 1024

    def read_page(self, page=0):
        if page == 0:
            page = self.page_num
        if self.page_num == 0:
            return "log file is empty"
        if page > self.page_num or page < 1:
            return f"page({page}) out of range"
        self.current = page
        with open(self.log_file, 'r', encoding='utf-8') as f:
            f.seek((page - 1) * self.page_size, os.SEEK_SET)
            log = f.read(self.page_size)
        return log
