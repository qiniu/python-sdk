import pytest
import time
from multiprocessing.pool import ThreadPool

from qiniu.http.single_flight import SingleFlight

class TestSingleFlight:
    def test_single_flight_success(self):
        sf = SingleFlight()

        def fn():
            return "result"

        result = sf.do("key1", fn)
        assert result == "result"

    def test_single_flight_exception(self):
        sf = SingleFlight()

        def fn():
            raise ValueError("error")

        with pytest.raises(ValueError, match="error"):
            sf.do("key2", fn)

    def test_single_flight_concurrent(self):
        sf = SingleFlight()
        share_state = []
        results = []

        def fn():
            time.sleep(1)
            share_state.append('share_state')
            return "result"

        def worker(_n):
            result = sf.do("key3", fn)
            results.append(result)

        ThreadPool(2).map(worker, range(5))

        assert len(share_state) == 3
        assert all(result == "result" for result in results)

    def test_single_flight_different_keys(self):
        sf = SingleFlight()
        results = []

        def fn():
            time.sleep(1)
            return "result"

        def worker(n):
            result = sf.do("key{}".format(n), fn)
            results.append(result)

        ThreadPool(2).map(worker, range(2))
        assert len(results) == 2
        assert all(result == "result" for result in results)
