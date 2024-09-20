import abc


class EndpointsProvider:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __iter__(self):
        """
        Returns
        -------
        list[Endpoint]
        """
