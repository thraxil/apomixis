from django.db import models
from datetime import datetime, timedelta

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
