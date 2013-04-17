# -*- coding: utf-8 -*-

from collections import Sequence
from datetime import datetime

try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin  # NOQA

from cosm.client import Client
from cosm.models import (
    Datapoint, Datastream, Feed, Key, Location, Permission, Resource, Trigger,
    Unit, Waypoint,
)


__all__ = ['CosmAPIClient']


class CosmAPIClient(object):
    """An instance of an authenticated Cosm API Client.

    The root object from which the user can manage feeds, keys and triggers.

    :param key: A Cosm API Key
    :type key: str

    Usage::

        >>> import cosm
        >>> cosm.CosmAPIClient("API_KEY")
        <cosm.CosmAPIClient()>

    """
    api_version = 'v2'
    client_class = Client

    def __init__(self, key):
        self.client = self.client_class(key)
        self.client.base_url += '/{}/'.format(self.api_version)
        self._feeds = FeedsManager(self.client)
        self._triggers = TriggersManager(self.client)
        self._keys = KeysManager(self.client)

    def __repr__(self):
        return "<{}.{}()>".format(__package__, self.__class__.__name__)

    @property
    def feeds(self):
        """
        Access :class:`.Feed` objects through a :class:`.FeedsManager`.
        """
        return self._feeds

    @property
    def triggers(self):
        """
        Access :class:`.Trigger` objects through a :class:`.TriggersManager`.
        """
        return self._triggers

    @property
    def keys(self):
        """
        Access :class:`.Key` objects through a :class:`.KeysManager`.
        """
        return self._keys


class ManagerBase(object):
    """Abstract base class for all of out manager classes."""

    @property
    def base_url(self):
        if getattr(self, '_base_url', None) is not None:
            return self._base_url
        parent = getattr(self, 'parent', None)
        if parent is None:
            return
        manager = getattr(parent, '_manager', None)
        if manager is None:
            return
        base_url = manager.url(parent.id) + '/' + self.resource
        return base_url

    @base_url.setter  # NOQA
    def base_url(self, base_url):
        self._base_url = base_url

    def url(self, url_or_id=None):
        """Return a url relative to the base url."""
        url = self.base_url
        if url_or_id:
            url = urljoin(url + '/', str(url_or_id))
        return url

    def _parse_datetime(self, value):
        """Parse and return a datetime string from the Cosm API."""
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")

    def _prepare_params(self, params):
        """Prepare parameters to be passed in query strings to the Cosm API."""
        params = dict(params)
        for name, value in params.items():
            if isinstance(value, datetime):
                params[name] = value.isoformat() + 'Z'
        return params


