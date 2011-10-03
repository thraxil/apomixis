from django.db import models
from datetime import datetime, timedelta
from hashlib import sha1
from restclient import POST
import simplejson
import urllib2
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers
from collections import deque
from django.conf import settings

class Node(models.Model):
    """ what we know about another node in the cluster """
    nickname = models.CharField(max_length=256)
    uuid = models.CharField(max_length=256)
    base_url = models.CharField(max_length=256)
    location = models.CharField(max_length=256)
    writeable = models.BooleanField(default=True)
    last_seen = models.DateTimeField(blank=True,null=True)
    last_failed = models.DateTimeField(blank=True,null=True)

    def __unicode__(self):
        return self.nickname
    
    def as_dict(self):
        # for gossip/announce
        return {'nickname' : self.nickname,
                'uuid' : self.uuid,
                'base_url' : normalize_url(self.base_url),
                'location' : self.location,
                'writeable' : self.writeable,
            }

    def is_current(self):
        """ ie, has this node been seen successfully more recently than unsuccessfully"""
        if self.last_failed and self.last_seen:
            return self.last_seen > self.last_failed
        return True

    def hash_keys(self,n=128):
        return hash_keys(self.uuid,n)

    def stash(self,ahash,extension,image_file):
        try:
            register_openers()
            datagen, headers = multipart_encode({"image": image_file,
                                                 "hash" : ahash,
                                                 "extension" : extension})
            request = urllib2.Request(self.base_url + "stash/",datagen, headers)
            r = urllib2.urlopen(request).read()
            return True
        except Exception, e:
            return False

    def fail(self):
        self.last_failed = datetime.now()
        self.writeable = False
        self.save()

    def update_from_dict(self,n):
        self.last_seen = datetime.now()
        self.nickname = n['nickname']
        self.base_url = n['base_url']
        self.location = n['location']
        self.writeable = n['writeable']
        self.save()

    def ping(self):
        """ ping this node. """
        myinfo = settings.CLUSTER
        if myinfo['uuid'] == self.uuid:
            # don't try to ping myself
            return
        try:
            myinfo['nodes'] = [n.as_dict() for n in current_neighbors()]
            r = POST(self.base_url + "announce/",params=dict(json=simplejson.dumps(myinfo)),async=False)
            n = simplejson.loads(r)
            if n['uuid'] == self.uuid:
                self.update_from_dict(n)
            else:
                # hello new neighbor!
                neighbor = Node.objects.create(uuid=n['uuid'],
                                               nickname=n['nickname'],
                                               base_url=n['base_url'],
                                               location=n['location'],
                                               writeable=n['writeable'],
                                               )
                # schedule for pinging
                tasks.ping_node.delay(neighbor.id)
            # does it know any nodes that we don't?
            check_for_new_neighbors(n['nodes'])
        except Exception, e:
            self.fail()

def ping_url(url):
    try:
        myinfo = settings.CLUSTER
        r = POST(url + "announce/",params=myinfo,async=False)
        n = simplejson.loads(r)
        nuuid = n['uuid']
        r = Node.objects.filter(uuid=nuuid)
        if r.count():
            # we've met this neighbor before. just update.
            neighbor = r[0]
            neighbor.last_seen = datetime.now()
            neighbor.writeable = n['writeable']
            neighbor.save()
        else:
            # hello new neighbor!
            neighbor = Node.objects.create(uuid=nuuid,
                                           nickname=n['nickname'],
                                           base_url=n['base_url'],
                                           location=n['location'],
                                           writeable=n['writeable'],
                                           last_seen=datetime.now(),
                                           )
    except Exception, e:
        pass


def check_for_new_neighbors(nodes):
    """ given a list of nodes (dicts), see if any are new ones
    and add them """
    for nnode in nodes:
        r = Node.objects.filter(uuid=nnode['uuid'])
        if r.count() == 0:
            # they know someone we don't
            nn = Node.objects.create(uuid=nnode['uuid'],
                                     nickname=nnode['nickname'],
                                     base_url=nnode['base_url'],
                                     location=nnode['location'],
                                     writeable=nnode['writeable'],
                                     )


def get_self_node():
    uuid = settings.CLUSTER['uuid']
    r = Node.objects.get(uuid=uuid)
    if r.count() == 1:
        return r[0]
    if r.count() == 0:
        # create a self node
        myinfo = settings.CLUSTER
        return Node.objects.create(
            nickname = myinfo['nickname'],
            uuid = myinfo['uuid'],
            base_url = myinfo['base_url'],
            writeable = myinfo['writeable'],
            location = myinfo['location'],
            )
    # TODO: raise an exception here instead
    print "more than one node with my UUID. this should never happen"

def hash_keys(uuid,n=128):
    keys = []
    for i in range(n):
        keys.append(long(sha1("%s%d" % (uuid,i)).hexdigest(), 16))
    return keys

def ring():
    r = []
    for n in current_neighbors():
        for k in n.hash_keys():
            r.append((k,n))
    r.sort(key=lambda x: x[0])
    return r

def write_ring():
    r = []
    for n in current_writeable_neighbors():
        for k in n.hash_keys():
            r.append((k,n))
    r.sort(key=lambda x: x[0])
    return r

def write_order(image_hash):
    wr = deque(write_ring())
    nodes = []
    appending = False
    seen = dict()
    while len(wr) > 0:
        # get the first element
        (k,n) = wr.popleft()
        if appending or image_hash > k:
            if n.uuid not in seen:
                nodes.append(n)
                seen[n.uuid] = True
            appending = True
        else:
            # put it back on
            wr.append((k,n))
    return nodes

def read_order(image_hash):
    r = deque(ring())
    nodes = []
    appending = False
    seen = dict()
    while len(r) > 0:
        # get the first element
        (k,n) = r.popleft()
        if appending or image_hash > k:
            if n.uuid not in seen:
                nodes.append(n)
                seen[n.uuid] = True
            appending = True
        else:
            # put it back on
            r.append((k,n))
    return nodes


def current_neighbors():
    """ nodes that we think are alive.
    ie, that haven't had a failure from more recently than we've heard from them """
    all_nodes = Node.objects.filter()
    return [n for n in all_nodes if n.is_current()]
    
def current_writeable_neighbors():    
    """ nodes that we think are alive and are writeable.
    ie, that haven't had a failure from more recently than 
    we've heard from them """
    all_nodes = Node.objects.filter(writeable=True)
    return [n for n in all_nodes if n.is_current()]

def normalize_url(url):
    return url.replace("localhost","127.0.0.1")
