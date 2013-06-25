import unittest
import config

class TestConfig(unittest.TestCase):
	def test_USER_AGENT(self):
		assert len(config.USER_AGENT) >= len('qiniu python-sdk')
	
if __name__ == '__main__':
	unittest.main()
