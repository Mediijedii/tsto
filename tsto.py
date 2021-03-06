#!/usr/bin/python

"""
TSTO tool.
WARNING: absolutly no warranties. Use this script at own risk.
"""

__author__ = 'jsbot@ya.ru (Oleg Polivets)'

import argparse
import logging
import requests
import json
import gzip
import StringIO
import time
import struct
import sys
import traceback
import random
import ld_pb2
import os.path
from stat import S_ISREG, ST_CTIME, ST_MODE

DESCRIPTION = 'The Simpsons Tapped Out tool'
URL_SIMPSONS = 'prod.simpsons-ea.com'
URL_OFRIENDS = 'm.friends.dm.origin.com'
URL_AVATAR = 'm.avatar.dm.origin.com'
URL_TNTAUTH = 'auth.tnt-ea.com'
URL_TNTNUCLEUS = 'nucleus.tnt-ea.com'
CT_PROTOBUF = 'application/x-protobuf'
CT_JSON = 'application/json'
CT_XML = 'application/xaml+xml'
ADB_SAVE_DIR = '/sdcard/Android/data/com.ea.game.simpsons4_row/files/save/'
VERSION_APP = '4.18.6'
VERSION_LAND = '35'


class TSTO:

    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)
        self.dataVerison = int(VERSION_LAND)
        self.mLogined = False
        self.mLandMessage = ld_pb2.LandMessage()
        self.mLandMessageExtra = None
        self.headers = dict()
        self.headers["Accept"] = "*/*"
        self.headers["Accept-Encoding"] = "gzip"
        self.headers["client_version"] = VERSION_APP
        self.headers["server_api_version"] = "4.0.0"
        self.headers["EA-SELL-ID"] = "857120"
        self.headers["platform"] = "android"
        self.headers["os_version"] = "15.0.0"
        self.headers["hw_model_id"] = "0 0.0"
        self.headers["data_param_1"] = "2633815347"
        self.mMhClientVersion = "Android." + VERSION_APP
        self.mSesSimpsons = requests.Session()
        self.mSesOther = requests.Session()
        self.mUid = None
        self.mPrompt = "tsto > "
        self.tokenLoadDefault()