class FeedsManager(ManagerBase):
    """Create, update and return Feed objects.

    .. note:: This manager should live on a :class:`.CosmAPIClient` instance
        and not instantiated directly.

    :param client: Low level :class:`.Client` instance

    Usage::

        >>> import cosm
        >>> api = cosm.CosmAPIClient("API_KEY")
        >>> api.feeds.create(title="Cosm Office environment")
        <cosm.Feed(7021)>
        >>> api.feeds.get(7021)
        <cosm.Feed(7021)>
        >>> api.feeds.update(7021, private=True)
        >>> api.feeds.delete(7021)

    """

    resource = 'feeds'

    def __init__(self, client):
        self.client = client
        self.base_url = client.base_url + self.resource

    def create(self, title, website=None, tags=None, location=None,
               private=None, **params):
        """Creates a new Feed.

        :param title: A descriptive name for the feed
        :param website: The URL of a website which is relevant to this feed
            e.g. home page
        :param tags: Tagged metadata about the environment (characters ' " and
            commas will be stripped out)
        :param location: :class:`.Location` object for this feed
        :param private: Whether the environment is private or not. Can be
            either True or False
        :param params: Additional parameters to be sent with the request

        """
        data = dict(title=title, website=website, tags=tags, location=location,
                    private=private, version=Feed.VERSION, **params)
        feed = self._coerce_feed(data)
        response = self.client.post(self.url(), data=feed)
        response.raise_for_status()
        location = response.headers['location']
        feed.feed = location
        feed.id = _id_from_url(location)
        return feed

    def update(self, id_or_url, **kwargs):
        """Updates an existing feed by its id or url.

        :param id_or_url: The id of a :class:`.Feed` or its URL
        :param kwargs: The fields to be updated

        """
        url = self.url(id_or_url)
        response = self.client.put(url, data=kwargs)
        response.raise_for_status()

    def list(self, page=None, per_page=None, content=None, q=None, tag=None,
             user=None, units=None, status=None, order=None, show_user=None,
             lat=None, lon=None, distance=None, distance_units=None, **params):
        """Returns a paged list of feeds.

        Only feeds that are viewable by the authenticated account will be
        returned. The following parameters can be applied to limit or refine
        the returned feeds:

        :param page: Integer indicating which page of results you are
            requesting. Starts from 1.
        :param per_page: Integer defining how many results to return per page
            (1 to 1000)
        :param content: String parameter ('full' or 'summary') describing
            whether we want full or summary results. Full results means all
            datastream values are returned, summary just returns the
            environment meta data for each feed
        :param q: Full text search parameter. Should return any feeds matching
            this string
        :param tag: Returns feeds containing datastreams tagged with the search
            query
        :param user: Returns feeds created by the user specified
        :param units: Returns feeds containing datastreams with units specified
            by the search query
        :param status: Possible values ('live', 'frozen', or 'all'). Whether to
            search for only live feeds, only frozen feeds, or all feeds.
            Defaults to all
        :param order: Order of returned feeds. Possible values ('created_at',
            'retrieved_at', or 'relevance')
        :param show_user: Include user login and user level for each feed.
            Possible values: true, false (default)

        The following additional parameters are available which allow location
        based searching of feeds:

        :param lat: Used to find feeds located around this latitude
        :param lon: Used to find feeds located around this longitude
        :param distance: search radius
        :param distance_units: miles or kms (default)
        :param params: Additional parameters to send with the request

        """
        url = self.url()
        params.update({k: v for k, v in (
            ('page', page),
            ('per_page', per_page),
            ('content', content),
            ('q', q),
            ('tag', tag),
            ('user', user),
            ('units', units),
            ('status', status),
            ('order', order),
            ('show_user', show_user),
            ('lat', lat),
            ('lon', lon),
            ('distance', distance),
            ('distance_units', distance_units),
        ) if v is not None})
        response = self.client.get(url, params=params)
        response.raise_for_status()
        json = response.json()
        feeds = [self._coerce_feed(feed_data) for feed_data in json['results']]
        return feeds

    def get(self, url_or_id, datastreams=None, show_user=None, **params):
        """Fetches and returns a feed by id or url.

        By default the most recent datastreams are returned. It is also
        possible to filter the datastreams returned with the feed by using the
        "datastreams" parameter and a list of datastream IDs.

        :param datastreams: Filter the returned datastreams
        :type datastreams: list of datastream IDs
        :param show_user: Include user login for each feed. (default: False)
        :type show_user: bool

        """
        url = self.url(url_or_id)
        if isinstance(datastreams, Sequence):
            datastreams = ','.join(datastreams)
        params.update({k: v for k, v in (
            ('datastreams', datastreams),
            ('show_user', show_user),
        ) if v is not None})
        params = self._prepare_params(params)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        feed = self._coerce_feed(data)
        return feed

    def delete(self, url_or_id):
        """Delete a feed by id or url.

        .. WARNING:: This is final and cannot be undone.

        :param url_or_id: The feed ID  or its URL

        """
        url = self.url(url_or_id)
        response = self.client.delete(url)
        response.raise_for_status()

    def _coerce_feed(self, feed_data):
        """Returns a Feed object from a mapping object (dict)."""
        datastreams_data = feed_data.pop('datastreams', None)
        location_data = feed_data.pop('location', None)
        feed = Feed(**feed_data)
        feed._manager = self
        if datastreams_data:
            datastreams_manager = DatastreamsManager(feed)
            datastreams = self._coerce_datastreams(
                datastreams_data, datastreams_manager)
            feed._data['datastreams'] = datastreams
            feed._datastreams = datastreams_manager
        if location_data:
            feed._data['location'] = self._coerce_location(location_data)
        return feed

    def _coerce_datastreams(self, datastreams_data, datastreams_manager):
        """Returns Datastream objects from the data given."""
        datastreams = []
        for data in datastreams_data:
            datastream = datastreams_manager._coerce_datastream(data)
            datastreams.append(datastream)
        return datastreams

    def _coerce_location(self, instance):
        """Returns a Location object, converted from instance if required."""
        if isinstance(instance, Location):
            location = instance
        else:
            location_data = dict(**instance)
            waypoints_data = location_data.pop('waypoints', None)
            if waypoints_data is not None:
                waypoints = self._coerce_waypoints(waypoints_data)
                location_data['waypoints'] = waypoints
            location = Location(**location_data)
        return location

    def _coerce_waypoints(self, waypoints_data):
        """Returns a list of Waypoint objects from the given waypoint data."""
        waypoints = []
        for data in waypoints_data:
            at = self._parse_datetime(data['at'])
            data = {k: v for k, v in data.items() if k != 'at'}
            waypoint = Waypoint(at=at, **data)
            waypoints.append(waypoint)
        return waypoints


