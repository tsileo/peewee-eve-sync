# -*- coding: utf-8 -*-

""" test_peewee_eve_sync.py - Test the peewee_eve_sync module. """

import unittest
import time
from sure import expect
import peewee
import requests
from peewee_eve_sync.model import History, SyncedModel, KeyValue, SyncSettings
from playhouse.test_utils import test_database
from eve_mocker import EveMocker
from httpretty import HTTPretty
import logging

NB_CLIENTS = 3
NB_ITEMS = 20
FIRST_INSERT = 0.3

log = logging.getLogger()

handler = logging.StreamHandler()
#handler.addFilter(ExcludeFilter())
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

log.addHandler(handler)
log.setLevel(logging.ERROR)


class TestModel(SyncedModel):
    key = peewee.CharField()
    content = peewee.CharField()

    class Sync(SyncSettings):
        pk = "key"


class TestPeeweeEveSync(unittest.TestCase):
    def setUp(self):
        self.dbs = {}
        for idb in range(NB_CLIENTS):
            self.dbs[idb] = peewee.SqliteDatabase(":memory:")

        self.models = (TestModel, History, KeyValue)

        HTTPretty.enable()
        self.eve_mocker = EveMocker("http://localhost/api/", pk_maps={"testmodel": "key"}, default_pk="uuid")

        self.items = []
        for i in range(NB_ITEMS):
            self.items.append({"key": "ok{0}".format(i), "content": "content{0}".format(i)})
        self.items = sorted(self.items, key=lambda x: x["key"])

    def tearDown(self):
        self.dbs = {}
        HTTPretty.disable()

    def _createTables(self):
        for m in self.models:
            if not m.table_exists():
                m.create_table()

    def _autoSync(self):
        for m in self.models:
            if issubclass(m, SyncedModel):
                m.Sync.auto = True

    def _rawEntries(self, select):
        """ Return dict from Models and remove id on the fly. """
        out = []
        for d in select:
            if not isinstance(d, dict):
                _d = dict(d._data)
            else:
                _d = dict(d)
            for k in ["id", "_id", "etag"]:
                if k in _d:
                    del _d[k]
            out.append(_d)
        return sorted(out, key=lambda x: x["key"])

    def testSynchronizationAuto(self):
        """ Setup a few models, and try to sync them between 3 sqlite databases. """
        # First, we create nb_items on db0
        nb_items = int(NB_ITEMS * FIRST_INSERT)
        with test_database(self.dbs[0], self.models, create_tables=False):
            self._createTables()
            self._autoSync()
            for item in self.items[:nb_items]:
                TestModel.create(**item)

        # Check if items are available via the API
        _items = requests.get("http://localhost/api/testmodel/").json().get("_items", [])
        self._rawEntries(_items).should.be.equal(self.items[:nb_items])

        # Check that the new model is propagated everywhere
        for db in self.dbs:
            with test_database(self.dbs[db], self.models, create_tables=False):
                self._createTables()
                self._autoSync()
                self._rawEntries(TestModel.select()).should.be.equal(self.items[:nb_items])

        # We edit an item on db2
        with test_database(self.dbs[2], self.models, create_tables=False):
            self._createTables()
            self._autoSync()
            cmodel = TestModel.get(TestModel.key == "ok0")
            cmodel.content = "new content0"
            cmodel.save()

        # Check that the change is made on the API
        remote_item = requests.get("http://localhost/api/testmodel/ok0/").json()
        remote_item["content"].should.be.equal("new content0")

        # Check that the update is propagated everywhere
        for db in self.dbs:
            with test_database(self.dbs[db], self.models, create_tables=False):
                self._createTables()
                self._autoSync()
                cmodel = TestModel.get(TestModel.key == "ok0")
                cmodel.content.should.be.equal("new content0")

        last_items = NB_ITEMS - nb_items
        # No we delete the 3 items, and we insert 4-9 on db3
        with test_database(self.dbs[1], self.models, create_tables=False):
            self._createTables()
            self._autoSync()
            for m in TestModel._select():
                m.delete_instance()
            for item in self.items[last_items:]:
                TestModel.create(**item)

        # Check the API
        _items = requests.get("http://localhost/api/testmodel/").json().get("_items", [])
        self._rawEntries(_items).should.be.equal(self.items[last_items:])

        # Check the 3 peewee dbs
        for db in self.dbs:
            with test_database(self.dbs[db], self.models, create_tables=False):
                self._createTables()
                self._autoSync()
                entries = TestModel.select()
                self._rawEntries(entries).should.be.equal(self.items[last_items:])

        # TODO faire le tout delete et checker empty
        # TODO remove le Item doesn't exists

if __name__ == '__main__':
    unittest.main()
