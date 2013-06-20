# -*- coding: utf-8 -*-
from playhouse.kv import PickledKeyStore
import peewee
from datetime import datetime
import json
import logging
import uuid

from remote import (get_remote_history,
                    get_resource,
                    post_resource,
                    patch_resource,
                    delete_resource)

log = logging.getLogger(__name__)

test_db = peewee.SqliteDatabase(':memory:')
kv = PickledKeyStore(database=test_db)
db = peewee.SqliteDatabase(None)


class JsonField(peewee.CharField):
    """Custom JSON field."""
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        try:
            return json.loads(value)
        except:
            return value


class BaseModel(peewee.Model):
    class Meta:
        database = db


class History(BaseModel):
    """ History for sync.

    Track create/update/delete for synced models.

    """
    data = JsonField()
    ts = peewee.IntegerField(index=True)
    action = peewee.CharField()
    model = peewee.CharField(index=True)
    pk = peewee.CharField()
    uuid = peewee.CharField(default=uuid.uuid4())

    def __repr__(self):
        return "<History: {model}/{action}/{uuid}>".format(**self._data)

    class Meta:
        db_table = 'history'


class SyncedModel(BaseModel):
    """ A base model to sync a peewee Model over a Eve REST API.
    Synchronization is history based, and works with multiple clients.
    """
    def __repr__(self):
        return "<{0} {1} (sync)>".format(self._meta.name, self._data.get(self.Sync.pk))

    @classmethod
    def create(cls, **attributes):
        if cls._meta.name != "history":
            History.create(data=json.dumps(dict(**attributes)),
                           ts=int(datetime.utcnow().strftime("%s")),
                           action="create",
                           model=cls._meta.name,
                           pk=attributes.get(cls.Sync.pk))
        return super(SyncedModel, cls).create(**attributes)

    def update(self, **update):
        if self._meta.name != "history":
            History.create(data=json.dumps(dict(**update)),
                           ts=int(datetime.utcnow().strftime("%s")),
                           action="update",
                           model=self._meta.name,
                           pk=self._data.get(self.Sync.pk))
        return super(SyncedModel, self).update(**update)

    def delete_instance(self):
        if self._meta.name != "history":
            History.create(data={},
                           ts=int(datetime.utcnow().strftime("%s")),
                           action="delete",
                           model=self._meta.name,
                           pk=self._data.get(self.Sync.pk))
        return super(SyncedModel, self).delete_instance(self)

    @classmethod
    def get_by_pk(cls, pk):
        """ Try to get a model from its primary key. """
        print cls.Sync.pk, pk
        print cls, getattr(cls, cls.Sync.pk), pk
        try:
            return cls.get(getattr(cls, cls.Sync.pk) == pk)
        except cls.DoesNotExist:
            print "DoesNotExist"
            return None

    @classmethod
    def sync(cls, debug=False):
        cls.sync_push(debug)
        cls.sync_pull(debug)

    @classmethod
    def sync_push(cls, debug=False):
        """ Process the local History and perform calls to the API. """
        # 1. PUSH
        last_sync = kv.get("last_dev_eve_sync_push", 0)

        for history in History.select().where(History.model == cls._meta.name,
                                              History.ts > last_sync):
            print "local history", history
            if history.action == "create":
                etag = post_resource(history.model, history.pk, history.data, raw_history=history._data)
                if etag:
                    kv["etag:{0}:{1}".format(history.model, history.pk)] = etag
            elif history.action == "update":
                etag = kv.get("etag:{0}:{1}".format(history.model, history.pk))
                patch_resource(history.model, history.pk, history.data, etag, raw_history=history._data)
            elif history.action == "delete":
                etag = kv.get("etag:{0}:{1}".format(history.model, history.pk))
                # TODO delete etag
                delete_resource(history.model, history.pk, etag, raw_history=history._data)
        kv['last_dev_eve_sync_push'] = int(datetime.utcnow().strftime("%s"))

    @classmethod
    def sync_pull(cls, debug=False):
        last_sync = kv.get("last_dev_eve_sync_pull", 0)

        # 2. PULL
        remote_history = get_remote_history(cls._meta.name, last_sync)
        for history in remote_history:
            print "remote history", history
            local = cls.get_by_pk(history["pk"])
            print "local", local
            if history["action"] == "create":
                if not local:
                    print "create from remote"
                    # Create from history data
                    cls.create(**json.loads(history["data"]))
                    # Retrieve ETag from remote API
                    remote = get_resource(history["model"], history["pk"])
                    kv["etag:{0}:{1}".format(history["model"], history["pk"])] = remote["etag"]
            elif history["action"] == "update":
                if local:
                    local.update(**json.loads(history["data"]))
                    # Retrieve ETag from remote API
                    remote = get_resource(history["model"], history["pk"])
                    kv["etag:{0}:{1}".format(history["model"], history["pk"])] = remote["etag"]
                else:
                    print "item doesn't exists !"
            elif history["action"] == "delete":
                if local:
                    local.delete_instance()
                else:
                    print "item doesn't exists !"

        kv["last_dev_eve_sync_pull"] = int(datetime.utcnow().strftime("%s"))
        # Faire l'appel a eve
        # ne pas oublier d'updater ETag

        # TODO cleaner le ETag model
        # TODO gerer la derniere date de sync
        # TODO sync ACK/confirmation
        # TODO => eve-client ?
        # TODO => peewee-eve-sync
        # TODO => tampon/buffer au cas ou API pas disponible
        # TODO => Ajouter des if debug: partout
        # TODO => tester le pk dans Meta au lieu de Sync