### Network ###

    def doRequest(self, method, content_type, host, path, keep_alive=False, body=[], uncomressedLen=-1):
        url = ("https://%s%s" % (host, path)).encode('utf-8')

        # filling headers for this request
        headers = self.headers.copy()
        if uncomressedLen > -1:
            headers["Content-Encoding"] = "gzip"
            headers["Uncompressed-Length"] = uncomressedLen
            headers["Content-Length"] = len(body)

        if keep_alive == True:
            headers["Connection"] = "Keep-Alive"
            ssn = self.mSesSimpsons if host == URL_SIMPSONS else self.mSesOther
        else:
            headers["Connection"] = "Close"
            ssn = requests
        headers["Content-Type"] = content_type

        # do request
        if method == "POST":
            r = ssn.post(url=url, headers=headers, verify=False, data=body)
        elif method == "GET":
            r = ssn.get(url=url, headers=headers, verify=False)
        elif method == "PUT":
            r = ssn.put(url=url, headers=headers, verify=False)

        # reading response
        data = r.content

        if (len(data) == 0):
            logging.debug("no content")
        else:
            if r.headers['Content-Type'] == 'application/x-protobuf':
                logging.debug(r.headers['Content-Type'])
            else:
                logging.debug(data)
        return data

    def protobufParse(self, msg, data):
        parsed = True
        try:
            msg.ParseFromString(data)
        except Exception:
            parsed = False
        return parsed

    def checkLogined(self):
        if self.mLogined != True:
            raise TypeError("ERR: need to login before perform this action!!!")

    def checkDownloaded(self):
        if self.mLandMessage.id == '':
            raise TypeError("ERR: LandMessage.id is empty!!!")

    def doTokenDelete(self):
        self.checkLogined()
        dtr = ld_pb2.DeleteTokenRequest()
        dtr.token = self.mUpdateToken
        data = dtr.SerializeToString()
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/deleteToken/%s/protoWholeLandToken/" % (self.mUid), True, data)
        dtr = ld_pb2.DeleteTokenResponse()
        dtr.ParseFromString(data)
        if dtr.result == False:
            print("FAIL")
        else:
            self.mLandMessageExtra = None
            self.mLandMessage = ld_pb2.LandMessage()
            self.mLogined = False
            self.mPrompt = "tsto > "
            print("OK")

    def doAuth(self, args):
        email = args[1]
        password = args[2]
        data = self.doRequest("POST", CT_JSON, URL_TNTNUCLEUS,
                              "/rest/token/%s/%s/" % (email, password), True)
        data = json.JSONDecoder().decode(data)
        self.mUserId = data["userId"]
        self.mEncrToken = data["encryptedToken"]
        self.doAuthWithToken(data["token"])
        self.tokenStore()

    def doAuthWithCryptedToken(self, cryptedToken):
        data = self.doRequest("POST", CT_JSON, URL_TNTNUCLEUS,
                              "/rest/token/validate", True, self.mToken)
        data = self.doRequest("POST", CT_JSON, URL_TNTNUCLEUS,
                              "/rest/token/%s/" % (cryptedToken), True)
        data = json.JSONDecoder().decode(data)
        self.mUserId = data["userId"]
        self.mEncrToken = data["encryptedToken"]
        self.doAuthWithToken(data["token"])

    def doAuthWithToken(self, token):
        self.mToken = token
        self.headers["nucleus_token"] = token
        self.headers["AuthToken"] = token

        data = self.doRequest("GET", CT_JSON, URL_TNTAUTH,
                              "/rest/oauth/origin/%s/Simpsons-Tapped-Out/" % self.mToken, True)
        data = json.JSONDecoder().decode(data)
        self.mCode = data["code"]
        self.mTntId = data["tntId"]
        self.headers["mh_auth_method"] = "tnt"
        self.headers["mh_auth_params"] = data["code"]
        self.headers["mh_client_version"] = self.mMhClientVersion

        data = self.doRequest("PUT", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/users?appVer=2.2.0&appLang=en&application=tnt&applicationUserId=%s" % self.mTntId, True)
        urm = ld_pb2.UsersResponseMessage()
        urm.ParseFromString(data)
        self.mUid = urm.user.userId
        self.mSession = urm.token.sessionKey
        self.headers["mh_uid"] = self.mUid
        self.headers["mh_session_key"] = self.mSession

        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/checkToken/%s/protoWholeLandToken/" % (self.mUid), True)
        wltr = ld_pb2.WholeLandTokenRequest()
        if self.protobufParse(wltr, data) == False:
            wltr = ld_pb2.WholeLandTokenRequest()
            wltr.requestId = self.mTntId
            data = wltr.SerializeToString()
            data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS,
                                  "/mh/games/bg_gameserver_plugin/protoWholeLandToken/%s/" % self.mUid, True, data)
            wltr = ld_pb2.WholeLandTokenRequest()
            wltr.ParseFromString(data)
        self.mUpdateToken = wltr.requestId
        self.headers["target_land_id"] = self.mUid
        self.headers["land-update-token"] = self.mUpdateToken
        self.mLogined = True
        print("OK")

    def doLandDownload(self):
        self.checkLogined()
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/protoland/%s/" % self.mUid, True)
        self.mLandMessage = ld_pb2.LandMessage()
        self.mLandMessage.ParseFromString(data)
        self.mPrompt = "%s@tsto > " % self.mLandMessage.friendData.name
        # make backup
        self.doFileSave(('save', "%s.%f" % (self.mUid, time.time())))

    def doLandUpload(self):
        self.checkLogined()
        self.checkDownloaded()
        # send extra message before landMessage if any
        self.doUploadExtraLandMessage()
        # store last played time and send GZipped Land itself
        self.mLandMessage.friendData.lastPlayedTime = int(time.time())
        data = self.mLandMessage.SerializeToString()
        uncomressedLen = len(data)
        out = StringIO.StringIO()
        g = gzip.GzipFile(fileobj=out, mode="w")
        g.write(data)
        g.close()
        data = out.getvalue()
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/protoland/%s/" % self.mUid, True, data, uncomressedLen)

    def doLoadCurrency(self):
        self.checkLogined()
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/protocurrency/%s/" % self.mUid, True)
        currdat = ld_pb2.CurrencyData()
        currdat.ParseFromString(data)
        print(str(currdat))
        return currdat

    def doDownloadFriendsData(self):
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/friendData?debug_mayhem_id=%s" % self.mUid, True)
        fdresp = ld_pb2.GetFriendDataResponse()
        fdresp.ParseFromString(data)
        return fdresp

    def doUploadExtraLandMessage(self):
        msg = self.mLandMessageExtra
        if msg == None:
            return
        data = msg.SerializeToString()
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/extraLandUpdate/%s/protoland/" % self.mUid, True, data)
        self.mLandMessageExtra = None

    def getExtraLandMessage(self):
        if self.mLandMessageExtra == None:
            self.mLandMessageExtra = ld_pb2.ExtraLandMessage()
        return self.mLandMessageExtra

    def doResetNotifications(self):
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/event/%s/protoland/" % self.mUid, True)
        if len(data) == 0:
            return
        events = ld_pb2.EventsMessage()
        events.ParseFromString(data)
        if self.protobufParse(events, data) == False:
            return
        extra = self.getExtraLandMessage()
        alreadyDone = set()
        for ev in events.event:
            if ev.id in alreadyDone:
                continue
            xev = extra.event.add()
            xev.id = ev.id
            alreadyDone.add(ev.id)
        data = self.doRequest("POST", CT_XML, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/usernotificationstatus/?type=reset_count", True)
        data = self.doRequest("POST", CT_XML, URL_SIMPSONS,
                              "/mh/games/bg_gameserver_plugin/usernotificationstatus/?type=reset_time", True)
        print("TIP: don't forget execute upload or uploadextra")

    # show sorted friends list

    def friendsShow(self):
        self.checkLogined()
        friends = self.doDownloadFriendsData()
        fds = []
        for fd in friends.friendData:
            f = fd.friendData
            fds.append("%s|%d|%s|%s|%s" % (
                time.strftime("%Y%m%d%H%M", time.localtime(f.lastPlayedTime)),
                f.level,
                fd.externalId,
                fd.friendId,
                f.name))
        fds.sort()
        print("LASTPLAYTIME | LEVEL | ORIGINID | MYHEMID | NAME")
        for f in fds:
            print(f)

    # drop single Origin friend by its id

    def friendDrop(self, args):
        self.checkLogined()
        self.checkDownloaded()
        friendOriginId = int(args[1])
        # resolve myhemId of Origin user
        friendMyhemId = ''
        for fd in self.doDownloadFriendsData().friendData:
            if fd.externalId == friendOriginId:
                friendMyhemId = fd.friendId
                break

        if friendMyhemId == '':
            raise TypeError("ERR: nothing found.")

        # resolve its index in current user land
        friendIdx = -1
        for idx in range(len(self.mLandMessage.friendListData)):
            fld = self.mLandMessage.friendListData[idx]
            if fld.friendID == friendMyhemId:
                friendIdx = idx
                break

        if friendIdx == -1:
            raise TypeError("ERR: not found friendIdx.")

        # delete
        self.doRequest("GET", CT_JSON, URL_OFRIENDS,
                       "/friends/deleteFriend?nucleusId=%s&friendId=%s" % (self.mUserId, friendOriginId))
        del self.mLandMessage.friendListData[friendIdx]
        self.mLandMessage.innerLandData.numSavedFriends = len(
            self.mLandMessage.friendListData)

    # drop friends that not playing more given days

    def friendsDropNotActive(self, args):
        self.checkLogined()
        self.checkDownloaded()
        days = 90
        if len(args) > 1:
            days = int(args[1])
        self.checkLogined()
        ts = time.mktime(time.localtime())
        crit = (24 * 60 * 60 * days)
        friends = self.doDownloadFriendsData()

#        for key, value in self.headers.items():
#            print (key, value)

#        self.doRequest("GET", CT_JSON, URL_OFRIENDS
#            , "//friends/user/%s/pendingfriends" % (self.mUserId)
#            , True)
#        self.doRequest("GET", CT_JSON, URL_OFRIENDS
#            , "//friends/user/%s/globalgroup/friendIds" % (self.mUserId)
#            , True)

        # find what don't need to delete
        notDel = []
        delAll = False
        for fd in friends.friendData:
            f = fd.friendData
            if (ts - f.lastPlayedTime) < crit:
                notDel.append(fd.friendId)
                continue
            print("%s|%d|%s|%s|%s" % (
                time.strftime("%Y%m%d%H%M", time.localtime(f.lastPlayedTime)),
                f.level,
                fd.externalId,
                fd.friendId,
                f.name))
            # user is confirmed?
            if delAll == False:
                inp = raw_input("Drop this friend (Y/N/A) ").lower()
                delAll = (inp == 'a')
            if delAll or inp == 'y':
                self.doRequest("GET", CT_JSON, URL_OFRIENDS, "/friends/deleteFriend?nucleusId=%s&friendId=%s" %
                               (self.mUserId, fd.externalId), True)
        # get indexes for deletion
        forDel = []
        for i in range(len(self.mLandMessage.friendListData)):
            f = self.mLandMessage.friendListData[i]
            if f.friendID not in notDel:
                forDel.insert(0, i)
        # delete by indexes
        for i in forDel:
            del self.mLandMessage.friendListData[i]
        self.mLandMessage.innerLandData.numSavedFriends = len(
            self.mLandMessage.friendListData)

    # show some date/time info for this land

    def showTimes(self):
        tm = time.gmtime(self.mLandMessage.innerLandData.timeSpentPlaying)
        timeSpentPlaying = "%d year(s) %d month(s) %d days %d h %d m" % (1970 - tm.tm_year,
                                                                         tm.tm_mon - 1, tm.tm_mday, tm.tm_hour, tm.tm_min)
        print("""friendData.lastPlayedTime: %s
userData.lastBonusCollection: %s
innerLandData.timeSpentPlaying: %s
innerLandData.creationTime: %s""" % (
            time.ctime(self.mLandMessage.friendData.lastPlayedTime),
            time.ctime(self.mLandMessage.userData.lastBonusCollection),
            timeSpentPlaying,
            time.ctime(self.mLandMessage.innerLandData.creationTime)))

### In-game items ###

    def donutsAdd(self, args):
        amount = int(args[1])
        elm = self.getExtraLandMessage()
        nextId = self.mLandMessage.innerLandData.nextCurrencyID
        sum = 0
        while sum < amount:
            cur = random.randint(499, 500)
            if sum + cur > amount:
                cur = amount - sum
            delta = elm.currencyDelta.add()
            delta.id = nextId
            delta.reason = "JOB"
            delta.amount = cur
            nextId += 1
            sum += cur
        self.mLandMessage.innerLandData.nextCurrencyID = nextId
        print("TIP: don't forget execute upload or uploadextra")

    def colliderRecharge(self):
        # get instance id
        id = self.mLandMessage.innerLandData.nextInstanceID

        # get list
        dl = self.mLandMessage.userData.powerupDataList.powerupData

        # clean powerupDataList items
        for i in reversed(range(len(dl))):
            del dl[i]

        # timestamp
        ts = int(time.time())

        # create a new items
        pd = dl.add()
        pd.entityID = id
        pd.timeBeganMS = ((ts + (24 * 60 * 60 * 19)) * 1000) + 953
        pd.powerupTypeID = 5
        pd.stateEnum = 2

        pd = dl.add()
        pd.entityID = id + 1
        pd.powerupTypeID = 5
        pd.stateEnum = 1

        # set varibles
        self.varChange(('vc', 'NewUserPowerUps_StartTime', ts))
        ts = ts + (24 * 60 * 60 * 1)
        self.varChange(('vc', 'NewUserPowerUps_ResurfaceTime', ts))

        # save instance counter
        self.mLandMessage.innerLandData.nextInstanceID = id + 2

    def arrSplit(self, arr):
        itms = []
        for it in arr.split(','):
            tt = it.split('-')
            if (len(tt) >= 2 and int(tt[0]) < int(tt[1])):
                for i in range(int(tt[0]), int(tt[1]) + 1):
                    itms.append(i)
            else:
                itms.append(int(tt[0]))
        return itms

    def inventoryAdd(self, args):
        itemsid = args[1]
        itemtype = 0
        count = 1
        if len(args) > 2:
            itemtype = int(args[2])
        if len(args) > 3:
            count = int(args[3])

        items = self.arrSplit(itemsid)
        # now add
        for it in items:
            # item exists?
            found = False
            for item in self.mLandMessage.inventoryItemData:
                if item.itemID == it and item.itemType == itemtype:
                    # item found, change its amount
                    found = True
                    self.inventoryCount(('ic', it, itemtype, count))
                    break
            # already exists? then precess next item
            if found == True:
                continue
            # or add item with given itemid and itemtype
            # into inventory
            t = self.mLandMessage.inventoryItemData.add()
            t.header.id = self.mLandMessage.innerLandData.nextInstanceID
            t.itemID = it
            t.itemType = itemtype
            t.count = count
            t.isOwnerList = False
            t.fromLand = 0
            t.sourceLen = 0
            self.mLandMessage.innerLandData.nextInstanceID = t.header.id + 1
            self.mLandMessage.innerLandData.numInventoryItems = len(
                self.mLandMessage.inventoryItemData)

    def inventoryCount(self, args):
        itemid = int(args[1])
        itemtype = int(args[2])
        count = int(args[3])
        it = -1
        for i in range(len(self.mLandMessage.inventoryItemData)):
            item = self.mLandMessage.inventoryItemData[i]
            if item.itemID == itemid and item.itemType == itemtype:
                it = i
                break
        if count <= 0:
            if it != -1:
                del self.mLandMessage.inventoryItemData[it]
                self.mLandMessage.innerLandData.numInventoryItems = len(
                    self.mLandMessage.inventoryItemData)
        else:
            if it != -1:
                self.mLandMessage.inventoryItemData[it].count = count
            else:
                self.inventoryAdd(('ia', str(itemid), itemtype, count))

    def spendablesShow(self):
        self.checkLogined()
        if (len(self.mLandMessage.spendablesData.spendable) == 0):
            raise TypeError("ERR: Download land first.")
        donuts = self.doLoadCurrency()
        print("donuts=%s" % (donuts.vcBalance))
        print("money=%s" % (self.mLandMessage.userData.money))
        for sp in self.mLandMessage.spendablesData.spendable:
            print("%d=%d" % (sp.type, sp.amount))

    def spendableSet(self, args):
        amount = int(args[2])
        types = self.arrSplit(args[1])
        notExist = types[:]
        # set amount for exists spendables and
        for sp in self.mLandMessage.spendablesData.spendable:
            if sp.type in types:
                notExist.remove(sp.type)
                sp.amount = amount
                for s in self.mLandMessage.friendData.spendable:
                    if s.type == sp.type:
                        s.amount = sp.amount
        # create not exists spendables
        for sp in notExist:
            sd = self.mLandMessage.spendablesData.spendable.add()
            sd.type = int(sp)
            sd.amount = amount

    def spendableAdd(self, args):
        amount = int(args[2])
        types = self.arrSplit(args[1])
        notExist = types[:]
        # set amount for exists spendables and
        for sp in self.mLandMessage.spendablesData.spendable:
            if sp.type in types:
                notExist.remove(sp.type)
                sp.amount += amount
                if sp.amount < 0:
                    sp.amount = 0
                for s in self.mLandMessage.friendData.spendable:
                    if s.type == sp.type:
                        s.amount = sp.amount
        # create not exists spendables
        for sp in notExist:
            sd = self.mLandMessage.spendablesData.spendable.add()
            sd.type = int(sp)
            sd.amount = amount

    def configShow(self):
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS, "/mh/games/bg_gameserver_plugin/protoClientConfig"
                              "/?id=ca0ddfef-a2c4-4a57-8021-27013137382e", True)
        cliConf = ld_pb2.ClientConfigResponse()
        cliConf.ParseFromString(data)

        data = self.doRequest("GET", CT_PROTOBUF,
                              URL_SIMPSONS, "/mh/gameplayconfig", True)
        gameConf = ld_pb2.GameplayConfigResponse()
        gameConf.ParseFromString(data)

        print("[protoClientConfig]")
        for item in cliConf.items:
            print("%s=%s" % (item.name, item.value))

        print("[gameplayconfig]")
        for item in gameConf.item:
            print("%s=%s" % (item.name, item.value))

    def skinsSet(self, args):
        data = args[1]
        self.mLandMessage.skinUnlocksData.skinUnlock = data
        self.mLandMessage.skinUnlocksData.skinReceived = data
        self.mLandMessage.skinUnlocksData.skinUnlockLen = len(data)
        self.mLandMessage.skinUnlocksData.skinReceivedLen = len(data)

    def skinsAdd(self, args):
        unlocked = self.mLandMessage.skinUnlocksData.skinUnlock
        skins = self.arrSplit(unlocked)
        toAdd = self.arrSplit(args[1])
        for skinId in toAdd:
            if skinId not in skins:
                unlocked += "," + str(skinId)
        self.skinsSet(('ss', unlocked))

    def buildingsMove(self, args):
        building = int(args[1])
        x = int(args[2])
        y = int(args[3])
        flip = int(args[4])

        for b in self.mLandMessage.buildingData:
            if b.building == building:
                b.positionX = x
                b.positionY = y
                b.flipState = flip

    def moneySet(self, args):
        amount = int(args[1])
        self.mLandMessage.userData.money = amount

    def levelSet(self, args):
        level = int(args[1])
        self.mLandMessage.friendData.level = level
        self.mLandMessage.userData.level = level

    def hurry(self):
        for job in self.mLandMessage.jobData:
            job.state = 2

    def questComplete(self, args):
        quests = tsto.arrSplit(args[1])
        for id in quests:
            # find questData for each quest
            qst = None
            for q in self.mLandMessage.questData:
                if q.questID == id:
                    qst = q
                    break
            # not found?
            if qst == None:
                # then create new one
                qst = self.mLandMessage.questData.add()
                qst.questID = id
                qst.timesCompleted = 0
                qst.header.id = self.mLandMessage.innerLandData.nextInstanceID
                self.mLandMessage.innerLandData.nextInstanceID = qst.header.id + 1
                self.mLandMessage.innerLandData.numQuests = len(
                    self.mLandMessage.questData)
            qst.questState = 5
            qst.numObjectives = 0
            qst.questScriptState = 0
            qst.timesCompleted += 1
            # delete objective data
            for i in reversed(range(len(qst.objectiveData))):
                del qst.objectiveData[i]

    def questsShow(self):
        print("questState | timesCompleted | numObjectives | questID")
        for q in self.mLandMessage.questData:
            if q.numObjectives > 0:
                print("%s | %s | %s | %s" % (q.questState,
                                             q.timesCompleted, q.numObjectives, q.questID))

    def getSpecialEvent(self, specialEventId):
        for e in self.mLandMessage.specialEventsData.specialEvent:
            if e.id == specialEventId:
                se = e
                break
        if se == None:
            raise TypeError("ERR: specialEvent with given id not found.")
        return se

    def nextPrizeSet(self, args):
        specialEventId = int(args[1])
        nextPrize = int(args[2])
        index = int(args[3]) if (len(args) >= 4) else 0
        se = self.getSpecialEvent(specialEventId)
        se.prizeDataSet.prizeData[index].nextPrize = nextPrize

    def cleanPurchases(self):
        self.checkDownloaded()
        self.mLandMessage.ClearField("processedPurchaseData")
        for i in reversed(range(len(self.mLandMessage.purchases))):
            del self.mLandMessage.purchases[i]
        for i in reversed(range(len(self.mLandMessage.amazonDimensionSet))):
            del self.mLandMessage.amazonDimensionSet[i]
        self.mLandMessage.userData.firstPurchase = False

    def cleanR(self):
        oX = 16
        oY = 13
        maxX = 32
        maxY = 32
        data = ''
        for row in range(oY):
            for col in range(oX):
                data += '1'
            for col in range(maxX - oX):
                data += '0'
        for i in range(maxY * (maxY - oY)):
            data += '0'

        self.mLandMessage.friendData.dataVersion = self.dataVerison
        self.mLandMessage.innerLandData.landBlocks = data
        self.mLandMessage.friendData.boardwalkTileCount = 0
        self.mLandMessage.innerLandData.landBlockWidth = maxX
        self.mLandMessage.innerLandData.landBlockHeight = maxY

        data = ''
        for i in range((oX - 2) * oY * 16):
            data += 'G'

        self.mLandMessage.roadsData.mapDataSize = len(data)
        self.mLandMessage.roadsData.mapData = data
        self.mLandMessage.riversData.mapDataSize = len(data)
        self.mLandMessage.riversData.mapData = data

        data = ''
        for i in range(2 * oY * 16):
            data += 'G'

        self.mLandMessage.oceanData.mapDataSize = len(data)
        self.mLandMessage.oceanData.mapData = data

    def cleanDebris(self):
        idx2del = []
        for idx, b in enumerate(self.mLandMessage.buildingData):
            if b.building in (1026, 1034, 1035, 1036, 1037, 3115, 3118, 3126, 3128, 3131):
                idx2del.insert(0, idx)
        for idx in idx2del:
            del self.mLandMessage.buildingData[idx]

    # change value of given specialEvent or objectVariables variable

    def varChange(self, args):
        value = args[2]
        for name in args[1].split(','):
            found = False
            for e in self.mLandMessage.specialEventsData.specialEvent:
                for v in e.variables.variable:
                    if v.name == name:
                        found = True
                        v.value = int(value)
                        break
            if found == False:
                for v in self.mLandMessage.objectVariables.variables.variable:
                    if v.name == name:
                        found = True
                        v.value = str(value)
                        break
            if found == False:
                raise ValueError(
                    "ERR: can't found variable with name='%s'" % name)

    # print all land variables

    def varsPrint(self, args):
        names = None
        if (len(args) > 1):
            names = args[1]
        printAll = names == None
        if printAll == False:
            ns = names.split(',')
        print("[specialEvent]")
        for e in self.mLandMessage.specialEventsData.specialEvent:
            for v in e.variables.variable:
                if printAll == False and ns.count(v.name) == 0:
                    continue
                print("%s=%s" % (v.name, v.value))
        print("[objectVariables]")
        for v in self.mLandMessage.objectVariables.variables.variable:
            if printAll == False and ns.count(v.name) == 0:
                continue
            print("%s=%s" % (v.name, v.value))

    def setGamblingType(self, args):
        self.checkDownloaded()
        gtypes = (
            "BOX",
            "QUEST",
            "DAILYBONUS",
            "REWARDCONSUMABLE",
            "SCRIPTEDEVENT",
            "REWARDPRIZE",
            "PROJECT",
            "BAG")
        gt = None
        if (len(args) > 1):
            gt = args[1]
        if (gt not in gtypes):
            gt = types[0]
        self.mLandMessage.userData.gambleItemType = gt

    def nextInstanceIDSet(self, args):
        self.checkDownloaded()
        self.mLandMessage.innerLandData.nextInstanceID = int(args[1])

    def showId(self):
        print("%s" % self.mLandMessage.id)

