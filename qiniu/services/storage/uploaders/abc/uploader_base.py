import abc

import qiniu.config as config
from qiniu.region import LegacyRegion
from qiniu.http.endpoint import Endpoint
from qiniu.http.regions_provider import get_default_regions_provider

# type import
from qiniu.auth import Auth # noqa
from qiniu.http.region import Region, ServiceName  # noqa


class UploaderBase(object):
    """
    Attributes
    ----------
    bucket_name: str
    auth: Auth
    regions: list[Region]
    """
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        bucket_name,
        **kwargs
    ):
        """
        Parameters
        ----------
        bucket_name: str
            The name of bucket which you want to upload to.
        auth: Auth
            The instance of Auth to sign requests.
        regions: list[Region], default=[]
            The regions of bucket. It will be queried if not specified.
        kwargs
            The others arguments may be used by subclass.
        """
        # default bucket_name
        self.bucket_name = bucket_name

        # change the default when implements AuthProvider
        self.auth = kwargs.get('auth', None)

        # regions config
        regions = kwargs.get('regions', None)
        if not regions:
            regions = []
        self.regions = regions

        query_regions_endpoints = kwargs.get('query_regions_endpoints', None)
        if not query_regions_endpoints:
            query_regions_endpoints = []
        self.query_regions_endpoints = query_regions_endpoints

        self.preferred_scheme = kwargs.get('preferred_scheme', 'https')

        # change the default value to False when remove config.get_default('default_zone')
        self.accelerate_uploading = kwargs.get('accelerate_uploading', None)

    def get_up_token(
        self,
        bucket_name=None,
        key=None,
        expired=None,
        policy=None,
        strict_policy=None,
        **_kwargs
    ):
        """
        Generate up token

        Parameters
        ----------
        bucket_name: str
        key: str
        expired: int
            seconds
        policy: dict
        strict_policy: bool
        _kwargs: dict
            useless for now, just for compatibility

        Returns
        -------
        str
        """
        if not self.auth:
            raise ValueError('can not get up_token by auth not provided')

        bucket_name = bucket_name if bucket_name else self.bucket_name

        kwargs_for_up_token = {
            k: v
            for k, v in {
                'bucket': bucket_name,
                'key': key,
                'expired': expired,
                'policy': policy,
                'strict_policy': strict_policy
            }.items()
            if k
        }
        up_token = self.auth.upload_token(**kwargs_for_up_token)
        return up_token

    def _get_regions_provider(self, access_key=None, bucket_name=None):
        """
        Parameters
        ----------
        access_key: str
        bucket_name: str

        Returns
        -------
        Iterable[Region or LegacyRegion]
        """
        if self.regions:
            return self.regions

        # handle compatibility for default_zone
        if config.is_customized_default('default_zone'):
            return [config.get_default('default_zone')]

        # handle compatibility for default_query_region_host
        query_regions_endpoints = self.query_regions_endpoints
        if not query_regions_endpoints:
            query_region_host = config.get_default('default_query_region_host')
            query_region_backup_hosts = config.get_default('default_query_region_backup_hosts')
            query_regions_endpoints = [
                Endpoint.from_host(h)
                for h in [query_region_host] + query_region_backup_hosts
            ]

        # get regions from default regions provider
        if not self.auth and not access_key:
            raise ValueError('Must provide access_key and bucket_name if auth is unavailable.')
        if not access_key:
            access_key = self.auth.get_access_key()
        if not bucket_name:
            bucket_name = self.bucket_name

        return get_default_regions_provider(
            query_endpoints_provider=query_regions_endpoints,
            access_key=access_key,
            bucket_name=bucket_name,
            accelerate_uploading=self.accelerate_uploading,
            preferred_scheme=self.preferred_scheme,
        )

    def _get_regions(self, access_key=None, bucket_name=None):
        """
        .. deprecated::
            This has been deprecated by implemented regions provider and endpoints

        Parameters
        ----------
        access_key: str
        bucket_name: str

        Returns
        -------
        list[LegacyRegion]
        """
        # TODO(lihs): the type not match legacy, fix it
        return list(self._get_regions_provider(access_key, bucket_name))

    def _get_up_hosts(self, access_key=None, bucket_name=None):
        """
        get hosts of upload by access key or the first region

        .. deprecated::
            This has been deprecated by implemented regions provider and endpoints

        Returns
        -------
        list[str]
        """
        if not bucket_name:
            bucket_name = self.bucket_name
        if not self.auth and not access_key:
            raise ValueError('Must provide access_key if auth is unavailable.')
        if not access_key:
            access_key = self.auth.get_access_key()

        regions = self._get_regions(access_key, bucket_name)

        if not regions:
            raise ValueError('No region available.')

        # get up hosts in region
        service_names = [ServiceName.UP]
        if self.accelerate_uploading:
            service_names.insert(0, ServiceName.UP_ACC)

        return [
            e.get_value()
            for sn in service_names
            for e in regions[0].services[sn]
        ]

    @abc.abstractmethod
    def upload(
        self,
        key,
        file_path,
        data,
        data_size,
        modify_time,

        part_size,
        mime_type,
        metadata,
        file_name,
        custom_vars,
        **kwargs
    ):
        """
        Upload method

        Parameters
        ----------
        key: str
        file_path: str
        data: IOBase
        data_size: int
        modify_time: int

        part_size: int
        mime_type: str
        metadata: dict
        file_name: str
        custom_vars: dict
        kwargs: dict

        Returns
        -------
        ret: dict
            The parsed response body
        info
            The response
        """
