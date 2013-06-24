# -*- coding: utf-8 -*-

""" test_peewee_eve_sync.py - Test the peewee_eve_sync module. """

import unittest
import requests
from httpretty import HTTPretty
#from playhouse.test_utils import test_database
from sure import expect
from peewee import SqliteDatabase

test_db = SqliteDatabase(':memory:')


class TestDirtools(unittest.TestCase):
    def setUp(self):
        HTTPretty.enable()
        HTTPretty.register_uri(HTTPretty.GET, "http://yipit.com/",
                               body="Find the best daily deals")
        """
        HTTPretty.register_uri(HTTPretty.GET, "http://github.com/gabrielfalcao/httpretty",
                               responses=[
                                HTTPretty.Response(body="first response", status=201),
                                HTTPretty.Response(body='second and last response', status=202),
                                ])
        """

    def tearDown(self):
        HTTPretty.disable()

    def testOne(self):
        response = requests.get('http://yipit.com')
        expect(response.text).to.equal("Find the best daily deals")
        #("ok").should.equal("ok2")

if __name__ == '__main__':
    unittest.main()