### Operations with files ###

    def doSaveAsText(self):
        self.checkDownloaded()
        with open("dbg.%s.txt" % self.mLandMessage.id, "w") as f:
            f.write(str(self.mLandMessage))

    def doSaveExtraAsText(self):
        self.checkDownloaded()
        with open("dbg.%sExtra.txt" % self.mLandMessage.id, "w") as f:
            f.write(str(self.mLandMessageExtra))

    def messageStoreToFile(self, fn, msg):
        data = msg.SerializeToString()
        with open(fn, "wb") as f:
            f.write(struct.pack('i', int(time.time())))
            f.write(struct.pack('i', 0))
            f.write(struct.pack('i', len(data)))
            f.write(data)

    def messageLoadFromFile(self, fn, msg):
        with open(fn, "rb") as f:
            f.seek(0x0c)
            data = f.read()
        msg.ParseFromString(data)
        return msg

    def doFileSave(self, args):
        self.messageStoreToFile(args[1], self.mLandMessage)

    def doFileOpen(self, args):
        self.mLandMessage = self.messageLoadFromFile(
            args[1], ld_pb2.LandMessage())
        self.mUid = self.mLandMessage.id
        self.mPrompt = "%s@tsto > " % self.mLandMessage.friendData.name

    def doFileSaveExtra(self, args):
        self.messageStoreToFile(args[1], self.mLandMessageExtra)

    def doFileOpenExtra(self, args):
        self.mLandMessageExtra = self.messageLoadFromFile(
            args[1], ld_pb2.ExtraLandMessage())

    def tokenPath(self):
        return os.path.join(os.path.expanduser('~'), '.tsto.conf')

    def tokenStore(self):
        self.checkLogined()
        with open(self.tokenPath(), 'w') as f:
            f.write(self.mToken + '\n')
            f.write(self.mEncrToken + '\n')
            f.write(self.mUid + '\n')

    def tokenForget(self):
        os.remove(self.tokenPath())

    def tokenLoadDefault(self):
        try:
            content = list()
            with open(self.tokenPath(), 'r') as f:
                content = [x.strip('\n') for x in f.readlines()]
            if len(content) >= 3:
                self.mToken = content[0]
                self.mEncrToken = content[1]
                self.mUid = content[2]
                return True
        except:
            pass
        return False

    def tokenLogin(self):
        if self.tokenLoadDefault():
            self.doAuthWithCryptedToken(self.mEncrToken)
        else:
            raise TypeError("ERR: wrong file format.")

    def doAdbPull(self):
        files = os.popen('adb shell "ls %s"' % ADB_SAVE_DIR).read()
        print(files)
        if self.mUid not in files:
            raise TypeError(
                "ERR: LandMessage file not found in save directory.")
        fn = '%s.%f' % (self.mUid, time.time())
        os.popen('adb pull "%s%s" %s' % (ADB_SAVE_DIR, self.mUid, fn))
        os.popen('adb pull "%s%sExtra" %sExtra' %
                 (ADB_SAVE_DIR, self.mUid, fn))
        self.doFileOpen(('load', fn))
        try:
            self.doFileOpenExtra(('loadextra', fn + 'Extra'))
        except:
            pass

    def doAdbPush(self):
        os.popen('adb shell "rm %s%sB"' % (ADB_SAVE_DIR, self.mUid))
        os.popen('adb shell "rm %s%sExtraB"' % (ADB_SAVE_DIR, self.mUid))
        os.popen('adb shell "rm %sLogMetricsSave"' % (ADB_SAVE_DIR))
        os.popen('adb shell "rm %sLogMessagesSave"' % (ADB_SAVE_DIR))
        fn = '%s.%f' % (self.mUid, time.time())
        self.doFileSave(('save', fn))
        os.popen('adb push "%s" "%s%s"' % (fn, ADB_SAVE_DIR, self.mUid))
        try:
            self.doFileSaveExtra(('saveextra', fn + 'Extra'))
            os.popen('adb push "%sExtra" "%s%sExtra"' %
                     (fn, ADB_SAVE_DIR, self.mUid))
        except:
            pass

    def backupsShow(self):
        if self.mUid == None:
            raise TypeError("ERR: I don't know your mayhem ID. Login first.")
        begining = self.mUid + '.'
        entries = (fn for fn in os.listdir('.') if fn.startswith(begining))
        entries = ((os.stat(path), path) for path in entries)
        entries = ((stat[ST_CTIME], path)
                   for stat, path in entries if S_ISREG(stat[ST_MODE]))
        for cdate, path in sorted(entries):
            print ("%s | %s" % (time.ctime(cdate), os.path.basename(path)))

    def doQuit(self):
        sys.exit(0)

    def doHelp(self):
        print("""SUPPORTED COMMANDS
login email pass     - login origin account
download             - download LandMessage
showtimes            - show some times variables from LandMessage
friends              - show friends info
friendsdrop days=90  - drop friends who not playing more then given amount
frienddrop ORIGINID  - drop friend by its Origin id
resetnotif           - clear neighbor handshakes
protocurrency        - show ProtoCurrency information
upload               - upload current LandMessage to mayhem server
uploadextra          - upload current ExtraLandMessage to mayhem server
config               - show current game config variables

tokenstore           - store current logined token in home dir
tokenforget          - remove stored encrypted token file
tokenlogin           - login by token stored in file in home dir
tokdel               - close current update token

load filepath        - load LandMessage from local filepath
save filepath        - save LandMessage to local filepath
astext               - save LandMessage text representation into file

adbpull              - pull/push LandMessage and ExtraLandMessage from
adbpush                local device save path using Android Debug Bridge

prizeset id number   - set current prize number for specialEvent with given id 
vs name[,name] val   - set variable(s) to value
vars [name[,name]]   - print variables with given names or all
donuts count         - set donuts for logined acc to count
ia ids type count=1  - add item(s) with id and type into inventory
ic id type count     - set count item with id and type
spendable id count   - set count spendable with id
money count          - set money count
ss 1,2,3             - set skins to (see: skinsmasterlist.xml)
sa 60,73             - append skins with ids 60 and 73 into unlocked
setlevel level       - set current level (be careful)
qc id                - complete quest with id
quests               - show not completed quests
hurry                - done all jobs and rewards
bm id x y flip       - set positions for all buildings with id
cleanr               - clear roads, rivers, broadwalk
cleandebris          - clean debris in subland 1 and 2
help                 - this message
quit                 - exit""")

