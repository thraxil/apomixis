from django.core.management.base import BaseCommand
from main.models import *
from django.conf import settings
from simplejson import loads
from restclient import GET,POST

def normalize_url(url):
    return url.replace("localhost","127.0.0.1")

class Command(BaseCommand):
    args = ''
    help = ''
    
    def handle(self, *args, **options):
        print "gossiping"
        # check if the bootstrap nodes from config are already
        # in our database. add them if not.
        for node in settings.CLUSTER['nodes']:
            r = Node.objects.filter(base_url=node)
            if r.count() == 0:
                # let's add a Node
                print "adding bootstrap node"
                n = loads(GET(node + "announce/"))
                print "got data from it"
                newnode = Node.objects.create(
                    nickname = n['nickname'],
                    uuid = n['uuid'],
                    base_url = normalize_url(n['base_url']),
                    location = n['location'],
                    writeable = n['writeable'],
                    )

        # compile a list of all the base_urls we know about
        base_urls = [normalize_url(n.base_url) for n in Node.objects.all()]
        base_urls.append(normalize_url(settings.CLUSTER['base_url']))

        # go through the nodes we know about and announce
        # ourself and update our info on them
        data = {
            'nickname' : settings.CLUSTER['nickname'], 
            'uuid' : settings.CLUSTER['uuid'], 
            'location' : settings.CLUSTER['location'],
            'nodes' : [n.as_dict() for n in current_neighbors()], 
            # TODO: determine based on storage caps
            'writeable' : settings.CLUSTER['writeable'], 
            # since we're running as a command, we have to rely
            # on the config to know this
            'base_url' : normalize_url(settings.CLUSTER['base_url']),
            }

        for node in Node.objects.all():
            n = loads(POST(normalize_url(node.base_url) + "announce/",
                           params=data,
                           async=False))
            # make sure it's the node we expected at that base_url
            assert node.uuid == n['uuid']
            node.nickname = n['nickname']
            node.location = n['location']
            node.writeable = n['writeable']
            for neighbor in n['nodes']:
                if normalize_url(neighbor['base_url']) not in base_urls:
                    # they know someone we don't
                    # let's go make friends!
                    print str(neighbor)
                    new_data = loads(POST(normalize_url(neighbor['base_url']) + "announce/",
                                          params=data,
                                          async=False))
                    new_neighbor = Node.objects.create(
                        nickname = new_data['nickname'],
                        uuid = new_data['uuid'],
                        location = new_data['location'],
                        base_url = normalize_url(new_data['base_url']),
                        writeable = new_data['writeable'],
                        )
