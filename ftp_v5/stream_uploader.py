# -*- coding:utf-8 -*-

import logging
import math
from multiprocessing.pool import ThreadPool
from cStringIO import StringIO

import ftp_v5.conf.common_config
from ftp_v5.conf.ftp_config import CosFtpConfig
from ftp_v5.multipart_upload import MultipartUpload


class FifoBuffer(object):
    def __init__(self):
        self.buf = StringIO()

    def read(self, *args, **kwargs):
        return self.buf.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        current_read_fp = self.buf.tell()
        if current_read_fp > 10 * ftp_v5.conf.common_config.MEGABYTE:
            new_buf = StringIO()
            new_buf.write(self.buf.read())
            self.buf = new_buf
            current_read_fp = 0

        self.buf.seek(0, 2)
        self.buf.write(*args, **kwargs)
        self.buf.seek(current_read_fp)

    def close(self):
        self.buf.close()

logger = logging.getLogger(__name__)


class StreamUploader(object):

    MIN_PART_SIZE = 20 * ftp_v5.conf.common_config.MEGABYTE

    def __init__(self, cos_client, bucket_name, object_name=None):
        self._cos_client = cos_client
        self._bucket_name = bucket_name
        self._key_name = object_name

        if CosFtpConfig().single_file_max_size > 40 * 1000 * ftp_v5.conf.common_config.GIGABYTE:
            raise ValueError("File size: %d is too big" % CosFtpConfig().single_file_max_size)

        self._min_part_size = int(math.ceil(CosFtpConfig().single_file_max_size / MultipartUpload.MaxiumPartNum / ftp_v5.conf.common_config.MEGABYTE) * ftp_v5.conf.common_config.MEGABYTE);

        if CosFtpConfig().single_file_max_size < StreamUploader.MIN_PART_SIZE:
            self._min_part_size = CosFtpConfig().single_file_max_size

        logger.info("Min part size: %d" % self._min_part_size)

        self._has_init = False
        self._has_commit = False
        self._buffer = FifoBuffer()
        self._buffer_len = 0
        self._multipart_uploader = None
        self._part_num = 1
        self._thread_pool = ThreadPool()            # TODO 多线程上传

    # TODO 增加上传字节数统计
    def write(self, data):
        logger.debug("Receive string with length : {0}".format(len(data)))

        self._buffer.write(data)
        self._buffer_len += len(data)

        while self._buffer_len >= self._min_part_size:
            if not self._has_init:
                response = self._cos_client.create_multipart_upload(Bucket=self._bucket_name, Key=self._key_name)
                self._multipart_uploader = MultipartUpload(self._cos_client, response)
                self._has_init = True
                self._part_num = 1

            if self._part_num % 3 == 0:
                self._thread_pool.apply(self._multipart_uploader.upload_part, (StringIO(self._buffer.read(self._min_part_size)), self._part_num) )
            else:
                self._thread_pool.apply_async(self._multipart_uploader.upload_part, (StringIO(self._buffer.read(self._min_part_size)), self._part_num) )

            self._part_num += 1
            self._buffer_len -= self._min_part_size
            logger.info("upload new part with length: {0}".format(self._min_part_size))

    def close(self):
        logger.info("Closing the stream upload...")

        if self._buffer_len != 0:
            logger.info("Simple upload")                            # 最后一个分片，采用单文件上传
            self._cos_client.put_object(Bucket=self._bucket_name,
                                        Body=self._buffer.read(self._buffer_len),
                                        Key=self._key_name)
        if self._has_init:
            self._thread_pool.close()
            self._thread_pool.join()
            self._multipart_uploader.complete_upload()

        self._buffer.close()


if __name__ == "__main__":
    pass