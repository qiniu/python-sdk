"""
Modified from standard httplib

1. HTTPConnection can send trunked data.
2. Remove httplib's automatic Content-Length insertion when data is a file-like object.
"""

# -*- coding: utf-8 -*-

import httplib
from httplib import _CS_REQ_STARTED, _CS_REQ_SENT
import string
import os
from array import array

class HTTPConnection(httplib.HTTPConnection):

	def send(self, data, is_chunked=False):
		"""Send `data' to the server."""
		if self.sock is None:
			if self.auto_open:
				self.connect()
			else:
				raise NotConnected()

		if self.debuglevel > 0:
			print "send:", repr(data)
		blocksize = 8192
		if hasattr(data,'read') and not isinstance(data, array):
			if self.debuglevel > 0: print "sendIng a read()able"
			datablock = data.read(blocksize)
			while datablock:
				if self.debuglevel > 0:
					print 'chunked:', is_chunked
				if is_chunked:
					if self.debuglevel > 0: print 'send: with trunked data'
					lenstr = string.upper(hex(len(datablock))[2:])
					self.sock.sendall('%s\r\n%s\r\n' % (lenstr, datablock))
				else:
					self.sock.sendall(datablock)
				datablock = data.read(blocksize)
			if is_chunked:
				self.sock.sendall('0\r\n\r\n')
		else:
			self.sock.sendall(data)


	def _set_content_length(self, body):
		# Set the content-length based on the body.
		thelen = None
		try:
			thelen = str(len(body))
		except (TypeError, AttributeError), te:
			# Don't send a length if this failed
			if self.debuglevel > 0: print "Cannot stat!!"

		if thelen is not None:
			self.putheader('Content-Length', thelen)
			return True
		return False


	def _send_request(self, method, url, body, headers):
		# Honor explicitly requested Host: and Accept-Encoding: headers.
		header_names = dict.fromkeys([k.lower() for k in headers])
		skips = {}
		if 'host' in header_names:
			skips['skip_host'] = 1
		if 'accept-encoding' in header_names:
			skips['skip_accept_encoding'] = 1

		self.putrequest(method, url, **skips)

		is_chunked = False
		if body and header_names.get('Transfer-Encoding') == 'chunked':
			is_chunked = True
		elif body and ('content-length' not in header_names):
			is_chunked = not self._set_content_length(body)
			if is_chunked:
				self.putheader('Transfer-Encoding', 'chunked')
		for hdr, value in headers.iteritems():
			self.putheader(hdr, value)

		self.endheaders(body, is_chunked=is_chunked)


	def endheaders(self, message_body=None, is_chunked=False):
		"""Indicate that the last header line has been sent to the server.

		This method sends the request to the server.  The optional
		message_body argument can be used to pass a message body
		associated with the request.  The message body will be sent in
		the same packet as the message headers if it is string, otherwise it is
		sent as a separate packet.
		"""
		if self.__state == _CS_REQ_STARTED:
			self.__state = _CS_REQ_SENT
		else:
			raise CannotSendHeader()
		self._send_output(message_body, is_chunked=is_chunked)


	def _send_output(self, message_body=None, is_chunked=False):
		"""Send the currently buffered request and clear the buffer.

		Appends an extra \\r\\n to the buffer.
		A message_body may be specified, to be appended to the request.
		"""
		self._buffer.extend(("", ""))
		msg = "\r\n".join(self._buffer)
		del self._buffer[:]
		# If msg and message_body are sent in a single send() call,
		# it will avoid performance problems caused by the interaction
		# between delayed ack and the Nagle algorithm.
		if isinstance(message_body, str):
			msg += message_body
			message_body = None
		self.send(msg)
		if message_body is not None:
			#message_body was not a string (i.e. it is a file) and
			#we must run the risk of Nagle
			self.send(message_body, is_chunked=is_chunked)

