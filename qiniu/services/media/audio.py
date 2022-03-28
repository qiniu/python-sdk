#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Xiang Wang @ 2020-03-06 16:02:02


from qiniu import http 


class AudioManager(object):
    """音频处理"""

    def __init__(self, auth):
        self.auth = auth

    def avinfo(self, url):
        """获取一个文件的音视频元信息:
        接口地址: https://developer.qiniu.com/dora/api/1247/audio-and-video-metadata-information-avinfo

        Args:
            url: 音视频的url链接

        Returns:
            一个dict变量, 类似:
                {
                    "streams": [
                        {
                            "index": 0,
                            "codec_name": "h264",
                            "codec_long_name": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
                            "codec_type": "video",
                            "codec_time_base": "1/30",
                            "codec_tag_string": "avc1",
                            "codec_tag": "0x31637661",
                            "width": 1152,
                            "height": 864,
                            ...
                        },
                        {
                            "index": 1,
                            "codec_name": "aac",
                            "codec_long_name": "Advanced Audio Coding",
                            "codec_type": "audio",
                            "codec_time_base": "1/44100",
                            "codec_tag_string": "mp4a",
                            "codec_tag": "0x6134706d",
                            ...
                        }
                    ],
                    "format": {
                        "nb_streams": 2,
                        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                        "format_long_name": "QuickTime/MPEG-4/Motion JPEG 2000 format",
                        "start_time": "0.000000",
                        "duration": "6413.359589",  # 注意，duration是字符串
                        ...
                    }
                }
            一个ResponseInfo对象
        """
        return http._session_get(url + "?avinfo", {}, self.auth)
