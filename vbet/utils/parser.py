import json
from typing import Dict, Any
import time
from datetime import datetime
import pytz


def encode_json(data: Dict) -> str:
    return json.dumps(data)


def decode_json(data: Any) -> [Dict, None]:
    if isinstance(data, str):
        try:
            return json.loads(data)
        except ValueError:
            return None
    return None


def inspect_ws_server_payload(payload: Dict):
    uri = payload.get('uri', None)
    body = payload.get('body', None)
    if uri is not None and body is not None:
        return uri, body
    return None, None


def inspect_websocket_response(payload: Dict):
    res = payload.get('res', None)
    xs = payload.get('xs', None)
    status_code = res.get('statusCode', None)
    valid_response = res.get('validResponse', False)
    resource = res.get('resource', None)
    body = res.get('body', None)
    _resource = None
    for k, v in Resources.items():
        if v == resource:
            _resource = k
            break
    if _resource:
        _resource = resource
    return xs, _resource, valid_response, body


def get_ticket_timestamp() -> str:
    now = datetime.now(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
    return "%s%s" % (now, "Z")


class Resource:
    LOGIN = '/session/login'
    SYNC = '/session/sync'
    EVENTS = '/eventBlocks/event/data'
    RESULTS = '/eventBlocks/event/result'
    TICKETS = '/tickets/send'
    HISTORY = '/eventBlocks/history'
    STATS = '/eventBlocks/stats'
    TICKETS_FIND_BY_ID = '/tickets/findById'


class UserResource:
    XS = -1
    CONNECTED = 'connected'
    LOST = 'lost'


Resources = {
    'login': Resource.LOGIN,
    'sync': Resource.SYNC,
    'events': Resource.EVENTS,
    'results': Resource.RESULTS,
    'history': Resource.HISTORY,
    'tickets': Resource.TICKETS,
    'stats': Resource.STATS,
    'tickets_find_by_id': Resource.TICKETS_FIND_BY_ID
}


def map_resource_to_name(resource: str):
    return list(Resources.keys())[list(Resources.values()).index(resource)]
