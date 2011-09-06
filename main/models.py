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
        print "stashing to %s" % self.nickname
        try:
            register_openers()
            datagen, headers = multipart_encode({"image": image_file,
                                                 "hash" : ahash,
                                                 "extension" : extension})
            request = urllib2.Request(self.base_url + "stash/",datagen, headers)
            r = urllib2.urlopen(request).read()
            return True
        except Exception, e:
            print str(e)
            return False

        

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
