import pytest

import qiniu


KB = 1024
MB = 1024 * KB
GB = 1024 * MB


# set a bucket lifecycle manually to delete prefix `test-pfop`!
# or this test will continue to occupy bucket space.
class TestPersistentFopByUpload:
    @pytest.mark.parametrize('temp_file', [10 * MB], indirect=True)
    @pytest.mark.parametrize('persistent_type', [None, 0, 1])
    def test_pfop_with_upload(
        self,
        set_conf_default,
        qn_auth,
        bucket_name,
        temp_file,
        persistent_type
    ):
        key = 'test-pfop-upload-file'
        persistent_key = '_'.join([
            'test-pfop-by-upload',
            'type',
            str(persistent_type)
        ])
        persistent_ops = ';'.join([
            qiniu.op_save(
                op='avthumb/m3u8/segtime/10/vcodec/libx264/s/320x240',
                bucket=bucket_name,
                key=persistent_key
            )
        ])

        upload_policy = {
            'persistentOps': persistent_ops
        }

        if persistent_type is not None:
            upload_policy['persistentType'] = persistent_type

        token = qn_auth.upload_token(
            bucket_name,
            key,
            policy=upload_policy
        )
        ret, resp = qiniu.put_file(
            token,
            key,
            temp_file.path,
            check_crc=True
        )

        assert ret is not None, resp
        assert ret['key'] == key, resp
        assert 'persistentId' in ret, resp

        pfop = qiniu.PersistentFop(qn_auth, bucket_name)
        ret, resp = pfop.get_status(ret['persistentId'])
        assert resp.status_code == 200, resp
        if persistent_type == 1:
            assert ret['type'] == 1, resp
        assert ret['creationDate'] is not None, resp
