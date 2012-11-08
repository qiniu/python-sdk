# -*- encoding: utf-8 -*-

from abc import ABCMeta, abstractmethod
import base64
import zlib
import httplib2
import config
import os

try:
    import json
except ImportError:
    import simplejson as json

InvalidCtx = 701  # 无效的上下文，断点续传校验失败


def __crc32(body):
    return zlib.crc32(body) & 0xFFFFFFFF


class Error(Exception):
    pass


class CallRet(object):
    def __init__(self, code, content):
        self.code, self.content = code, content

    def ok(self):
        return self.code / 100 == 2


class Client(object):
    """docstring for Client"""
    def __init__(self, upToken):
        self.upToken = upToken

    def CallWithString(self, url, bodyString, bodyLength, _from=0):
        s = bodyString[_from: _from + bodyLength]
        headers = {}
        headers['Authorization'] = 'UpToken %s' % (self.upToken)
        headers['Content-Type'] = 'application/octet-stream'
        headers['Content-Length'] = str(bodyLength)
        print '#################'
        print str(url)
        print headers
        print '#################'
        try:
            resp, content = httplib2.Http('').request(str(url), 'POST', body=s, headers=headers)
        except Exception, e:
            return CallRet(599, str(e))

        code = resp['status']
        return CallRet(int(code), content)

##################################################################################################


