# -*- coding: utf-8 -*-
import peewee
import logging
from peewee_eve_sync.model import History, SyncedModel, KeyValue, SyncSettings
from playhouse.test_utils import test_database
from eve_mocker import EveMocker
from httpretty import HTTPretty
from tempfile import NamedTemporaryFile
import time


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
print "###################"

with test_database(db1, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    create_tables()
    #TestModel.Sync.auto = False
    print "before", list(TestModel.select())
    tm = TestModel.create(key="ok", content="my content")
    print "after", list(TestModel.select())
    """
    tm1 = TestModel.get(TestModel.key == "ok")
    tm1.content = "my new content"
    tm1.save()
    print TestModel.get(TestModel.key == "ok")._data
    """

time.sleep(2)
print "##### STEP #2 #####"
print " => db2"
print " - create tables"
print " - create <ok2>"
print "###################"

with test_database(db2, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    create_tables()
    print "before", list(TestModel.select())
    tm2 = TestModel.create(key="ok2", content="my content2")
    print "post create"
    print "after->", list(TestModel.select())

print time.sleep(2)
print "##### STEP #3 #####"
print " => db1"
print " - check if <ok2> is here"
print "###################"

with test_database(db1, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    #print "before", list(TestModel.select())
    print "after=>", list(TestModel.select())

time.sleep(2)
print "##### STEP #4 #####"
print " => db2"
print " - update <ok>"
print "###################"

with test_database(db2, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    print "before", list(TestModel.select())
    ok1 = TestModel.get(TestModel.key == "ok")
    print ok1._data, "pre update"
    ok1.content = "my updated content"
    ok1.save()
    print ok1._data, "post update"
    print "after->", list(TestModel.select())

time.sleep(2)
print "##### STEP #5 #####"
print " => db1"
print " - check if <ok> is updated"
print " ======> pq il est NOT actually UPDATED????"
print " - delete <ok2>"
print "###################"

with test_database(db1, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    print "ok1 updated:", TestModel.get(TestModel.key == "ok")._data
    print "before", list(TestModel.select())
    ok2 = TestModel.get(TestModel.key == "ok2")
    print ok2._data, "pre delete"
    ok2.delete_instance()
#    print "after=>", list(TestModel.select())


print "##### STEP #6 #####"
print " => db2"
print " - check if ok2 is deleted"
print " - create <ok3>"
print "###################"
time.sleep(2)
with test_database(db2, (TestModel, History, KeyValue), create_tables=False, drop_tables=False):
    time.sleep(2)
    print "before", list(TestModel.select())
    time.sleep(2)
    tm2 = TestModel.create(key="ok3", content="my content3")
    print "post create"
    print "after->", list(TestModel.select())

time.sleep(2)
print "##### STEP #7 #####"
print " => db1"
print " - check if <ok> and <ok3> are here"
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
""""""
