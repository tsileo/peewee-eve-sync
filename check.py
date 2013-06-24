# -*- coding: utf-8 -*-
import peewee
import logging
from peewee_eve_sync.model import History, SyncedModel, KeyValue
from playhouse.test_utils import test_database
from eve_mocker import EveMocker
from httpretty import HTTPretty
from tempfile import NamedTemporaryFile


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

test_db = peewee.SqliteDatabase(':memory:')


class TestModel(SyncedModel):
    key = peewee.CharField()
    content = peewee.CharField()

    class Sync:
        pk = "key"

HTTPretty.enable()
EveMocker("http://localhost/api/", pk_maps={"testmodel": "key"}, default_pk="uuid")

db1 = peewee.SqliteDatabase(NamedTemporaryFile().name)
db2 = peewee.SqliteDatabase(NamedTemporaryFile().name)


def create_tables():
    History.create_table()
    TestModel.create_table()
    KeyValue.create_table()


with test_database(db1, (TestModel, History, KeyValue), create_tables=False):
    print "inside test_db1"
    create_tables()
    print "before", list(TestModel.select())
    tm = TestModel.create(key="ok", content="my content")
    TestModel.sync()
    print "after", list(TestModel.select())


with test_database(db2, (TestModel, History, KeyValue), create_tables=False):
    print "inside test_db2"
    create_tables()
    print "before", list(TestModel.select())
    TestModel.sync()
    print "after", list(TestModel.select())


with test_database(db1, (TestModel, History, KeyValue), create_tables=False):
    print "inside test_db1"
    print "before", list(TestModel.select())
    print list(TestModel.select())
    print "after", list(TestModel.select())


HTTPretty.disable()

# TODO ajouter des logs
# TODO DRY HTTPretty
# TODO => update and delete
# TODO => multiple client with from playhouse.test_utils import test_database
