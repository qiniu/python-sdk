# -*- coding: utf-8 -*-
from __future__ import print_function

import uuid

from qiniu.services.sandbox import Sandbox
from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    source = create_sandbox(timeout=300)
    restored = None
    snapshot_id = None
    # Persist this key in your application before capture. Reuse it and the same
    # body after a timeout; a new key means a new capture, even for the same name.
    capture_key = str(uuid.uuid4())
    name = 'python-sdk-snapshot-{0}:v1'.format(capture_key)
    try:
        source.files.write('/home/user/snapshot-demo.txt', 'saved by python sdk')
        print('capture key:', capture_key)
        snapshot = source.create_snapshot(
            capture_key, memory=False, name=name)
        snapshot_id = snapshot['snapshotID']
        print('snapshot:', snapshot_id, snapshot['names'])

        # Replaying a completed capture returns the original snapshot.
        replay = source.create_snapshot(capture_key, memory=False, name=name)
        assert replay['snapshotID'] == snapshot_id
        next_token = None
        while True:
            page = source.client.list_snapshots(
                sandbox_id=source.sandbox_id, name=name, limit=1,
                next_token=next_token)
            print('snapshots:', page['items'])
            next_token = page['nextToken']
            if not next_token:
                break
        print('tags:', source.client.list_template_tags(snapshot_id))

        restored = Sandbox.create(snapshot_id, client=source.client, timeout=300)
        restored.wait_for_ready()
        print('restored file:', restored.files.read_text('/home/user/snapshot-demo.txt'))
    finally:
        cleanup_sandbox(restored)
        cleanup_sandbox(source)
        if snapshot_id:
            source.client.delete_template(snapshot_id)
            print('snapshot deleted:', snapshot_id)
        else:
            print('If capture outcome is unknown, investigate with list_snapshots '
                  'using name {0} and retry with key {1}; do not change the key.'
                  .format(name, capture_key))


if __name__ == '__main__':
    run_example(main)