if __name__ != '__main__':
    sys.exit(0)
tsto = TSTO()
cmdwarg = {
    "sa": tsto.skinsAdd,
    "ss": tsto.skinsSet,
    "vs": tsto.varChange,
    "ia": tsto.inventoryAdd,
    "ic": tsto.inventoryCount,
    "qc": tsto.questComplete,
    "bm": tsto.buildingsMove,
    "sgt": tsto.setGamblingType,
    "vars": tsto.varsPrint,
    "load": tsto.doFileOpen,
    "save": tsto.doFileSave,
    "login": tsto.doAuth,
    "money": tsto.moneySet,
    "sniid": tsto.nextInstanceIDSet,
    "donuts": tsto.donutsAdd,
    "setlevel": tsto.levelSet,
    "prizeset": tsto.nextPrizeSet,
    "spendable": tsto.spendableSet,
    "loadextra": tsto.doFileOpenExtra,
    "saveextra": tsto.doFileSaveExtra,
    "frienddrop": tsto.friendDrop,
    "friendsdrop": tsto.friendsDropNotActive,
    "spendableadd": tsto.spendableAdd,
}
cmds = {
    "id": tsto.showId,
    "quit": tsto.doQuit,
    "help": tsto.doHelp,
    "hurry": tsto.hurry,
    "tokdel": tsto.doTokenDelete,
    "upload": tsto.doLandUpload,
    "config": tsto.configShow,
    "quests": tsto.questsShow,
    "cleanr": tsto.cleanR,
    "astext": tsto.doSaveAsText,
    "adbpull": tsto.doAdbPull,
    "adbpush": tsto.doAdbPush,
    "backups": tsto.backupsShow,
    "friends": tsto.friendsShow,
    "download": tsto.doLandDownload,
    "recharge": tsto.colliderRecharge,
    "showtimes": tsto.showTimes,
    "resetnotif": tsto.doResetNotifications,
    "spendables": tsto.spendablesShow,
    "tokenlogin": tsto.tokenLogin,
    "tokenstore": tsto.tokenStore,
    "tokenforget": tsto.tokenForget,
    "cleandebris": tsto.cleanDebris,
    "uploadextra": tsto.doUploadExtraLandMessage,
    "astextextra": tsto.doSaveExtraAsText,
    "protocurrency": tsto.doLoadCurrency,
    "cleanpurchases": tsto.cleanPurchases,
}

