# -*- coding: utf-8 -*-
import peewee
from peewee import Query, not_allowed
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

db = peewee.SqliteDatabase(None)

SYNC_BUFFER = 2

"""
class UpdateQuerySync(Query):
    def __init__(self, model_class, update=None):
        self._update = update
        self.is_synced = issubclass(model_class, SyncedModel)
        if update and self.is_synced:
            for k, v in update.items():
                print k, type(k), k.__dict__, v
            self.update_data = dict([(k.db_column, v) for k, v in update.items()])
            print self.update_data
        super(UpdateQuerySync, self).__init__(model_class)

    def clone(self):
        query = super(UpdateQuerySync, self).clone()
        query._update = dict(self._update)
        return query

    join = not_allowed('joining')

    def sql(self):
        return self.compiler().generate_update(self)

    def execute(self):
        _execute = self._execute()
        _return = self.database.rows_affected(_execute)
        if self.is_synced:
            self.model_class.sync_auto()
        return _return

peewee.UpdateQuery = UpdateQuerySync
"""

def get_ts():
    return int(datetime.utcnow().strftime("%s"))

"""

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

"""


class SyncSettings:
    auto = True
    pk = "uuid"


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


class KeyValue(BaseModel):
    """ key => value store.

    This custom KeyValue is used instead of the one in peewee
    playground because it doesn't support deferred initialization.

    """
    key = peewee.CharField(index=True, unique=True)
    value = JsonField()

    @classmethod
    def get_key(self, key, default=None):
        try:
            return KeyValue.get(KeyValue.key == key).value
        except KeyValue.DoesNotExist:
            return default

    @classmethod
    def set_key(self, key, value=None):
        q = KeyValue.select().where(KeyValue.key == key)
        if q.count():
            KeyValue.update(value=value).where(KeyValue.key == key).execute()
        else:
            KeyValue.create(key=key, value=value)


def get_etag(model, pk):
    try:
        return KeyValue.get_key("etag:{0}:{1}".format(model, pk))
    except:
        return


def set_etag(model, pk, etag):
    KeyValue.set_key("etag:{0}:{1}".format(model, pk), etag)


def delete_etag(model, pk):
    try:
        key = "etag:{0}:{1}".format(model, pk)
        kv = KeyValue.get(KeyValue.key == key)
        kv.delete_instance()
    except:
        # TODO voir pq
        return

class History(BaseModel):
    """ History for sync.

    Track create/update/delete for synced models.

    """
    data = JsonField()
    ts = peewee.IntegerField(index=True)
    action = peewee.CharField()
    model = peewee.CharField(index=True)
    pk = peewee.CharField()
    uuid = peewee.CharField()

    @classmethod
    def create(cls, **attributes):
        """ Safe create, without syncing things. """
        attributes["uuid"] = uuid.uuid4()
        return super(History, cls).create(**attributes)

    @property
    def is_synced(self):
        return KeyValue.get_key("history:{0}".format(self.uuid), False)

    def synced(self):
        KeyValue.set_key("history:{0}".format(self.uuid), True)

    def __repr__(self):
        return "<History: {model}/{action}/{uuid}>".format(**self._data)

    class Meta:
        db_table = 'history'


