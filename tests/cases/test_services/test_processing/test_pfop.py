import pytest

from qiniu import PersistentFop, op_save


persistent_id = None


class TestPersistentFop:
    def test_pfop_execute(self, qn_auth):
        pfop = PersistentFop(qn_auth, 'testres', 'sdktest')
        op = op_save('avthumb/m3u8/segtime/10/vcodec/libx264/s/320x240', 'pythonsdk', 'pfoptest')
        ops = [
            op
        ]
        ret, resp = pfop.execute('sintel_trailer.mp4', ops, 1)
        assert resp.status_code == 200, resp
        assert ret is not None, resp
        assert ret['persistentId'] is not None, resp
        global persistent_id
        persistent_id = ret['persistentId']

    def test_pfop_get_status(self, qn_auth):
        assert persistent_id is not None
        pfop = PersistentFop(qn_auth, 'testres', 'sdktest')
        ret, resp = pfop.get_status(persistent_id)
        assert resp.status_code == 200, resp
        assert ret is not None, resp

    @pytest.mark.parametrize(
        'persistent_options',
        (
            # included by above test_pfop_execute
            # {
            #     'persistent_type': None,
            # },
            {
                'persistent_type': 0,
            },
            {
                'persistent_type': 1,
            },
            {
                'workflow_template_id': 'test-workflow',
            },
        )
    )
    def test_pfop_idle_time_task(
        self,
        set_conf_default,
        qn_auth,
        bucket_name,
        persistent_options,
    ):
        persistent_type = persistent_options.get('persistent_type')
        workflow_template_id = persistent_options.get('workflow_template_id', None)

        execute_opts = {}
        if workflow_template_id:
            execute_opts['workflow_template_id'] = workflow_template_id
        else:
            persistent_key = '_'.join([
                'test-pfop/test-pfop-by-api',
                'type',
                str(persistent_type)
            ])
            execute_opts['fops'] = [
                op_save(
                    op='avinfo',
                    bucket=bucket_name,
                    key=persistent_key
                )
            ]

        if persistent_type is not None:
            execute_opts['persistent_type'] = persistent_type

        pfop = PersistentFop(qn_auth, bucket_name)
        key = 'qiniu.png'
        ret, resp = pfop.execute(
            key,
            **execute_opts
        )

        assert resp.status_code == 200, resp
        assert ret is not None
        assert 'persistentId' in ret, resp

        ret, resp = pfop.get_status(ret['persistentId'])
        assert resp.status_code == 200, resp
        assert ret is not None
        assert ret['creationDate'] is not None, resp

        if persistent_id == 1:
            assert ret['type'] == 1, resp
        elif workflow_template_id:
            assert workflow_template_id in ret['taskFrom'], resp
