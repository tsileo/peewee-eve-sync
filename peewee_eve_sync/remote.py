# encoding: utf-8
from datetime import datetime
import json
import requests
import logging

log = logging.getLogger(__name__)

api_root = "http://localhost/api/{0}/".format
api_resource = "http://localhost/api/{0}/{1}/".format


def get_remote_history(model, last_sync=0):
    """ Fetch the remote history over the API since last sync. """
    log.info("Fetching remote history since {0}".format(last_sync))
    r = requests.get(api_root('history'),
                     params={"where": json.dumps({"ts": {"$gt": last_sync},
                                                  "model": model})})
    r.raise_for_status()
    return r.json().get("_items", [])


def delete_resource(model, pk, etag, raw_history=None):
    """ Delete a resource. """
    log.info("Deleting resource {0} {1} (etag={2}, history={3}".format(model, pk, etag, raw_history))
    r = requests.delete(api_resource(model, pk),
                        headers={"If-Match": etag})
    r.raise_for_status()
    resp = r.json()
    log.info(resp)
    if resp.get("status") == "OK":
        del raw_history["id"]
        raw_history["ts"] = int(datetime.utcnow().strftime("%s"))
        post_resource("history", raw_history.get("uuid"), json.dumps(raw_history))
        return True
    elif resp.get("status") != "OK":
        log.error("Issue deleting: {0} <{1}>".format(model, pk))
        for issue in resp["issues"]:
            log.error(issue)
        return False


def patch_resource(model, pk, update, etag, raw_history=None):
    """ Patch a resource. """
    log.info("Patching {0} {1}: {2} (etag={3}, history={4}".format(model, pk, update, etag, raw_history))
    payload = {"data": update}
    r = requests.patch(api_resource(model, pk),
                       payload,
                       headers={"If-Match": etag})
    r.raise_for_status()
    resp = r.json().get("data")
    log.info(resp)
    if resp.get("status") == "OK":
        if model != "history" and raw_history is not None:
            # Call post_resource itself for the history
            del raw_history["id"]  # Since we can't rely on autoincrement id, we use uuid
            # We also update the timestamp (ts)
            raw_history["ts"] = int(datetime.utcnow().strftime("%s"))

            # The model is patched, so now we need to post this history entry to the API
            post_resource("history", raw_history.get("uuid"), json.dumps(raw_history))

            return resp.get("etag")

    elif resp.get("status") == "ERR":
        log.error("Issue patching: {0}".format(payload))
        for issue in resp["issues"]:
            log.error(issue)
    elif resp.get("status") != "OK":
        log.error("Issue patching {0}: {1}".format(payload, resp))


def post_resource(model, pk, data, raw_history=None):
    """ Create a resource, but verify if it doesn't exist yet before.
    Also used to POST history to the API.

    :return: resource ETag if successful, None if any error.

    """
    log.info("Posting {0} {1}: {2} (history={3}".format(model, pk, data, raw_history))
    call_url = api_resource(model, pk)
    r = requests.get(call_url)
    if r.status_code == 404:
        payload = {"item": data}
        r = requests.post(api_root(model),
                          payload)
        #try:
        r.raise_for_status()
        resp = r.json().get("item")
        log.info(resp)
        if resp.get("status") == "OK":
            if model != "history" and raw_history is not None:
                etag = resp.get("etag")
                # Call post_resource itself for the history
                del raw_history["id"]  # Since we can't rely on autoincrement id, we use uuid
                # We also update the timestamp (ts)
                raw_history["ts"] = int(datetime.utcnow().strftime("%s"))
                post_resource("history", raw_history.get("uuid"), json.dumps(raw_history))
                return etag
        elif resp.get("status") == "ERR":
            log.error("Issue posting: {0}".format(payload))
            for issue in resp["issues"]:
                log.error(issue)
        elif resp.get("status") != "OK":
            log.error("Issue posting {0}: {1}".format(payload, resp))


def get_resource(model, pk):
    """ Perform a GET request over a resource. """
    print "get_resource", model, pk
    log.info("GET {0} {1}".format(model, pk))
    call_url = api_resource(model, pk)
    r = requests.get(call_url)
    if r.status_code == 200:
        r.raise_for_status()
        data = r.json()
        if "_id" in data:
            del data["_id"]
            del data["_links"]
            del data["created"]
            del data["updated"]
        return data
