# -*- coding: utf-8 -*-
import peewee
import logging
from peewee_eve_sync.model import History, SyncedModel, KeyValue, SyncSettings
from playhouse.test_utils import test_database
from eve_mocker import EveMocker
from httpretty import HTTPretty
from tempfile import NamedTemporaryFile


class ExcludeFilter(logging.Filter):
    def filter(self, rec):
        if rec.name.startswith("peewee_eve_sync") or rec.name == "root":
            return True
        else:
            return rec.levelno >= logging.WARNING

log = logging.getLogger()

handler = logging.StreamHandler()
handler.addFilter(ExcludeFilter())
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

log.addHandler(handler)
log.setLevel(logging.ERROR)

test_db = peewee.SqliteDatabase(':memory:')


class TestModel(SyncedModel):
    key = peewee.CharField()
    content = peewee.CharField()

    class Sync(SyncSettings):
        pk = "key"

HTTPretty.enable()
EveMocker("http://localhost/api/", pk_maps={"testmodel": "key"}, default_pk="uuid")

db1 = peewee.SqliteDatabase(NamedTemporaryFile().name)
db2 = peewee.SqliteDatabase(NamedTemporaryFile().name)


def create_tables():
    History.create_table()
    TestModel.create_table()
    KeyValue.create_table()

print "##### STEP #1 #####"
print " => db1"
print " - create tables"
print " - create <ok>"
print " - sync"
print "###################"

with test_database(db1, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    create_tables()
    print "before", list(TestModel.select())
    tm = TestModel.create(key="ok", content="my content")
    print "after", list(TestModel.select())

print "##### STEP #2 #####"
print " => db2"
print " - create tables"
print " - create <ok2>"
print " - sync"
print "###################"

with test_database(db2, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    create_tables()
    print "before", list(TestModel.select())
    tm2 = TestModel.create(key="ok2", content="my content2")
    print "post create"
    print "after->", list(TestModel.select())

print "##### STEP #3 #####"
print " => db1"
print " - sync"
print "###################"

with test_database(db1, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    #print "before", list(TestModel.select())
    print "after=>", list(TestModel.select())

# TODO check that .get auto sync works with get when an updated version is
#       availabe on Eve

HTTPretty.disable()

# TODO ajouter des logs
# TODO DRY HTTPretty
# TODO => update and delete
# TODO => multiple client with from playhouse.test_utils import test_database
