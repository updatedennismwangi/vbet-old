import json
import os
from typing import Dict, Any, Tuple, Optional, Union, List
from datetime import datetime
import pytz


def encode_json(data: Dict) -> str:
    return json.dumps(data)


def decode_json(data: Any) -> Union[Dict, List, None]:
    if isinstance(data, str):
        try:
            return json.loads(data)
        except ValueError:
            return None
    return None


def inspect_ws_server_payload(payload: Dict) -> Optional[Tuple[str, Dict]]:
    uri: Optional[str] = payload.get('uri', None)
    body: Optional[Any] = payload.get('body', None)
    if uri is not None and body is not None:
        return uri, body


def inspect_websocket_response(payload: Dict) -> Optional[Tuple[int, str, int, bool, Any]]:
    res: Dict = payload.get('res', {})
    xs: Optional[int] = payload.get('xs', None)
    status_code: Optional[int] = res.get('statusCode', None)
    valid_response: bool = res.get('validResponse', False)
    resource: Optional[str] = res.get('resource', None)
    body: Optional[Any] = res.get('body', None)
    _resource: Optional[str] = None
    for k, v in Resources.items():
        if v == resource:
            _resource = k
            break
    if _resource:
        _resource = resource
        return xs, _resource, status_code, valid_response, body


def get_ticket_timestamp() -> str:
    now = datetime.now(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
    return "%s%s" % (now, "Z")


def create_dir(dir_name: str):
    os.makedirs(dir_name, exist_ok=True)


class Resource:
    LOGIN = '/session/login'
    SYNC = '/session/sync'
    EVENTS = '/eventBlocks/event/data'
    RESULTS = '/eventBlocks/event/result'
    TICKETS = '/tickets/send'
    HISTORY = '/eventBlocks/history'
    STATS = '/eventBlocks/stats'
    TICKETS_FIND_BY_ID = '/tickets/findById'


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
