import threading


class _FlightLock:
    """
    Do not use dataclass which caused the event created only once
    """
    def __init__(self):
        self.event = threading.Event()
        self.result = None
        self.error = None


class SingleFlight:
    def __init__(self):
        self._locks = {}
        self._lock = threading.Lock()

    def do(self, key, fn, *args, **kwargs):
        # here does not use `with` statement
        # because need to wait by another object if it exists,
        # and reduce the `acquire` times if it not exists
        self._lock.acquire()
        if key in self._locks:
            flight_lock = self._locks[key]

            self._lock.release()
            flight_lock.event.wait()

            if flight_lock.error:
                raise flight_lock.error
            return flight_lock.result

        flight_lock = _FlightLock()
        self._locks[key] = flight_lock
        self._lock.release()

        try:
            flight_lock.result = fn(*args, **kwargs)
        except Exception as e:
            flight_lock.error = e
        finally:
            flight_lock.event.set()

        with self._lock:
            del self._locks[key]

        if flight_lock.error:
            raise flight_lock.error
        return flight_lock.result
