import os
from collections import namedtuple
from hashlib import new as hashlib_new

import tempfile
import pytest

from qiniu.compat import json, is_py2
from qiniu import (
    Zone,
    config as qn_config,
    set_default,
    put_file,
    put_data,
    put_stream
)
from qiniu.services.storage.uploader import _form_put

KB = 1024
MB = 1024 * KB
GB = 1024 * MB


@pytest.fixture(scope='session')
def valid_up_host(access_key, bucket_name):
    zone = Zone()
    try:
        hosts = json.loads(
            zone.bucket_hosts(access_key, bucket_name)
        ).get('hosts')
        up_host = 'https://' + hosts[0].get('up', {}).get('domains')[0]
    except IndexError:
        up_host = 'https://upload.qiniup.com'
    return up_host


CommonlyOptions = namedtuple(
    'CommonlyOptions',
    [
        'mime_type',
        'params',
        'metadata'
    ]
)


@pytest.fixture()
def commonly_options(request):
    res = CommonlyOptions(
        mime_type='text/plain',
        params={'x:a': 'a'},
        metadata={
            'x-qn-meta-name': 'qiniu',
            'x-qn-meta-age': '18'
        }
    )
    if hasattr(request, 'params'):
        res = res._replace(**request.params)
    yield res


@pytest.fixture(scope='function')
def set_default_up_host_zone(request, valid_up_host):
    zone_args = {
        'up_host': valid_up_host,
    }
    if hasattr(request, 'param') and request.param is not None:
        zone_args = {
            'up_host': request.param,
            'up_host_backup': valid_up_host
        }
    set_default(
        default_zone=Zone(**zone_args)
    )
    yield
    set_default(default_zone=Zone())
    qn_config._is_customized_default['default_zone'] = False


TempFile = namedtuple(
    'TempFile',
    [
        'path',
        'md5',
        'name',
        'size'
    ]
)


@pytest.fixture(scope='function')
def temp_file(request):
    size = 4 * KB
    if hasattr(request, 'param'):
        size = request.param

    tmp_file_path = tempfile.mktemp()
    chunk_size = 4 * KB

    md5_hasher = hashlib_new('md5')
    with open(tmp_file_path, 'wb') as f:
        remaining_bytes = size
        while remaining_bytes > 0:
            chunk = os.urandom(min(chunk_size, remaining_bytes))
            f.write(chunk)
            md5_hasher.update(chunk)
            remaining_bytes -= len(chunk)

    yield TempFile(
        path=tmp_file_path,
        md5=md5_hasher.hexdigest(),
        name=os.path.basename(tmp_file_path),
        size=size
    )

    try:
        os.remove(tmp_file_path)
    except Exception:
        pass


