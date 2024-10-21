import pytest

import qiniu


KB = 1024
MB = 1024 * KB
GB = 1024 * MB


# set a bucket lifecycle manually to delete prefix `test-pfop`!
# or this test will continue to occupy bucket space.
class TestPersistentFopByUpload:
    @pytest.mark.parametrize('temp_file', [10 * MB], indirect=True)
    @pytest.mark.parametrize(
        'persistent_options',
        (
            {
                'persistent_type': None,
            },
            {
                'persistent_type': 0,
            },
            {
                'persistent_type': 1,
            },
            {
                'persistent_workflow_template_id': 'test-workflow',
            },
        )
    )
    def test_pfop_with_upload(
        self,
        set_conf_default,
        qn_auth,
        bucket_name,
        temp_file,
        persistent_options,
    ):
        key = 'test-pfop/upload-file'
        persistent_type = persistent_options.get('persistent_type')
        persistent_workflow_template_id = persistent_options.get('persistent_workflow_template_id')

        upload_policy = {}

        # set pfops or tmplate id
        if persistent_workflow_template_id:
            upload_policy['persistentWorkflowTemplateID'] = persistent_workflow_template_id
        else:
            persistent_key = '_'.join([
                'test-pfop/test-pfop-by-upload',
                'type',
                str(persistent_type)
            ])
            persistent_ops = ';'.join([
                qiniu.op_save(
                    op='avinfo',
                    bucket=bucket_name,
                    key=persistent_key
                )
            ])
            upload_policy['persistentOps'] = persistent_ops

        # set persistent type
        if persistent_type is not None:
            upload_policy['persistentType'] = persistent_type

        # upload
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
        assert ret is not None, resp
        assert ret['creationDate'] is not None, resp

        if persistent_type == 1:
            assert ret['type'] == 1, resp
        elif persistent_workflow_template_id:
            assert persistent_workflow_template_id in ret['taskFrom'], resp
