from datetime import datetime, timedelta, tzinfo

from qiniu import utils, compat


class _CN_TZINFO(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)

    def tzname(self, dt):
        return "CST"

    def dst(self, dt):
        return timedelta(0)


class TestUtils:
    def test_urlsafe(self):
        a = 'hello\x96'
        u = utils.urlsafe_base64_encode(a)
        assert compat.b(a) == utils.urlsafe_base64_decode(u)

    def test_canonical_mime_header_key(self):
        field_names = [
            ":status",
            ":x-test-1",
            ":x-Test-2",
            "content-type",
            "CONTENT-LENGTH",
            "oRiGin",
            "ReFer",
            "Last-Modified",
            "acCePt-ChArsEt",
            "x-test-3",
            "cache-control",
        ]
        expect_canonical_field_names = [
            ":status",
            ":x-test-1",
            ":x-Test-2",
            "Content-Type",
            "Content-Length",
            "Origin",
            "Refer",
            "Last-Modified",
            "Accept-Charset",
            "X-Test-3",
            "Cache-Control",
        ]
        assert len(field_names) == len(expect_canonical_field_names)
        for i in range(len(field_names)):
            assert utils.canonical_mime_header_key(field_names[i]) == expect_canonical_field_names[i]

    def test_entry(self):
        case_list = [
            {
                'msg': 'normal',
                'bucket': 'qiniuphotos',
                'key': 'gogopher.jpg',
                'expect': 'cWluaXVwaG90b3M6Z29nb3BoZXIuanBn'
            },
            {
                'msg': 'key empty',
                'bucket': 'qiniuphotos',
                'key': '',
                'expect': 'cWluaXVwaG90b3M6'
            },
            {
                'msg': 'key undefined',
                'bucket': 'qiniuphotos',
                'key': None,
                'expect': 'cWluaXVwaG90b3M='
            },
            {
                'msg': 'key need replace plus symbol',
                'bucket': 'qiniuphotos',
                'key': '012ts>a',
                'expect': 'cWluaXVwaG90b3M6MDEydHM-YQ=='
            },
            {
                'msg': 'key need replace slash symbol',
                'bucket': 'qiniuphotos',
                'key': '012ts?a',
                'expect': 'cWluaXVwaG90b3M6MDEydHM_YQ=='
            }
        ]
        for c in case_list:
            assert c.get('expect') == utils.entry(c.get('bucket'), c.get('key')), c.get('msg')

    def test_decode_entry(self):
        case_list = [
            {
                'msg': 'normal',
                'expect': {
                    'bucket': 'qiniuphotos',
                    'key': 'gogopher.jpg'
                },
                'entry': 'cWluaXVwaG90b3M6Z29nb3BoZXIuanBn'
            },
            {
                'msg': 'key empty',
                'expect': {
                    'bucket': 'qiniuphotos',
                    'key': ''
                },
                'entry': 'cWluaXVwaG90b3M6'
            },
            {
                'msg': 'key undefined',
                'expect': {
                    'bucket': 'qiniuphotos',
                    'key': None
                },
                'entry': 'cWluaXVwaG90b3M='
            },
            {
                'msg': 'key need replace plus symbol',
                'expect': {
                    'bucket': 'qiniuphotos',
                    'key': '012ts>a'
                },
                'entry': 'cWluaXVwaG90b3M6MDEydHM-YQ=='
            },
            {
                'msg': 'key need replace slash symbol',
                'expect': {
                    'bucket': 'qiniuphotos',
                    'key': '012ts?a'
                },
                'entry': 'cWluaXVwaG90b3M6MDEydHM_YQ=='
            }
        ]
        for c in case_list:
            bucket, key = utils.decode_entry(c.get('entry'))
            assert bucket == c.get('expect', {}).get('bucket'), c.get('msg')
            assert key == c.get('expect', {}).get('key'), c.get('msg')

    def test_dt2ts(self):
        dt = datetime(year=2011, month=8, day=3, tzinfo=_CN_TZINFO())
        expect = 1312300800
        assert utils.dt2ts(dt) == expect

        base_dt = datetime(year=2011, month=8, day=3)
        now_dt = datetime.now()
        assert int((now_dt - base_dt).total_seconds()) == utils.dt2ts(now_dt) - utils.dt2ts(base_dt)
