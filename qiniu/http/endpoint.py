class Endpoint:
    @staticmethod
    def from_host(host):
        """
        Autodetect scheme from host string

        Parameters
        ----------
        host: str

        Returns
        -------
        Endpoint
        """
        if '://' in host:
            scheme, host = host.split('://')
            return Endpoint(host=host, default_scheme=scheme)
        else:
            return Endpoint(host=host)

    def __init__(self, host, default_scheme='https'):
        self.host = host
        self.default_scheme = default_scheme

    def __str__(self):
        return 'Endpoint(host:\'{0}\',default_scheme:\'{1}\')'.format(
            self.host,
            self.default_scheme
        )

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if not isinstance(other, Endpoint):
            raise TypeError('Cannot compare Endpoint with {0}'.format(type(other)))

        return self.host == other.host and self.default_scheme == other.default_scheme

    def get_value(self, scheme=None):
        scheme = scheme if scheme is not None else self.default_scheme
        return ''.join([scheme, '://', self.host])

    def clone(self):
        return Endpoint(
            host=self.host,
            default_scheme=self.default_scheme
        )
