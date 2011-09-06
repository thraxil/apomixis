from celery.task import task
from celery.task import Task, PeriodicTask
from models import Node, current_neighbors
from django.conf import settings
from restclient import POST
import simplejson
from datetime import datetime, timedelta

@task(ignore_results=True)
def bootstrap(myinfo):
    for url in settings.CLUSTER['nodes']:
        ping_url.delay(myinfo,url)

@task(ignore_results=True)
def ping_url(myinfo,url):
    try:
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
        print str(e)
        pass

@task(ignore_results=True)
def ping_node(node_id):
    node = Node.objects.get(id=node_id)
    myinfo = settings.CLUSTER
    print "ping_node(%d) (by %s)" % (node_id,myinfo['nickname'])
    if node.uuid == myinfo['uuid']:
        # don't ping ourself, just update the db entry
        node.last_seen = datetime.now()
        node.save()
        return
    # if we've heard from them more recently than the announce_frequency,
    # no reason to re-ping
    f = timedelta(seconds=int(settings.CLUSTER["announce_frequency"]))
    if node.last_seen is not None:
        now = datetime.now()
        delt = now - node.last_seen
        if delt < f:
            return
    try:
        myinfo['nodes'] = [n.as_dict() for n in current_neighbors()]
        r = POST(node.base_url + "announce/",params=dict(json=simplejson.dumps(myinfo)),async=False)
        n = simplejson.loads(r)
        if n['uuid'] == node.uuid:
            node.last_seen = datetime.now()
            node.nickname = n['nickname']
            node.base_url = n['base_url']
            node.location = n['location']
            node.writeable = n['writeable']
            node.save()
        else:
            # hello new neighbor!
            neighbor = Node.objects.create(uuid=n['uuid'],
                                           nickname=n['nickname'],
                                           base_url=n['base_url'],
                                           location=n['location'],
                                           writeable=n['writeable'],
                                           )
        # does it know any nodes that we don't?
        for nnode in n['nodes']:
            r = Node.objects.filter(uuid=nnode['uuid'])
            if r.count() == 0:
                # they know someone we don't
                nn = Node.objects.create(uuid=nnode['uuid'],
                                         nickname=nnode['nickname'],
                                         base_url=nnode['base_url'],
                                         location=nnode['location'],
                                         writeable=nnode['writeable'],
                                         )
        return True
    except Exception, e:
        node.last_failed = datetime.now()
        node.writeable = False
        node.save()
        return False

class GossipTask(PeriodicTask):
#    run_every = timedelta(seconds=int(settings.CLUSTER['announce_frequency']))
    run_every = timedelta(seconds=30)

    def run(self,**kwargs):
        for n in Node.objects.all():
            ping_node.delay(n.id)
        return True

