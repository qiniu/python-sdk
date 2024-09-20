import pytest

from qiniu.services.storage.bucket import BucketManager
from qiniu.region import LegacyRegion
from qiniu import build_batch_restore_ar


@pytest.fixture(scope='function')
def object_key(bucket_manager, bucket_name, rand_string):
    key_to = 'copyto_' + rand_string(8)
    bucket_manager.copy(
        bucket=bucket_name,
        key='copyfrom',
        bucket_to=bucket_name,
        key_to=key_to,
        force='true'
    )

    yield key_to

    bucket_manager.delete(bucket_name, key_to)


class TestBucketManager:
    # TODO(lihs): Move other test cases to here from test_qiniu.py
    def test_restore_ar(self, bucket_manager, bucket_name, object_key):
        ret, resp = bucket_manager.restore_ar(bucket_name, object_key, 7)
        assert not resp.ok(), resp
        ret, resp = bucket_manager.change_type(bucket_name, object_key, 2)
        assert resp.ok(), resp
        ret, resp = bucket_manager.restore_ar(bucket_name, object_key, 7)
        assert resp.ok(), resp

    @pytest.mark.parametrize(
        'cond,expect_ok',
        [
            (
                None, True
            ),
            (
                {
                    'mime': 'text/plain'
                },
                True
            ),
            (
                {
                    'mime': 'application/json'
                },
                False
            )
        ]
    )
    def test_change_status(
        self,
        bucket_manager,
        bucket_name,
        object_key,
        cond,
        expect_ok
    ):
        ret, resp = bucket_manager.change_status(bucket_name, object_key, 1, cond)
        assert resp.ok() == expect_ok, resp

    def test_mkbucketv3(self, bucket_manager, rand_string):
        # tested manually, no drop bucket API to auto cleanup
        # ret, resp = bucket_manager.mkbucketv3('py-test-' + rand_string(8).lower(), 'z0')
        # assert resp.ok(), resp
        pass

    def test_list_bucket(self, bucket_manager, bucket_name):
        ret, resp = bucket_manager.list_bucket('na0')
        assert resp.ok(), resp
        assert any(b.get('tbl') == bucket_name for b in ret)

    def test_bucket_info(self, bucket_manager, bucket_name):
        ret, resp = bucket_manager.bucket_info(bucket_name)
        assert resp.ok(), resp
        for k in [
            'protected',
            'private'
        ]:
            assert k in ret

    def test_change_bucket_permission(self, bucket_manager, bucket_name):
        ret, resp = bucket_manager.bucket_info(bucket_name)
        assert resp.ok(), resp
        original_private = ret['private']
        ret, resp = bucket_manager.change_bucket_permission(
            bucket_name,
            1 if original_private == 1 else 0
        )
        assert resp.ok(), resp
        ret, resp = bucket_manager.change_bucket_permission(
            bucket_name,
            original_private
        )
        assert resp.ok(), resp

    def test_batch_restore_ar(
        self,
        bucket_manager,
        bucket_name,
        object_key
    ):
        bucket_manager.change_type(bucket_name, object_key, 2)
        ops = build_batch_restore_ar(
            bucket_name,
            {
                object_key: 7
            }
        )
        ret, resp = bucket_manager.batch(ops)
        assert resp.status_code == 200, resp
        assert len(ret) > 0
        assert ret[0].get('code') == 200, ret[0]

    def test_compatible_with_zone(self, qn_auth, bucket_name, regions_with_real_endpoints):
        r = LegacyRegion(
            io_host='https://fake-io.python-sdk.qiniu.com',
            rs_host='https://fake-rs.python-sdk.qiniu.com',
            rsf_host='https://fake-rsf.python-sdk.qiniu.com',
            api_host='https://fake-api.python-sdk.qiniu.com'
        )
        bucket_manager = BucketManager(
            qn_auth,
            zone=r
        )

        # rs host
        ret, resp = bucket_manager.stat(bucket_name, 'python-sdk.html')
        assert resp.status_code == -1
        assert ret is None

        # rsf host
        ret, _eof, resp = bucket_manager.list(bucket_name, '', limit=10)
        assert resp.status_code == -1
        assert ret is None

        # io host
        ret, info = bucket_manager.prefetch(bucket_name, 'python-sdk.html')
        assert resp.status_code == -1
        assert ret is None

        # api host
        # no API method to test

    @pytest.mark.parametrize(
        'preferred_scheme',
        [
            None,  # default 'http'
            'http',
            'https'
        ]
    )
    def test_preferred_scheme(
        self,
        qn_auth,
        bucket_name,
        preferred_scheme
    ):
        bucket_manager = BucketManager(
            auth=qn_auth,
            preferred_scheme=preferred_scheme
        )

        ret, resp = bucket_manager.stat(bucket_name, 'python-sdk.html')

        assert ret is not None, resp
        assert resp.ok(), resp

        expect_scheme = preferred_scheme if preferred_scheme else 'http'
        assert resp.url.startswith(expect_scheme + '://'), resp.url

    def test_operation_with_regions_and_retrier(
        self,
        qn_auth,
        bucket_name,
        regions_with_fake_endpoints
    ):
        bucket_manager = BucketManager(
            auth=qn_auth,
            regions=regions_with_fake_endpoints,
        )

        ret, resp = bucket_manager.stat(bucket_name, 'python-sdk.html')

        assert ret is not None, resp
        assert resp.ok(), resp

    def test_uc_service_with_retrier(
        self,
        qn_auth,
        bucket_name,
        regions_with_fake_endpoints
    ):
        bucket_manager = BucketManager(
            auth=qn_auth,
            regions=regions_with_fake_endpoints
        )

        ret, resp = bucket_manager.list_bucket('na0')
        assert resp.ok(), resp
        assert len(ret) > 0, resp
        assert any(b.get('tbl') for b in ret), ret
