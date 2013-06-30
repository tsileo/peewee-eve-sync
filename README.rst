=================
 Peewee-Eve-Sync
=================

Synchronization over a Eve powered REST API for Peewee Models.

Getting Started
===============

.. code-block:: python

    from peewee_eve_sync import SyncedModel, SyncSettings
    import peewee

    class MyModel(SyncedModel):
        field = peewee.CharField()

        class Sync(SyncSettings):
            pk = "uuid"


Limitations
===========

Peewee-Eve-Sync doesn't work with UpdateQuery and DeleteQuery.

Creating new model
------------------

Model.create() or initialize a empty model and call Model.save()

Update model
------------

Model.get(), then you update attr, and call Model.save()

Delete model
------------

Model.get(), then Model.delete_instance()

Auto Sync
---------

Auto sync is enabled by default, you disable it by setting the Sync setting auto to False.


.. code-block:: python

    Model.Sync.auto = False

TOTO
====

* Be able to sync records given a specific query (like sync only {cat:"cat1"})