class BlockProgressNotifier(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def notify(self, blockIndex, blockProgress=None):
        pass


class ProgressNotifier(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def notify(self, blockIndex, checksum=None):
        pass


class BlockProgress(object):
    def __init__(self):
        self.ctx, self.offset, self.restSize = None, None, None


class ResumablePutRet(CallRet):
    def __init__(self, callRet):
        CallRet.__init__(self, callRet.code, callRet.content)
        if callRet.ok() and callRet.content != None and callRet.content != '':
            self.ctx, self.checksum, self.crc32 = self.__unmarshal(callRet.content)

    def __unmarshal(self, content):
        m = json.loads(content)
        return (str(m.get('ctx')), str(m.get('checksum')), int(m.get('crc32')))


class UpService(object):
    def __init__(self, client):
        self.conn = client

    def makeBlock(self, blockSize, body, bodyLength):
        '''
        @param long blockSize
        @param file body
        @param long bodyLength
        @return
        '''
        url = config.UP_HOST + '/mkblk/' + str(blockSize)
        callRet = self.conn.CallWithString(url, body, bodyLength)
        return ResumablePutRet(callRet)

    def putBlock(self, blockSize, ctx, offset, body, bodyLength):
        '''
        put the chunk data into the
        @param blockSize
        @param ctx
        @param offset
        @param body
        @param bodyLength
        '''
        url = config.UP_HOST + '/bput/' + ctx + '/' + str(offset)
        callRet = self.conn.CallWithString(url, body, bodyLength)
        return ResumablePutRet(callRet)

    def makeFile(self, entryURI, fsize, params, callbackParams, checksums):

        if callbackParams != None and callbackParams != '':
            params += "/params/" + base64.urlsafe_b64encode(callbackParams)

        url = config.UP_HOST + '/rs-mkfile/' + base64.urlsafe_b64encode(entryURI) + '/fsize/' + str(fsize) + params

        body = ''
        for k, c in enumerate(checksums):
            body += base64.urlsafe_b64decode(c)

        callRet = self.conn.CallWithString(url, body, len(body))
        return callRet

    def blockCount(self, fsize):
        return (fsize + config.BLOCK_SIZE - 1) / config.BLOCK_SIZE

    def resumablePutBlock(self, localFile, blockIndex, blockSize, chunkSize, retryTimes, blockProgress, blockProgressNotifier):
        ret = None

        if blockProgress.ctx == None or blockProgress.ctx == '':
            bodyLength = blockSize
            if blockSize > chunkSize:
                bodyLength = chunkSize

            try:
                localFile.seek(config.BLOCK_SIZE * blockIndex)
                body = localFile.read(bodyLength)
                if len(body) != bodyLength:
                    return ResumablePutRet(CallRet(400, 'Read nothing'))

                # make a new block and put the first chunk data
                ret = self.makeBlock(blockSize, body, bodyLength)
                if not ret.ok():
                    return ret

                if ret.crc32 != __crc32(body):
                    ret.code = 400
                    return ret
            except Exception, e:
                return ResumablePutRet(CallRet(599, str(e)))

            blockProgress.ctx = ret.ctx
            blockProgress.offset = bodyLength
            blockProgress.restSize = blockSize - bodyLength

            blockProgressNotifier.notify(blockIndex, blockProgress=blockProgress)

        elif blockProgress.offset + blockProgress.restSize != blockSize:
            return ResumablePutRet(CallRet(400, 'Invalid arg. File length does not match'))

        while blockProgress.restSize > 0:
            bodyLength = blockProgress.restSize
            if chunkSize < blockProgress.restSize:
                bodyLength = chunkSize

            succeed = False
            for i in range(retryTimes):
                try:
                    localFile.seek(blockIndex * config.BLOCK_SIZE + blockProgress.offset)
                    body = localFile.read(bodyLength)
                    if len(body) != bodyLength:
                        return ResumablePutRet(CallRet(400, 'Read nothing'))

                    ret = self.putBlock(blockSize, blockProgress.ctx, blockProgress.offset, body, bodyLength)
                    if ret.ok():
                        if ret.crc32 == __crc32(body):
                            blockProgress.ctx = ret.ctx
                            blockProgress.offset += bodyLength
                            blockProgress.restSize -= bodyLength
                            blockProgressNotifier.notify(blockIndex, blockProgress=blockProgress)
                            succeed = True
                            break
                        else:
                            ret.code, ret.content = 400, 'crc32 check failed.'
                    elif ret.code == 701:
                        # error occurs, We should roll back to the latest block that uploaded successfully,
                        # and put the whole block that currently failed from the first chunk again.
                        # For convenient, we just fabricate a progress with empty context.
                        blockProgress.ctx = ''
                        blockProgressNotifier.notify(blockIndex, blockProgress=blockProgress)
                        return ret

                except Exception:
                    pass

            if not succeed:
                break

        if ret == None:
            ret = ResumablePutRet(CallRet(400, None))

        return ret

    def resumablePut(self, localFile, fsize, checksums, blockProgresses, progressNotifier, blockProgressNotifier):
        blockCount = self.blockCount(fsize)
        print 'blockCount', blockCount

        if len(checksums) != blockCount or len(blockProgresses) != blockCount:
            return ResumablePutRet(CallRet(400, 'Invalid arg. Unexpected block count.'))

        for i in range(blockCount):
            if checksums[i] == None or checksums[i] == '':
                blockIndex = i
                blockSize = config.BLOCK_SIZE
                if blockIndex == blockCount - 1:
                    blockSize = fsize - config.BLOCK_SIZE * blockIndex

                if blockProgresses[i] == None:
                    blockProgresses[i] = BlockProgress()

                ret = self.resumablePutBlock(localFile,
                    blockIndex, blockSize,
                    config.PUT_CHUNK_SIZE, config.PUT_RETRY_TIMES,
                    blockProgresses[i], blockProgressNotifier)

                if not ret.ok():
                    return ret

                checksums[i] = ret.checksum
                progressNotifier.notify(i, checksum=checksums[i])

        return ResumablePutRet(CallRet(200, None))


#############################################################################

def __resumablePutFile(upService,
                    checksums, blockProgresses,
                    progressNotifier, blockProgressNotifier,
                    bucketName, key, mimeType,
                    localFile, fsize,
                    customMeta, customerId, callbackParams):  # Exception
    ret = upService.resumablePut(localFile, fsize, checksums, blockProgresses,
            progressNotifier, blockProgressNotifier)

    if not ret.ok():
        return ret

    if mimeType == None or mimeType == '':
        mimeType = 'application/octet-stream'

    params = '/mimeType/' + base64.urlsafe_b64encode(mimeType)

    if customMeta != None and customMeta != '':
        params += '/meta/' + base64.urlsafe_b64decode(customMeta)

    if customerId != None:
        params += '/customer/' + str(customerId)

    entryURI = bucketName + ':' + key
    callRet = upService.makeFile(entryURI, fsize, params, callbackParams, checksums)
    return callRet


class __ResumableNotifier(BlockProgressNotifier, ProgressNotifier):
    def __init__(self, progressFilePath):
        self.fh = open(progressFilePath, 'a')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.fh.close()

    def write(self, s):
        self.fh.write(s)

    def notify(self, blockIdx, checksum=None, blockProgress=None):
        if checksum == None and blockProgress == None:
            raise Error('checksum == None and blockProgress == None')

        if checksum != None:
            doc = {"block": blockIdx, "checksum": checksum}
            try:
                s = json.dumps(doc)
                self.write(s + '\r\n')
            except Exception, e:
                print e

        if blockProgress != None:
            m = {
                "ctx": blockProgress.ctx,
                "offset": blockProgress.offset,
                "restSize": blockProgress.restSize
            }
            doc = {
                "block": blockIdx,
                "progress": m,
            }
            try:
                s = json.dumps(doc)
                self.write(s + '\r\n')
            except Exception, e:
                print e


def resumablePutFile(upService,
                    bucketName, key, mimeType,
                    inputFilePath,
                    customMeta=None, customId=None, callBackParams=None, progressFilePath=None):
    callRet = None
    try:
        with open(inputFilePath, 'r') as f:
            fsize = os.path.getsize(inputFilePath)
            blockCount = upService.blockCount(fsize)
            if progressFilePath == None or progressFilePath == '':
                progressFilePath = inputFilePath + '.progress' + str(fsize)
            print 'fsize = ', fsize
            checksums = [None for i in range(blockCount)]
            blockProgresses = [None for i in range(blockCount)]

            try:
                __readProgress(progressFilePath, checksums, blockProgresses, blockCount)
            except IOError, e:
                print e

            with __ResumableNotifier(progressFilePath) as notif:
                callRet = __resumablePutFile(upService,
                                            checksums, blockProgresses,
                                            notif, notif,
                                            bucketName, key, mimeType,
                                            f, fsize,
                                            customMeta, customId, callBackParams)
    except Exception, e:
        print e

    return callRet


def __readProgress(filePath, checksums, blockProgresses, blockCount):  # IOError
    with open(filePath) as fi:
        while True:
            line = fi.readline()
            if len(line) == 0:
                break

            m = json.loads(line)
            block = m.get('block')
            if block == None:
                break

            blockIdx = int(block)
            if blockIdx < 0 or blockIdx > blockCount:
                break

            checksum = m.get('checksum')
            if checksum != None:
                checksums[blockIdx] = str(checksum)
                continue

            blockProgress = m.get('progress')
            if blockProgress != None:
                bp = BlockProgress()
                bp.ctx = blockProgress.get('ctx')
                bp.offset = blockProgress.get('offset')
                bp.restSize = blockProgress.get('restSize')
                blockProgresses[blockIdx] = bp
                continue

            break