class SyncedModel(BaseModel):
    """ A base model to sync a peewee Model over a Eve REST API.
    Synchronization is history based, and works with multiple clients.

    Limitations:

    - Update must be done on model instance
        by setting attribute and calling save/no update on mutltiple records.

    """
    def __repr__(self):
        return "<{0} {1} (sync)>".format(self._meta.name, self._data.get(self.Sync.pk))

    @classmethod
    def sync_auto(cls):
        if cls.Sync.auto and cls._meta.name != "history":
            log.debug("trigger sync auto")
            cls.sync()

    @classmethod
    def _select(cls, *selection):
        """ Safe select, without syncing things. """
        return super(SyncedModel, cls).select(*selection)

    @classmethod
    def select(cls, *selection):
        cls.sync_auto()
        return super(SyncedModel, cls).select(*selection)

    @classmethod
    def create(cls, **attributes):
        if cls._meta.name != "history":
            History.create(data=json.dumps(dict(**attributes)),
                           ts=get_ts(),
                           action="create",
                           model=cls._meta.name,
                           pk=attributes.get(cls.Sync.pk))
        return super(SyncedModel, cls).create(**attributes)

    @classmethod
    def _create(cls, **attributes):
        """ Safe create, without syncing things. """
        return super(SyncedModel, cls).create(**attributes)

    def save(self, force_insert=False, only=None):
        if self._meta.name != "history" and self.get_id():
            # we perform an update
            update_data = dict(self._data)
            if "id" in update_data:
                del update_data["id"]

            History.create(data=json.dumps(update_data),
                           ts=get_ts(),
                           action="update",
                           model=self._meta.name,
                           pk=self._data.get(self.Sync.pk))

        _return = super(SyncedModel, self).save(force_insert=False, only=None)
        self.sync_auto()

        return _return

    def _save(self, force_insert=False, only=None):
        """ Safe save, without syncing things. """
        return super(SyncedModel, self).save(force_insert=False, only=None)

    def delete_instance(self):
        if self._meta.name != "history":
            History.create(data={},
                           ts=get_ts(),
                           action="delete",
                           model=self._meta.name,
                           pk=self._data.get(self.Sync.pk))
        _return = super(SyncedModel, self).delete_instance()
        self.sync_auto()

        return _return

    def _delete_instance(self):
        """ Safe delete_instance, without syncing things. """
        return super(SyncedModel, self).delete_instance()

    @classmethod
    def get(cls, *query, **kwargs):
        cls.sync_auto()
        return cls._get(*query, **kwargs)

    @classmethod
    def _get(cls, *query, **kwargs):
        """ Rewrite of the orginal get to use _select instead of select. """
        sq = cls._select().naive()
        if query:
            sq = sq.where(*query)
        if kwargs:
            sq = sq.filter(**kwargs)
        return sq.get()

    @classmethod
    def get_by_pk(cls, pk):
        """ Try to get a model from its primary key. """
        try:
            return cls._get(getattr(cls, cls.Sync.pk) == pk)
        except cls.DoesNotExist:
            return None

    @classmethod
    def sync(cls, debug=True):
        if debug:
            log.debug("Starting sync")

        try:
            cls.sync_push(debug)
            cls.sync_pull(debug)
        except Exception, exc:
            log.error("Error while syncing")
            log.exception(exc)

        if debug:
            log.debug("End sync")

    @classmethod
    def sync_push(cls, debug=False):
        """ Process the local History and perform calls to the API. """
        # 1. PUSH
        if debug:
            log.debug("starting push")

        last_sync = KeyValue.get_key("last_dev_eve_sync_push", 0)
        if last_sync:
            last_sync -= SYNC_BUFFER
        for history in History.select().where(History.model == cls._meta.name,
                                              History.ts >= last_sync):
            if debug:
                log.debug("history.is_synced {0}".format(history.is_synced))

            if not history.is_synced:
                if debug:
                    log.debug("current local history: {0}".format(history))

                if history.action == "create":
                    etag = post_resource(history.model, history.pk, history.data, raw_history=history._data)
                    if etag:
                        set_etag(history.model, history.pk, etag)
                        history.synced()
                elif history.action == "update":
                    etag = get_etag(history.model, history.pk)
                    new_etag = patch_resource(history.model, history.pk, history.data, etag, raw_history=history._data)
                    # We update the etag locally
                    if new_etag:
                        set_etag(history.model, history.pk, new_etag)
                        history.synced()
                elif history.action == "delete":
                    etag = get_etag(history.model, history.pk)
                    delete_resource(history.model, history.pk, etag, raw_history=history._data)
                    history.synced()
                    if etag:
                        delete_etag(history.model, history.pk)

        KeyValue.set_key("last_dev_eve_sync_push", get_ts())

    @classmethod
    def sync_pull(cls, debug=False):
        last_sync = KeyValue.get_key("last_dev_eve_sync_pull", 0)

        if debug:
            log.debug("starting pull")

        # 2. PULL
        remote_history = get_remote_history(cls._meta.name, last_sync)
        for history in remote_history:
            log.info(history)
            if debug:
                log.debug("receiving remote history: {0}".format(history))

            local = cls.get_by_pk(history["pk"])

            if debug:
                log.debug("local model version: {0}".format(local))

            if history["action"] == "create":
                if not local:
                    if debug:
                        log.debug("create from remote")
                    # Create from history data
                    cls._create(**json.loads(history["data"]))
                    # Retrieve ETag from remote API
                    remote = get_resource(history["model"], history["pk"])
                    #print "REMOTE CREATE", remote, history
                    if remote:
                        set_etag(history["model"], history["pk"], remote["etag"])
                        #print "ETAG", get_etag(history["model"], history["pk"])
            elif history["action"] == "update":
                local_etag = get_etag(history["model"], history["pk"])
                # TODO voir pq le etag dans history
                if local and local_etag:
                    remote = get_resource(history["model"], history["pk"])
                    if remote:  #  voir pq utile pour la deletion
                        log.info("remote item to be updated: {0}".format(remote))
                        log.info(local_etag)
                        # The update is performed only if the remote model is different from local
                        if local_etag != remote["etag"]:
                            log.info(local._data)
                            for k, v in json.loads(history["data"]).items():
                                setattr(local, k, v)
                            local._save()
                            log.info("local update {0}".format(json.loads(history["data"])))
                            set_etag(history["model"], history["pk"], remote["etag"])
                else:
                    log.error("item doesn't exists !")

            elif history["action"] == "delete":
                if local:
                    local._delete_instance()
                    delete_etag(history["model"], history["pk"])
                else:
                    log.debug("Item already deleted")

        KeyValue.set_key("last_dev_eve_sync_pull", get_ts())

    class Sync(SyncSettings):
        pass