class TestUploadFuncs:
    def test_put(self, qn_auth, bucket_name):
        key = 'a\\b\\c"hello'
        data = 'hello bubby!'
        token = qn_auth.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        print(info)
        assert ret['key'] == key

    def test_put_crc(self, qn_auth, bucket_name):
        key = ''
        data = 'hello bubby!'
        token = qn_auth.upload_token(bucket_name, key)
        ret, info = put_data(token, key, data, check_crc=True)
        print(info)
        assert ret['key'] == key

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_file(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        get_remote_object_headers_and_md5
    ):
        key = 'test_file'

        token = qn_auth.upload_token(bucket_name, key)
        ret, info = put_file(
            token,
            key,
            temp_file.path,
            mime_type=commonly_options.mime_type,
            check_crc=True
        )

        _, actual_md5 = get_remote_object_headers_and_md5(key=key)

        assert ret['key'] == key, info
        assert actual_md5 == temp_file.md5

    def test_put_with_invalid_crc(self, qn_auth, bucket_name):
        key = 'test_invalid'
        data = 'hello bubby!'
        crc32 = 'wrong crc32'
        token = qn_auth.upload_token(bucket_name)
        ret, info = _form_put(token, key, data, None, None, crc=crc32)
        assert ret is None, info
        assert info.status_code == 400, info

    def test_put_without_key(self, qn_auth, bucket_name):
        key = None
        data = 'hello bubby!'
        token = qn_auth.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        print(info)
        assert ret['hash'] == ret['key']

        data = 'hello bubby!'
        token = qn_auth.upload_token(bucket_name, 'nokey2')
        ret, info = put_data(token, None, data)
        print(info)
        assert ret is None
        assert info.status_code == 403  # key not match

    @pytest.mark.parametrize(
        'set_default_up_host_zone',
        [
            'http://fake.qiniu.com',
            None
        ],
        indirect=True
    )
    def test_without_read_without_seek_retry(self, set_default_up_host_zone, qn_auth, bucket_name):
        key = 'retry'
        data = 'hello retry!'
        token = qn_auth.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        print(info)
        assert ret['key'] == key
        assert ret['hash'] == 'FlYu0iBR1WpvYi4whKXiBuQpyLLk'

    @pytest.mark.parametrize('temp_file', [30 * MB], indirect=True)
    def test_put_data_without_fname(
        self,
        qn_auth,
        bucket_name,
        is_travis,
        temp_file
    ):
        if is_travis:
            return
        key = 'test_putData_without_fname'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_data(token, key, input_stream)
            print(info)
            assert ret is not None

    @pytest.mark.parametrize('temp_file', [30 * MB], indirect=True)
    def test_put_data_with_empty_fname(
        self,
        qn_auth,
        bucket_name,
        is_travis,
        temp_file,
        commonly_options
    ):
        if is_travis:
            return
        key = 'test_putData_without_fname1'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_data(
                token,
                key,
                input_stream,
                commonly_options.params,
                commonly_options.mime_type,
                False,
                None,
                ''
            )
            print(info)
            assert ret is not None

    @pytest.mark.parametrize('temp_file', [30 * MB], indirect=True)
    def test_put_data_with_space_only_fname(
        self,
        qn_auth,
        bucket_name,
        is_travis,
        temp_file,
        commonly_options
    ):
        if is_travis:
            return
        key = 'test_putData_without_fname2'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_data(
                token,
                key,
                input_stream,
                commonly_options.params,
                commonly_options.mime_type,
                False,
                None,
                '  '
            )
            print(info)
            assert ret is not None

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_file_with_metadata(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        bucket_manager,
        get_remote_object_headers_and_md5
    ):
        key = 'test_file_with_metadata'
        token = qn_auth.upload_token(bucket_name, key)
        ret, info = put_file(token, key, temp_file.path, metadata=commonly_options.metadata)
        _, actual_md5 = get_remote_object_headers_and_md5(key=key)
        assert ret['key'] == key
        assert actual_md5 == temp_file.md5

        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    def test_put_data_with_metadata(
        self,
        qn_auth,
        bucket_name,
        commonly_options,
        bucket_manager
    ):
        key = 'put_data_with_metadata'
        data = 'hello metadata!'
        token = qn_auth.upload_token(bucket_name, key)
        ret, info = put_data(token, key, data, metadata=commonly_options.metadata)
        assert ret['key'] == key
        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_file_with_callback(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        bucket_manager,
        upload_callback_url,
        get_remote_object_headers_and_md5
    ):
        key = 'test_file_with_callback'
        policy = {
            'callbackUrl': upload_callback_url,
            'callbackBody': '{"custom_vars":{"a":$(x:a)},"key":$(key),"hash":$(etag)}',
            'callbackBodyType': 'application/json',
        }
        token = qn_auth.upload_token(bucket_name, key, policy=policy)
        ret, info = put_file(
            token,
            key,
            temp_file.path,
            metadata=commonly_options.metadata,
            params=commonly_options.params,
        )
        _, actual_md5 = get_remote_object_headers_and_md5(key=key)
        assert ret['key'] == key
        assert actual_md5 == temp_file.md5
        assert ret['custom_vars']['a'] == 'a'

        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    def test_put_data_with_callback(
        self,
        qn_auth,
        bucket_name,
        commonly_options,
        bucket_manager,
        upload_callback_url
    ):
        key = 'put_data_with_metadata'
        data = 'hello metadata!'
        policy = {
            'callbackUrl': upload_callback_url,
            'callbackBody': '{"custom_vars":{"a":$(x:a)},"key":$(key),"hash":$(etag)}',
            'callbackBodyType': 'application/json',
        }
        token = qn_auth.upload_token(bucket_name, key, policy=policy)
        ret, info = put_data(
            token,
            key,
            data,
            metadata=commonly_options.metadata,
            params=commonly_options.params
        )
        assert ret['key'] == key
        assert ret['custom_vars']['a'] == 'a'
        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'


