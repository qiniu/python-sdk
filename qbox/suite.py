#!/usr/bin/env python

import testcase

tc = testcase.TestCase()
if not tc.SetUp():
	exit(1)
success = 0
failed = 0
for k in testcase.TestCase.__dict__.keys():
	if k.startswith('Test'):
		print k
		ret = getattr(tc, k)()
		if 0 == ret:
			print "Success"
			success = success + 1
		else:
			print "Failed"
			failed = failed + 1

print '%d Success' % success
print '%d Failed' % failed

if failed!=0:
	exit(1)
else:
	exit(0)
