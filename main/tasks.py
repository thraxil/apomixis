from celery.task import task
from celery.task import Task, PeriodicTask
from models import Node, current_neighbors
import models
from django.conf import settings
from datetime import datetime, timedelta

@task(ignore_results=True)
def bootstrap():
    for url in settings.CLUSTER['nodes']:
        ping_url.delay(url)

@task(ignore_results=True)
def ping_url(url):
    models.ping_url(url)

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
    node.ping()

class GossipTask(PeriodicTask):
    run_every = timedelta(seconds=int(settings.CLUSTER['announce_frequency']))
    def run(self,**kwargs):
        for n in Node.objects.all():
            ping_node.delay(n.id)
        return True


class BootstrapTask(PeriodicTask):
    """ once an hour, re-run bootstrap"""
    run_every = timedelta(seconds=60 * 60)

    def run(self,**kwargs):
        print "BootStrapTask"
        bootstrap.delay()
        return True