class DatastreamsManager(Sequence, ManagerBase):
    """Create, update and return Datastream objects.

    Instances of this class hang off of :class:`.Feed` objects to manage
    datastreams of that feed.

    A list of datastreams can be retrieved along with the feed which can be
    accessed via this instance as a sequence.

    """

    resource = 'datastreams'

    def __init__(self, feed):
        self.parent = feed
        feed_manager = getattr(feed, '_manager', None)
        self.client = getattr(feed_manager, 'client', None)

    def __contains__(self, value):
        return value in self.datastreams['datastreams']

    def __getitem__(self, item):
        return self._datastreams[item]

    def __len__(self):
        return len(self._datastreams)

    @property
    def _datastreams(self):
        return self.parent._data.setdefault('datastreams', [])

    def create(self, id, **kwargs):
        """Create a new datastream on a feed."""
        data = {
            'version': self.parent.version,
            'datastreams': [dict(id=id, **kwargs)],
        }
        response = self.client.post(self.url(), data=data)
        response.raise_for_status()
        datastream = Datastream(id=id, **kwargs)
        datastream._manager = self
        return datastream

    def update(self, datastream_id, **kwargs):
        """Update a feeds datastream by id."""
        url = self.url(datastream_id)
        response = self.client.put(url, data=kwargs)
        response.raise_for_status()

    def list(self, **params):
        """Return a list of datastreams for the parent feed object."""
        url = self.url('..')
        response = self.client.get(url, params=params)
        response.raise_for_status()
        json = response.json()
        for datastream_data in json.get('datastreams', []):
            datastream = Datastream(**datastream_data)
            datastream._manager = self
            yield datastream

    def get(self, id, **params):
        """Fetch and return a feeds datastream by its id."""
        url = self.url(id)
        params = self._prepare_params(params)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        datastream = self._coerce_datastream(data)
        return datastream

    def delete(self, url_or_id):
        """Delete a datastream by id or url."""
        url = self.url(url_or_id)
        response = self.client.delete(url)
        response.raise_for_status()

    def _coerce_datapoints(self, datapoints_manager, datapoints_data):
        datapoints = []
        for data in datapoints_data:
            data['at'] = self._parse_datetime(data['at'])
            datapoint = datapoints_manager._coerce_datapoint(data)
            datapoints.append(datapoint)
        return datapoints

    def _coerce_datastream(self, d):
        if isinstance(d, dict):
            datapoints_data = d.pop('datapoints', None)
            datastream = Datastream(**d)
            if datapoints_data:
                datapoints = self._coerce_datapoints(
                    datastream.datapoints, datapoints_data)
                datastream.datapoints = datapoints
        elif isinstance(d, Datastream):
            datastream = d
        datastream._manager = self
        return datastream


class DatapointsManager(Sequence, ManagerBase):
    """Manage datapoints of a datastream.

    A list of :class:`.Datapoint` objects can be retrieved along with the
    :class:`.Datastream` (or :class:`.Feed`) which can be accessed via this
    instance as a sequence.

    """

    resource = 'datapoints'

    def __init__(self, datastream):
        self.parent = datastream
        datastream_manager = getattr(datastream, '_manager', None)
        self.client = getattr(datastream_manager, 'client', None)

    def __contains__(self, value):
        return value in self.datapoints['datapoints']

    def __getitem__(self, item):
        return self._datapoints[item]

    def __len__(self):
        return len(self._datapoints)

    @property
    def _datapoints(self):
        return self.parent._data['datapoints']

    def create(self, datapoints):
        """Create a number of new datapoints for this datastream."""
        datapoints = [self._coerce_datapoint(d) for d in datapoints]
        payload = {'datapoints': datapoints}
        response = self.client.post(self.url(), data=payload)
        response.raise_for_status()
        return datapoints

    def update(self, at, value):
        """Update the value of a datapiont at a given timestamp."""
        url = "{}/{}Z".format(self.url(), at.isoformat())
        payload = {'value': value}
        response = self.client.put(url, data=payload)
        response.raise_for_status()

    def get(self, at):
        """Fetch and return a :class:`.Datapoint` at the given timestamp."""
        url = "{}/{}Z".format(self.url(), at.isoformat())
        response = self.client.get(url)
        response.raise_for_status()
        data = response.json()
        data['at'] = self._parse_datetime(data['at'])
        return self._coerce_datapoint(data)

    def history(self, **params):
        """Fetch and return a list of datapoints in a given timerange."""
        url = self.url('..').rstrip('/')
        params = self._prepare_params(params)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        for datapoint_data in data.get('datapoints', []):
            datapoint_data['at'] = self._parse_datetime(datapoint_data['at'])
            yield self._coerce_datapoint(datapoint_data)

    def delete(self, at=None, **params):
        """Delete a datapoint or a range of datapoints."""
        url = self.url()
        if at:
            url = "{}/{}Z".format(url, at.isoformat())
        elif params:
            params = self._prepare_params(params)
        response = self.client.delete(url, params=params)
        response.raise_for_status()

    def _coerce_datapoint(self, d):
        if isinstance(d, Datapoint):
            datapoint = self._clone_datapoint(d)
        elif isinstance(d, dict):
            datapoint = Datapoint(**d)
        datapoint._manager = self
        return datapoint

    def _clone_datapoint(self, d):
        return Datapoint(**d._data)


