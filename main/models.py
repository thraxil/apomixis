from django.db import models
from datetime import datetime, timedelta

def normalize_url(url):
    return url.replace("localhost","127.0.0.1")


class Node(models.Model):
    """ what we know about another node in the cluster """
    nickname = models.CharField(max_length=256)
    uuid = models.CharField(max_length=256)
    base_url = models.CharField(max_length=256)
    location = models.CharField(max_length=256)
    writeable = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    last_failed = models.DateTimeField(blank=True,null=True)

    def as_dict(self):
        # for gossip/announce
        return {'nickname' : self.nickname,
                'uuid' : self.uuid,
                'base_url' : normalize_url(self.base_url),
                'location' : self.location,
                'writeable' : self.writeable,
            }

def current_neighbors():
    """ nodes that we think are alive.
    ie, that we've heard from in the last hour
    and haven't had a failure from more recently than we've heard from them """
    now = datetime.now()
    last_hour = now - timedelta(hours=1)
    all_nodes = Node.objects.filter()
    return [n for n in all_nodes if not n.last_failed or n.last_seen > n.last_failed]
    
def current_writeable_neighbors():    
    """ nodes that we think are alive and are writeable.
    ie, that we've heard from in the last hour
    and haven't had a failure from more recently than we've heard from them """
    now = datetime.now()
    last_hour = now - timedelta(hours=1)
    return [n for n in Node.objects.filter(last_seen__gte=last_hour,writeable=True) if n.last_seen > n.last_failed]

