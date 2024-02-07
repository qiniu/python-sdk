import pytest

from qiniu import BucketManager


@pytest.fixture()
def bucket_manager(qn_auth):
    yield BucketManager(qn_auth)