class TriggersManager(ManagerBase):
    """Manage :class:`.Trigger`.

    This manager should live on a :class:`.CosmAPIClient` instance and not
    instantiated directly.

    """

    resource = 'triggers'

    def __init__(self, client):
        self.client = client
        self.base_url = client.base_url + self.resource

    def create(self, *args, **kwargs):
        """Create a new :class:`.Trigger`.

        :returns: A new :class:`.Trigger` object.

        """
        trigger = Trigger(*args, **kwargs)
        response = self.client.post(self.url(), data=trigger)
        response.raise_for_status()
        trigger._manager = self
        location = response.headers['location']
        trigger._data['id'] = int(location.rsplit('/', 1)[1])
        return trigger

    def get(self, id):
        """Fetch and return an existing trigger by its id."""
        url = self.url(id)
        response = self.client.get(url)
        response.raise_for_status()
        data = response.json()
        data.pop('id')
        notified_at = data.pop('notified_at', None)
        user = data.pop('user', None)
        trigger = Trigger(**data)
        trigger._data['id'] = id
        if notified_at:
            trigger._data['notified_at'] = self._parse_datetime(notified_at)
        if user:
            trigger._data['user'] = user
        trigger._manager = self
        return trigger

    def update(self, id, **kwargs):
        """Update an existing trigger."""
        url = self.url(id)
        response = self.client.put(url, data=kwargs)
        response.raise_for_status()

    def list(self, **params):
        """Return a list of triggers."""
        url = self.url()
        response = self.client.get(url, params=params)
        response.raise_for_status()
        json = response.json()
        for data in json:
            trigger = Trigger(**data)
            trigger._manager = self
            yield trigger

    def delete(self, url_or_id):
        """Delete a trigger by id or url."""
        url = self.url(url_or_id)
        response = self.client.delete(url)
        response.raise_for_status()


class KeysManager(ManagerBase):
    """Manage keys their permissions and restrict by resource."""

    resource = 'keys'

    def __init__(self, client):
        self.client = client
        self.base_url = client.base_url + self.resource

    def create(self, label, permissions, **kwargs):
        """Create a new API key."""
        data = dict(label=label, permissions=permissions, **kwargs)
        response = self.client.post(self.url(), data={'key': data})
        response.raise_for_status()
        location = response.headers['Location']
        data['api_key'] = _id_from_url(location)
        key = self._coerce_key(data)
        return key

    def list(self, feed_id=None, **kwargs):
        """List all API keys for this account or for the given feed."""
        url = self.url()
        params = {}
        if feed_id is not None:
            params['feed_id'] = feed_id
        params.update(kwargs)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        json = response.json()
        for data in json['keys']:
            key = self._coerce_key(data)
            yield key

    def get(self, key_id, **params):
        """Fetch and return an API key by its id."""
        url = self.url(key_id)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        key = self._coerce_key(data['key'])
        return key

    def delete(self, key_id):
        """Delete an API key."""
        url = self.url(key_id)
        response = self.client.delete(url)
        response.raise_for_status()

    def _coerce_key(self, data):
        api_key = data.get('api_key')
        permissions_data = data.get('permissions', [])
        data = {k: v for (k, v) in data.items() if k != 'api_key'}
        permissions = []
        for permission_data in permissions_data:
            permission = self._coerce_permission(permission_data)
            permissions.append(permission)
        data['permissions'] = permissions
        key = Key(**data)
        key._data['api_key'] = api_key
        key._manager = self
        return key

    def _coerce_permission(self, data):
        if isinstance(data, Permission):
            return data
        resources_data = data.get('resources')
        data = {k: v for (k, v) in data.items() if k != 'resources'}
        permission = Permission(**data)
        if resources_data:
            resources = []
            for resource_data in resources_data:
                resource = self._coerce_resource(resource_data)
                resources.append(resource)
            permission._data['resources'] = resources
        return permission

    def _coerce_resource(self, data):
        resource = Resource(**data)
        return resource


def _id_from_url(url):
    """Return the last part or a url

    >>> _id_from_url('http://api.cosm.com/v2/feeds/1234')
    '1234'

    """
    id = url.rsplit('/', 1)[1]
    return id
