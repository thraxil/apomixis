from celery.task import task
from models import Node
from django.conf import settings
from restclient import POST
import simplejson
from datetime import datetime

@task(ignore_results=True)
def bootstrap(myinfo):
    for url in settings.CLUSTER['nodes']:
        ping_node.delay(myinfo,url)

@task(ignore_results=True)
def ping_node(myinfo,url):
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
