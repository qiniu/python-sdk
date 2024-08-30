from datetime import datetime, timedelta

from enum import Enum

from .endpoint import Endpoint


# Use StrEnum when min version of python update to >= 3.11
# to make the json stringify more readable,
# or find another way to simple the json stringify
class ServiceName(Enum):
    UC = 'uc'
    UP = 'up'
    UP_ACC = 'up_acc'
    IO = 'io'
    # IO_SRC = 'io_src'
    RS = 'rs'
    RSF = 'rsf'
    API = 'api'


class Region:
    @staticmethod
    def merge(*args):
        """
        Parameters
        ----------
        args: list[list[Region]]

        Returns
        -------

        """
        if not args:
            raise TypeError('There aren\'ta any regions to merge')
        source, rest = args[0], args[1:]
        target = source.clone()
        for r in rest:
            for sn, el in r.services.items():
                if sn not in target.services:
                    target.services[sn] = [e.clone() for e in el]
                else:
                    target_values = [e.get_value() for e in target.services[sn]]
                    target.services[sn] += [
                        e.clone()
                        for e in el
                        if e.get_value() not in target_values
                    ]

        return target

    @staticmethod
    def from_region_id(region_id, **kwargs):
        """
        Parameters
        ----------
        region_id: str
        kwargs: dict
            s3_region_id: str
            ttl: int
            create_time: datetime
            extended_services: dict[str, list[Region]]
            preferred_scheme: str

        Returns
        -------
        Region
        """
        # create services endpoints
        endpoint_kwargs = {
        }
        if 'preferred_scheme' in kwargs:
            endpoint_kwargs['default_scheme'] = kwargs.get('preferred_scheme')

        is_z0 = region_id == 'z0'
        services_hosts = {
            ServiceName.UC: ['uc.qiniuapi.com'],
            ServiceName.UP: [
                'upload-{0}.qiniup.com'.format(region_id),
                'up-{0}.qiniup.com'.format(region_id)
            ] if not is_z0 else [
                'upload.qiniup.com',
                'up.qiniup.com'
            ],
            ServiceName.IO: [
                'iovip-{0}.qiniuio.com'.format(region_id),
            ] if not is_z0 else [
                'iovip.qiniuio.com',
            ],
            ServiceName.RS: [
                'rs-{0}.qiniuapi.com'.format(region_id),
            ],
            ServiceName.RSF: [
                'rsf-{0}.qiniuapi.com'.format(region_id),
            ],
            ServiceName.API: [
                'api-{0}.qiniuapi.com'.format(region_id),
            ]
        }
        services = {
            k: [
                Endpoint(h, **endpoint_kwargs) for h in v
            ]
            for k, v in services_hosts.items()
        }
        services.update(kwargs.get('extended_services', {}))

        # create region
        region_kwargs = {
            k: kwargs.get(k)
            for k in [
                's3_region_id',
                'ttl',
                'create_time'
            ] if k in kwargs
        }
        region_kwargs['region_id'] = region_id
        region_kwargs.setdefault('s3_region_id', region_id)
        region_kwargs['services'] = services

        return Region(**region_kwargs)

    def __init__(
        self,
        region_id=None,
        s3_region_id=None,
        services=None,
        ttl=86400,
        create_time=None
    ):
        """
        Parameters
        ----------
        region_id: str
        s3_region_id: str
        services: dict[ServiceName or str, list[Endpoint]]
        ttl: int, default 86400
        create_time: datetime, default datetime.now()
        """
        self.region_id = region_id
        self.s3_region_id = s3_region_id if s3_region_id else region_id

        self.services = services if services else {}
        self.services.update(
            {
                k: []
                for k in ServiceName
                if
                k not in self.services or
                not isinstance(self.services[k], list)
            }
        )

        self.ttl = ttl
        self.create_time = create_time if create_time else datetime.now()

    @property
    def is_live(self):
        """
        Returns
        -------
        bool
        """
        if self.ttl < 0:
            return True
        live_time = datetime.now() - self.create_time
        return live_time < timedelta(seconds=self.ttl)

    def clone(self):
        """
        Returns
        -------
        Region
        """
        return Region(
            region_id=self.region_id,
            s3_region_id=self.s3_region_id,
            services={
                k: [endpoint.clone() for endpoint in self.services[k]]
                for k in self.services
            },
            ttl=self.ttl,
            create_time=self.create_time
        )