class TestResumableUploader:
    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_stream(self, qn_auth, bucket_name, temp_file, commonly_options):
        key = 'test_file_r'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=None,
                version=None,
                bucket_name=None
            )
            assert ret['key'] == key

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_stream_v2_without_bucket_name(self, qn_auth, bucket_name, temp_file, commonly_options):
        key = 'test_file_r'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=1024 * 1024 * 10,
                version='v2'
            )
            assert ret['key'] == key

    @pytest.mark.parametrize(
        'temp_file',
        [
            2 * MB + 1,
            4 * MB,
            10 * MB + 1
        ],
        ids=[
            '2MB+',
            '4MB',
            '10MB+'
        ],
        indirect=True
    )
    def test_put_stream_v2(self, qn_auth, bucket_name, temp_file, commonly_options):
        key = 'test_file_r'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=1024 * 1024 * 4,
                version='v2',
                bucket_name=bucket_name
            )
            assert ret['key'] == key

    @pytest.mark.parametrize('temp_file', [4 * MB + 1], indirect=True)
    def test_put_stream_v2_without_key(self, qn_auth, bucket_name, temp_file, commonly_options):
        part_size = 4 * MB
        key = None
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=part_size,
                version='v2',
                bucket_name=bucket_name
            )
            assert ret['key'] == ret['hash']

    @pytest.mark.parametrize('temp_file', [4 * MB + 1], indirect=True)
    def test_put_stream_v2_with_empty_return_body(self, qn_auth, bucket_name, temp_file, commonly_options):
        part_size = 4 * MB
        key = 'test_file_empty_return_body'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key, policy={'returnBody': ' '})
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=part_size,
                version='v2',
                bucket_name=bucket_name
            )
            assert info.status_code == 200
            assert ret == {}

    @pytest.mark.parametrize('temp_file', [4 * MB + 1], indirect=True)
    def test_big_file(self, qn_auth, bucket_name, temp_file, commonly_options):
        key = 'big'
        token = qn_auth.upload_token(bucket_name, key)

        ret, info = put_file(
            token,
            key,
            temp_file.path,
            commonly_options.params,
            commonly_options.mime_type,
            progress_handler=lambda progress, total: progress
        )
        print(info)
        assert ret['key'] == key

    @pytest.mark.parametrize(
        'set_default_up_host_zone',
        [
            'http://fake.qiniu.com',
            None
        ],
        indirect=True
    )
    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_retry(
        self,
        set_default_up_host_zone,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        get_remote_object_headers_and_md5
    ):
        key = 'test_file_r_retry'
        token = qn_auth.upload_token(bucket_name, key)
        ret, info = put_file(
            token,
            key,
            temp_file,
            commonly_options.params,
            commonly_options.mime_type
        )
        _, actual_md5 = get_remote_object_headers_and_md5(key=key)
        assert ret['key'] == key, info
        assert actual_md5 == temp_file.md5

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_stream_with_key_limits(self, qn_auth, bucket_name, temp_file, commonly_options):
        key = 'test_file_r'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key, policy={'keylimit': ['test_file_d']})
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type
            )
            assert info.status_code == 403
            token = qn_auth.upload_token(
                bucket_name,
                key,
                policy={'keylimit': ['test_file_d', 'test_file_r']}
            )
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type
            )
            assert info.status_code == 200

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_stream_with_metadata(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        bucket_manager
    ):
        key = 'test_put_stream_with_metadata'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=None,
                version=None,
                bucket_name=None,
                metadata=commonly_options.metadata
            )
            assert ret['key'] == key
        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    @pytest.mark.parametrize('temp_file', [4 * MB + 1], indirect=True)
    def test_put_stream_v2_with_metadata(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        bucket_manager
    ):
        part_size = 4 * MB
        key = 'test_put_stream_v2_with_metadata'
        with open(temp_file.path, 'rb') as input_stream:
            token = qn_auth.upload_token(bucket_name, key)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=part_size,
                version='v2',
                bucket_name=bucket_name,
                metadata=commonly_options.metadata
            )
            assert ret['key'] == key
        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    @pytest.mark.parametrize('temp_file', [64 * KB], indirect=True)
    def test_put_stream_with_callback(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        bucket_manager,
        upload_callback_url
    ):
        key = 'test_put_stream_with_callback'
        with open(temp_file.path, 'rb') as input_stream:
            policy = {
                'callbackUrl': upload_callback_url,
                'callbackBody': '{"custom_vars":{"a":$(x:a)},"key":$(key),"hash":$(etag)}',
                'callbackBodyType': 'application/json',
            }
            token = qn_auth.upload_token(bucket_name, key, policy=policy)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=None,
                version=None,
                bucket_name=None,
                metadata=commonly_options.metadata
            )
            assert ret['key'] == key
            assert ret['custom_vars']['a'] == 'a'
        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    @pytest.mark.parametrize('temp_file', [4 * MB + 1], indirect=True)
    def test_put_stream_v2_with_callback(
        self,
        qn_auth,
        bucket_name,
        temp_file,
        commonly_options,
        bucket_manager,
        upload_callback_url
    ):
        part_size = 4 * MB
        key = 'test_put_stream_v2_with_metadata'
        with open(temp_file.path, 'rb') as input_stream:
            policy = {
                'callbackUrl': upload_callback_url,
                'callbackBody': '{"custom_vars":{"a":$(x:a)},"key":$(key),"hash":$(etag)}',
                'callbackBodyType': 'application/json',
            }
            token = qn_auth.upload_token(bucket_name, key, policy=policy)
            ret, info = put_stream(
                token,
                key,
                input_stream,
                temp_file.name,
                temp_file.size,
                None,
                commonly_options.params,
                commonly_options.mime_type,
                part_size=part_size,
                version='v2',
                bucket_name=bucket_name,
                metadata=commonly_options.metadata
            )
            assert ret['key'] == key
            assert ret['custom_vars']['a'] == 'a'
        ret, info = bucket_manager.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    @pytest.mark.parametrize('temp_file', [30 * MB], indirect=True)
    @pytest.mark.parametrize('version', ['v1', 'v2'])
    def test_resume_upload(self, bucket_name, qn_auth, temp_file, version):
        key = 'test_resume_upload_{}'.format(version)
        part_size = 4 * MB

        def mock_fail(uploaded_size, _total_size):
            if uploaded_size > 10 * MB:
                raise Exception('Mock Fail')

        try:
            token = qn_auth.upload_token(bucket_name, key)
            try:
                _ret, _into = put_file(
                    up_token=token,
                    key=key,
                    file_path=temp_file.path,
                    hostscache_dir=None,
                    part_size=part_size,
                    version=version,
                    bucket_name=bucket_name,
                    progress_handler=mock_fail
                )
            except Exception as e:
                if 'Mock Fail' not in str(e):
                    raise e
        except IOError:
            if is_py2:
                # https://github.com/pytest-dev/pytest/issues/2370
                # https://github.com/pytest-dev/pytest/pull/3305
                pass

        def should_start_from_resume(uploaded_size, _total_size):
            assert uploaded_size // part_size >= 3

        token = qn_auth.upload_token(bucket_name, key)
        ret, into = put_file(
            up_token=token,
            key=key,
            file_path=temp_file.path,
            hostscache_dir=None,
            part_size=part_size,
            version=version,
            bucket_name=bucket_name,
            progress_handler=should_start_from_resume
        )
        assert ret['key'] == key
