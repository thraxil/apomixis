from django.db import models
from datetime import datetime, timedelta
from hashlib import sha1
from restclient import POST
import simplejson
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

    def ping(self,base_url):
        myinfo = settings.CLUSTER
        myinfo['base_url'] = base_url
        try:
            r = POST(self.base_url + "announce/",params=myinfo,async=False)
            n = simplejson.loads(r)
            if n['uuid'] == self.uuid:
                self.last_seen = datetime.now()
                self.nickname = n['nickname']
                self.base_url = n['base_url']
                self.location = n['location']
                self.writeable = n['writeable']
                self.save()
            else:
                # hello new neighbor!
                neighbor = Node.objects.create(uuid=nuuid,
                                               nickname=n['nickname'],
                                               base_url=n['base_url'],
                                               location=n['location'],
                                               writeable=n['writeable'],
                                               )
                # let's clear ourself out though.
                self.delete()
            # does it know any nodes that we don't?
            for node in n['nodes']:
                r = Node.objects.filter(uuid=node['uuid'])
                if r.count() == 0:
                    # they know someone we don't
                    nn = Node.objects.create(uuid=node['uuid'],
                                             nickname=node['nickname'],
                                             base_url=node['base_url'],
                                             location=node['location'],
                                             writeable=node['writeable'],
                                             )
        except Exception, e:
            self.last_failed = datetime.now()
            self.writeable = False
            self.save()

        

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
