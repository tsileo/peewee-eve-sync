# -*- coding: utf-8 -*-
import peewee
import logging
from peewee_eve_sync.model import db, History, SyncedModel


class ExcludeFilter(logging.Filter):
    def filter(self, rec):
        print rec.__dict__
        if rec.name.startswith("peewee_eve_sync") or rec.name == "root":
            return True
        else:
            return rec.levelno >= logging.WARNING

log = logging.getLogger(__name__)

handler = logging.StreamHandler()
#handler.addFilter(ExcludeFilter())
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
log.addHandler(handler)
log.setLevel(logging.DEBUG)

db.init(":memory:")
History.create_table()


class TestModel(SyncedModel):
    key = peewee.CharField()

    class Sync:
        pk = "key"

TestModel.create_table()

tm = TestModel.create(key="ok")
print tm._meta.name
print
print list(History.select())
print

import re
import json
from httpretty import HTTPretty
HTTPretty.enable()

HTTPretty.register_uri(HTTPretty.GET, re.compile("http://localhost/api/testmodel/(.+)/"),
                       responses=[HTTPretty.Response(body="", status=404),
                                  HTTPretty.Response(body='{"etag": "sqdqsd"}', status=200)])

HTTPretty.register_uri(HTTPretty.POST, "http://localhost/api/testmodel/",
                       body='{"item": {"status": "OK", "etag": "sqdqsd"}}',
                       content_type="application/json")

HTTPretty.register_uri(HTTPretty.PATCH, "http://localhost/api/testmodel/",
                       body='{"item": {"status": "OK", "etag": "sqdqsd2"}}',
                       content_type="application/json")

HTTPretty.register_uri(HTTPretty.DELETE, "http://localhost/api/testmodel/",
                       body='{}',
                       content_type="application/json")


HTTPretty.register_uri(HTTPretty.POST, "http://localhost/api/history/",
                       body='{"item": {"status": "OK", "etag": "sqdqsd"}}',
                       content_type="application/json")

HTTPretty.register_uri(HTTPretty.GET, re.compile("http://localhost/api/history/(.+)/"),
                       responses=[HTTPretty.Response(body="", status=404)])


HTTPretty.register_uri(HTTPretty.PATCH, re.compile("http://localhost/api/history/(.+)/"),
                       responses=[HTTPretty.Response(body="", status=404)])


HTTPretty.register_uri(HTTPretty.GET, "http://localhost/api/history/",
                       body=json.dumps({"_items": [{"data": '{"key": "ok"}',
                                        "ts": 0,
                                        "action": "create",
                                        "model": "testmodel",
                                        "pk": "ok",
                                        "uuid": "azqdqds"}]}),
                       content_type="application/json")

tm.sync()

HTTPretty.disable()

print list(TestModel.select())

# TODO ajouter des logs
# TODO DRY HTTPretty
# TODO => update and delete
# TODO => multiple client with from playhouse.test_utils import test_database
