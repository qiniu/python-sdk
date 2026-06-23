# -*- coding: utf-8 -*-
import time

from .errors import SandboxError
from .envd import connect_rpc, envd_headers, raw_envd_request


class FileType(object):
    FILE = 'file'
    DIR = 'dir'
    DIRECTORY = DIR


class FilesystemEventType(object):
    CREATE = 'create'
    WRITE = 'write'
    REMOVE = 'remove'
    RENAME = 'rename'
    CHMOD = 'chmod'


class FilesystemEvent(object):
    def __init__(self, name=None, type=None):
        self.name = name
        self.type = type

    def to_dict(self):
        return {'name': self.name, 'type': self.type}


def normalize_event_type(event_type):
    mapping = {
        'EVENT_TYPE_CREATE': FilesystemEventType.CREATE,
        'EVENT_TYPE_WRITE': FilesystemEventType.WRITE,
        'EVENT_TYPE_REMOVE': FilesystemEventType.REMOVE,
        'EVENT_TYPE_RENAME': FilesystemEventType.RENAME,
        'EVENT_TYPE_CHMOD': FilesystemEventType.CHMOD,
        1: FilesystemEventType.CREATE,
        2: FilesystemEventType.WRITE,
        3: FilesystemEventType.REMOVE,
        4: FilesystemEventType.RENAME,
        5: FilesystemEventType.CHMOD,
    }
    return mapping.get(event_type, event_type)


def normalize_entry(entry):
    entry = entry or {}
    entry_type = entry.get('type')
    if entry_type in ('FILE_TYPE_DIRECTORY', 'DIRECTORY', 'dir'):
        entry_type = 'dir'
    elif entry_type in ('FILE_TYPE_FILE', 'FILE', 'file'):
        entry_type = 'file'
    if entry_type:
        entry['type'] = entry_type
    return entry


class WatchHandle(object):
    def __init__(self, filesystem, watcher_id):
        self.filesystem = filesystem
        self.watcher_id = watcher_id
        self.watcherID = watcher_id
        self._closed = False

    def get_new_events(self, user=None, timeout=None):
        if self._closed:
            raise SandboxError('The watcher is already stopped')
        data = connect_rpc(
            self.filesystem.sandbox,
            '/filesystem.Filesystem/GetWatcherEvents',
            {'watcherId': self.watcher_id},
            user=user,
            timeout=timeout,
        )
        events = []
        for event in (data or {}).get('events', []):
            events.append(FilesystemEvent(
                name=event.get('name'),
                type=normalize_event_type(event.get('type')),
            ))
        return events

    getNewEvents = get_new_events

    def stop(self, user=None, timeout=None):
        if self._closed:
            return None
        connect_rpc(
            self.filesystem.sandbox,
            '/filesystem.Filesystem/RemoveWatcher',
            {'watcherId': self.watcher_id},
            user=user,
            timeout=timeout,
        )
        self._closed = True
        return None


class Filesystem(object):
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def read(self, path, user=None, format='text', **opts):
        url = self.sandbox.download_url(path, user=user)
        response = raw_envd_request(
            self.sandbox,
            'GET',
            url,
            headers=envd_headers(self.sandbox, user),
        )
        if format == 'bytes':
            return response.content
        return response.content.decode(opts.get('encoding', 'utf-8'))

    def read_text(self, path, user=None, **opts):
        return self.read(path, user=user, format='text', **opts)

    readText = read_text

    def write(self, path, data, user=None, **opts):
        if not isinstance(data, bytes):
            data = str(data).encode(opts.get('encoding', 'utf-8'))
        url = self.sandbox.upload_url(path, user=user)
        if opts.get('use_octet_stream'):
            response = raw_envd_request(
                self.sandbox,
                'POST',
                url,
                data=data,
                headers=envd_headers(
                    self.sandbox,
                    user,
                    {'Content-Type': 'application/octet-stream'},
                ),
            )
            return self._format_write_response(response)

        boundary = 'qiniu-sandbox-{0}'.format(int(time.time() * 1000))
        response = raw_envd_request(
            self.sandbox,
            'POST',
            url,
            data=self._multipart_body(boundary, path, data),
            headers=envd_headers(
                self.sandbox,
                user,
                {'Content-Type': 'multipart/form-data; boundary={0}'.format(
                    boundary
                )},
            ),
        )
        return self._format_write_response(response)

    def _format_write_response(self, response):
        if not response.content:
            return None
        data = response.json()
        if isinstance(data, list):
            return normalize_entry(data[0] if data else {})
        return normalize_entry(data)

    def _multipart_body(self, boundary, filename, data):
        safe_filename = str(filename).replace('\\', '\\\\').replace('"', '\\"')
        chunks = [
            '--{0}\r\n'.format(boundary).encode('utf-8'),
            (
                'Content-Disposition: form-data; name="file"; '
                'filename="{0}"\r\n'
            ).format(safe_filename).encode('utf-8'),
            b'Content-Type: application/octet-stream\r\n\r\n',
            data,
            b'\r\n',
            '--{0}--\r\n'.format(boundary).encode('utf-8'),
        ]
        return b''.join(chunks)

    def write_files(self, files, user=None, **opts):
        result = []
        for item in files or []:
            if isinstance(item, dict):
                path = item.get('path')
                data = item.get('data', item.get('content', ''))
            else:
                path, data = item
            result.append(self.write(path, data, user=user, **opts))
        return result

    writeFiles = write_files

    def get_info(self, path, user=None, timeout=None):
        data = connect_rpc(
            self.sandbox,
            '/filesystem.Filesystem/Stat',
            {'path': path},
            user=user,
            timeout=timeout,
        )
        return normalize_entry((data or {}).get('entry'))

    getInfo = get_info
    stat = get_info

    def list(self, path, depth=1, user=None, timeout=None):
        data = connect_rpc(
            self.sandbox,
            '/filesystem.Filesystem/ListDir',
            {'path': path, 'depth': depth},
            user=user,
            timeout=timeout,
        )
        return [
            normalize_entry(entry) for entry in (
                data or {}).get(
                'entries', [])]

    def exists(self, path, user=None, timeout=None):
        try:
            self.get_info(path, user=user, timeout=timeout)
            return True
        except Exception as err:
            response = getattr(err, 'response', None)
            if response is not None and getattr(
                    response, 'status_code', None) == 404:
                return False
            raise

    def make_dir(self, path, user=None, timeout=None):
        data = connect_rpc(
            self.sandbox,
            '/filesystem.Filesystem/MakeDir',
            {'path': path},
            user=user,
            timeout=timeout,
        )
        return normalize_entry((data or {}).get('entry'))

    makeDir = make_dir
    mkdir = make_dir

    def remove(self, path, user=None, timeout=None):
        connect_rpc(
            self.sandbox,
            '/filesystem.Filesystem/Remove',
            {'path': path},
            user=user,
            timeout=timeout,
        )
        return None

    def rename(self, old_path, new_path, user=None, timeout=None):
        data = connect_rpc(
            self.sandbox,
            '/filesystem.Filesystem/Move',
            {'source': old_path, 'destination': new_path},
            user=user,
            timeout=timeout,
        )
        return normalize_entry((data or {}).get('entry'))

    def watch_dir(self, path, recursive=False, user=None, timeout=None):
        data = connect_rpc(
            self.sandbox,
            '/filesystem.Filesystem/CreateWatcher',
            {'path': path, 'recursive': recursive},
            user=user,
            timeout=timeout,
        )
        watcher_id = (
            (data or {}).get('watcherId') or
            (data or {}).get('watcher_id')
        )
        return WatchHandle(self, watcher_id)

    watchDir = watch_dir
