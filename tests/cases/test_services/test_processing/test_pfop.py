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
        assert ret['persistentId'] is not None, resp
        global persistent_id
        persistent_id = ret['persistentId']

    def test_pfop_get_status(self, qn_auth):
        assert persistent_id is not None
        pfop = PersistentFop(qn_auth, 'testres', 'sdktest')
        ret, resp = pfop.get_status(persistent_id)
        assert resp.status_code == 200, resp
        assert ret is not None, resp

    def test_pfop_idle_time_task(self, set_conf_default, qn_auth):
        persistence_key = 'python-sdk-pfop-test/test-pfop-by-api'

        key = 'sintel_trailer.mp4'
        pfop = PersistentFop(qn_auth, 'testres')
        ops = [
            op_save(
                op='avthumb/m3u8/segtime/10/vcodec/libx264/s/320x240',
                bucket='pythonsdk',
                key=persistence_key
            )
        ]
        ret, resp = pfop.execute(key, ops, force=1, persistent_type=1)
        assert resp.status_code == 200, resp
        assert 'persistentId' in ret, resp

        ret, resp = pfop.get_status(ret['persistentId'])
        assert resp.status_code == 200, resp
        assert ret['type'] == 1, resp
        assert ret['creationDate'] is not None, resp