try:
    if len(sys.argv) == 1:
        # console interface
        while True:
            args = raw_input(tsto.mPrompt).split()
            args_count = len(args)
            if args_count == 0:
                continue
            func = cmds.get(args[0])
            if func is not None:
                func()
            else:
                func = cmdwarg.get(args[0])
                if func is not None:
                    func(args)
            if func is None:
                print(
                    "ERR: unknown command '%s'.\nMaybe you should try 'help'." % (args[0]))
    else:
        # command line interface using argparse module (thanks @oskgeek)
        class CustomAction(argparse.Action):

            def __call__(self, parser, namespace, values, option_string=None):
                if not 'ordered_args' in namespace:
                    setattr(namespace, 'ordered_args', [])
                previous = namespace.ordered_args
                previous.append((self.dest, values))
                setattr(namespace, 'ordered_args', previous)
        parser = argparse.ArgumentParser(
            description=DESCRIPTION, add_help=False)
        for command_name in cmds.keys():
            parser.add_argument("--%s" % command_name,
                                nargs=0, action=CustomAction)
        for command_name in cmdwarg.keys():
            parser.add_argument("--%s" % command_name,
                                nargs='+', action=CustomAction)
        args = parser.parse_args()
        for arguments in args.ordered_args:
            command, values = arguments
            if len(values) == 0:
                cmds.get(command)()
            else:
                values.insert(0, command)
                cmdwarg.get(command)(values)
except Exception as e:
    print(traceback.print_exc())
