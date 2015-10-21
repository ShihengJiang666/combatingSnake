# https://docs.djangoproject.com/en/1.8/topics/testing/tools/
from django.test import TestCase
from django.test import Client
from models import *
from django.core.exceptions import *
import json

class RestTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        self.sessionId = None
    def tearDown(self):
        self.sessionId = None

    def get(self, path, data=None, **extra):
        if self.sessionId:
            extra.update({'X-Snake-Session-Id' : self.sessionId})
        response = self.c.get(path, data = data, **extra)
        return response

    def post(self, path, data = None, **extra):
        if self.sessionId:
            extra.update({'X-Snake-Session-Id' : self.sessionId})
        extra.update({'data' : json.dumps(data) if data else None,
            'content_type' : 'application/json'})
        response = self.c.post(path, **extra)
        return response

    def put(self, path, data = None, **extra):
        if self.sessionId:
            extra.update({'X-Snake-Session-Id' : self.sessionId})
        extra.update({'data' : json.dumps(data) if data else None,
            'content_type' : 'application/json'})
        response = self.c.put(path, **extra)
        return response
    def delete(self, path, **extra):
        if self.sessionId:
            extra.update({'X-Snake-Session-Id' : self.sessionId})
        response = self.c.delete(path, **extra)
        return response

    def assertResponseSuccess(self, response, msg = None):
        '''
        Assert the response 2xx and 3xx, and return the parsed content
        '''
        self.assertLess(response.status_code, 400,
            'response is not successful with status code {} and content{}{}'
                .format(response.status_code,response.content,
                    ': {}'.format(msg) if msg else ''))
        return json.loads(response.content)

    def assertResponseFail(self, response, msg = None):
        '''
        Assert the response 4xx and 5xx, and return the parsed content
        '''
        self.assertGreaterEqual(response.status_code, 400,
            'response is successful with status code {} and content{}{}'
                .format(response.status_code,response.content,
                    ': {}'.format(msg) if msg else ''))
        d = json.loads(response.content)
        self.assertIn('err', d)
        return d

class UsersViewTestCase(RestTestCase):

    def testRegLogin(self):
        d = self.assertResponseSuccess(self.post('/users', {'username':'user','password':'pass'}))
        self.assertIn('userId', d)
        self.assertIn('sessionId', d)
        userId = d['userId']
        oldSessionId = d['sessionId']
        d = self.assertResponseSuccess(self.put('/users/login', {'username':'user','password':'pass'}))
        self.assertIn('userId', d)
        self.assertIn('sessionId', d)
        self.assertEquals(userId, d['userId'])
        self.assertNotEquals(oldSessionId, d['sessionId'])

        self.sessionId = d['sessionId']
        d = self.assertResponseSuccess(self.delete('/users/login'))
        with self.assertRaises(ObjectDoesNotExist):
            User.find_by_session_id(self.sessionId)

        self.assertResponseSuccess(self.delete('/users/login'), 'logging out again should not fail')
        self.sessionId = 'Invalid id'
        self.assertResponseSuccess(self.delete('/users/login'), 'logging out with invalid session id should not fail')

        self.assertEquals(userId, User.find_by_id(userId).strId) # assert that delete does not delete the user

    def testRegLogin2(self):
        self.assertResponseSuccess(self.post('/users', {'username':'user','password':'pass'}))
        self.sessionId = self.assertResponseSuccess(self.put('/users/login', {'username':'user','password':'pass'}))['sessionId']
        self.assertResponseFail(self.put('/users/login', {'username':'user','password':'qass'}))
        self.assertIsNotNone(User.find_by_session_id(self.sessionId))
        self.assertResponseSuccess(self.delete('/users/login'))
        self.assertResponseFail(self.put('/users/login', {'username':'user','password':'qass'}))
        self.assertResponseFail(self.put('/users/login', {'username':'user','password':'pass '}))
        with self.assertRaises(ObjectDoesNotExist):
            User.find_by_session_id(self.sessionId)
        self.assertResponseSuccess(self.put('/users/login', {'username':'user','password':'pass'}))['sessionId']

    def testUpdateProfile(self):
        pass # TODO tests for PUT /users/:userId

    def testUrlsPattern(self):
        k = 0
        userId = None
        while True:
            userId = self.assertResponseSuccess(self.post('/users', {'username':'user' + str(k),'password':'pass'}))['userId']
            k += 1
            toBreak = False
            for e in ('a','b','c','d','e','f'):
                if e in userId:
                    toBreak = True
                    break
            if toBreak:
                break
        anotherUserId = self.assertResponseSuccess(self.get('/users/' + userId))['userId']
        self.assertEquals(userId, anotherUserId)

class RoomsViewTestCase(RestTestCase):
    def setUp(self):
        RestTestCase.setUp(self)
        self.user = self.alice = self.assertResponseSuccess(self.post('/users', {'username':'alice','password':'pass','nickname':'alice'}));
        self.bob = self.assertResponseSuccess(self.post('/users', {'username':'bob','password':'pass','nickname':'bob'}));
        self.iAmAlice()

    def iAmAlice(self):
        self.sessionId = self.alice['sessionId']
    def iAmBob(self):
        self.sessionId = self.bob['sessionId']

    def testCreateBy(self):
        d = self.assertResponseSuccess(self.post('/rooms'))
        self.assertEquals(self.user['userId'], d['creator']['userId'])
        self.assertIn('roomId', d)
        self.assertTrue(d['roomId'], '{} is False or empty'.format(d['roomId']))

    def testGetRooms(self):
        roomIds = [self.assertResponseSuccess(self.post('/rooms'))['roomId']
            for _ in range(20)]
        gotArray = self.assertResponseSuccess(self.get('/rooms'))['rooms']
        gotRoomIds = [e['roomId'] for e in gotArray]
        self.assertEquals(set(roomIds), set(gotRoomIds))
        self.assertEquals(len(roomIds), len(gotRoomIds), 'GET /rooms size doesn\'t match')

        gotArrayLookup = dict()
        for e in gotArray:
            gotArrayLookup[e['roomId']] = e

        for roomId in roomIds:
            gotRoom = self.assertResponseSuccess(self.get('/rooms/' + roomId))
            self.assertEquals(gotArrayLookup[roomId], gotRoom)

    def testParams(self):
        self.iAmAlice()
        room = self.assertResponseSuccess(self.post('/rooms'))
        roomId = room['roomId']
        self.iAmBob()

        self.assertResponseSuccess(self.put('/rooms/' + roomId + '/members/' + self.bob['userId']))
        d = self.assertResponseSuccess(self.get('/rooms/' + roomId, {'creator-profile': True}))
        self.assertIn('creator',d)
        self.assertIn('nickname',d['creator'])
        self.assertEquals(self.alice['nickname'], d['creator']['nickname'])

        self.assertResponseSuccess(self.get('/rooms/' + roomId, {'members': True}))
        self.assertIn('members', d)
        members = d['members']
        self.assertIsInstance(members, list)
        self.assertEquals(1, len(members))
        self.assertEquals(self.bob['userId'], self[members][0]['userId'])

        self.assertResponseSuccess(self.get('/rooms/' + roomId, {'member-profile': True}))
        self.assertIn('members', d)
        members = d['members']
        self.assertIsInstance(members, list)
        self.assertEquals(1, len(members))
        self.assertEquals(self.bob['userId'], self[members][0]['userId'])
        self.assertEquals(self.bob['nickname'], self[members][0]['nickname'])


    def testUrls(self):
        resp = self.put('/rooms/a/members/b')
        print resp.status_code
        print resp
        self.assertNotEquals(405, resp.status_code)





