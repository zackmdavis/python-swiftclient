# Copyright (c) 2010-2012 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Miscellaneous utility functions for use with Swift."""
import hashlib
import hmac
import json
import logging
import time

import six

TRUE_VALUES = set(('true', '1', 'yes', 'on', 't', 'y'))
EMPTY_ETAG = 'd41d8cd98f00b204e9800998ecf8427e'


def config_true_value(value):
    """
    Returns True if the value is either True or a string in TRUE_VALUES.
    Returns False otherwise.
    This function comes from swift.common.utils.config_true_value()
    """
    return value is True or \
        (isinstance(value, six.string_types) and value.lower() in TRUE_VALUES)


def prt_bytes(bytes, human_flag):
    """
    convert a number > 1024 to printable format, either in 4 char -h format as
    with ls -lh or return as 12 char right justified string
    """

    if human_flag:
        suffix = ''
        mods = list('KMGTPEZY')
        temp = float(bytes)
        if temp > 0:
            while temp > 1023:
                try:
                    suffix = mods.pop(0)
                except IndexError:
                    break
                temp /= 1024.0
            if suffix != '':
                if temp >= 10:
                    bytes = '%3d%s' % (temp, suffix)
                else:
                    bytes = '%.1f%s' % (temp, suffix)
        if suffix == '':    # must be < 1024
            bytes = '%4s' % bytes
    else:
        bytes = '%12s' % bytes

    return bytes


def generate_temp_url(path, seconds, key, method, absolute=False):
    """Generates a temporary URL that gives unauthenticated access to the
    Swift object.

    :param path: The full path to the Swift object. Example:
    /v1/AUTH_account/c/o.
    :param seconds: The amount of time in seconds the temporary URL will
    be valid for.
    :param key: The secret temporary URL key set on the Swift cluster.
    To set a key, run 'swift post -m
    "Temp-URL-Key:b3968d0207b54ece87cccc06515a89d4"'
    :param method: A HTTP method, typically either GET or PUT, to allow for
    this temporary URL.
    :raises: ValueError if seconds is not a positive integer
    :raises: TypeError if seconds is not an integer
    :return: the path portion of a temporary URL
    """
    if seconds < 0:
        raise ValueError('seconds must be a positive integer')
    try:
        if not absolute:
            expiration = int(time.time() + seconds)
        else:
            expiration = int(seconds)
    except TypeError:
        raise TypeError('seconds must be an integer')

    standard_methods = ['GET', 'PUT', 'HEAD', 'POST', 'DELETE']
    if method.upper() not in standard_methods:
        logger = logging.getLogger("swiftclient")
        logger.warning('Non default HTTP method %s for tempurl specified, '
                       'possibly an error', method.upper())

    hmac_body = '\n'.join([method.upper(), str(expiration), path])

    # Encode to UTF-8 for py3 compatibility
    sig = hmac.new(key.encode(),
                   hmac_body.encode(),
                   hashlib.sha1).hexdigest()

    return ('{path}?temp_url_sig='
            '{sig}&temp_url_expires={exp}'.format(
                path=path,
                sig=sig,
                exp=expiration))


def parse_api_response(headers, body):
    charset = 'utf-8'
    # Swift *should* be speaking UTF-8, but check content-type just in case
    content_type = headers.get('content-type', '')
    if '; charset=' in content_type:
        charset = content_type.split('; charset=', 1)[1].split(';', 1)[0]

    return json.loads(body.decode(charset))


class NoopMD5(object):
    def __init__(self, *a, **kw):
        pass

    def update(self, *a, **kw):
        pass

    def hexdigest(self, *a, **kw):
        return ''


class ReadableToIterable(object):
    """
    Wrap a filelike object and act as an iterator.

    It is recommended to use this class only on files opened in binary mode.
    Due to the Unicode changes in python 3 files are now opened using an
    encoding not suitable for use with the md5 class and because of this
    hit the exception on every call to next. This could cause problems,
    especially with large files and small chunk sizes.
    """

    def __init__(self, content, chunk_size=65536, md5=False):
        """
        :param content: The filelike object that is yielded from.
        :param chunk_size: The max size of each yielded item.
        :param md5: Flag to enable calculating the MD5 of the content
                    as it is yielded.
        """
        self.md5sum = hashlib.md5() if md5 else NoopMD5()
        self.content = content
        self.chunk_size = chunk_size

    def get_md5sum(self):
        return self.md5sum.hexdigest()

    def __next__(self):
        """
        Both ``__next__`` and ``next`` are provided to allow compatibility
        with python 2 and python 3 and their use of ``iterable.next()``
        and ``next(iterable)`` respectively.
        """
        chunk = self.content.read(self.chunk_size)
        if not chunk:
            raise StopIteration

        try:
            self.md5sum.update(chunk)
        except TypeError:
            self.md5sum.update(chunk.encode())

        return chunk

    def next(self):
        return self.__next__()

    def __iter__(self):
        return self


class LengthWrapper(object):
    """
    Wrap a filelike object with a maximum length.

    Fix for https://github.com/kennethreitz/requests/issues/1648
    It is recommended to use this class only on files opened in binary mode.
    """
    def __init__(self, readable, length, md5=False):
        """
        :param readable: The filelike object to read from.
        :param length: The maximum amount of content to that can be read from
                       the filelike object before it is simulated to be
                       empty.
        :param md5: Flag to enable calculating the MD5 of the content
                    as it is read.
        """
        self.md5sum = hashlib.md5() if md5 else NoopMD5()
        self._length = self._remaining = length
        self._readable = readable

    def __len__(self):
        return self._length

    def get_md5sum(self):
        return self.md5sum.hexdigest()

    def read(self, *args, **kwargs):
        if self._remaining <= 0:
            return ''

        chunk = self._readable.read(*args, **kwargs)[:self._remaining]
        self._remaining -= len(chunk)

        try:
            self.md5sum.update(chunk)
        except TypeError:
            self.md5sum.update(chunk.encode())

        return chunk
