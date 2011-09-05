#!ve/bin/python
import os
import uuid
import subprocess
from multiprocessing import Process

NUM_NODES = 10

for n in range(NUM_NODES):
    u = str(uuid.uuid1())
    settings_file = open("settings_%d.py" % n,"w")
    contents = """
from settings_shared import *

DATABASE_NAME = '/var/www/apomixis/apomixis%d.sqlite' 
MEDIA_ROOT = "/var/www/apomixis%d/uploads/"
BROKER_VHOST = "/node%d"
CLUSTER = {
    'name' : 'testcluster', # name of the cluster
    'uuid' : '%s', # my UUID (randomly generated)
    'secret' : 'this is secret stuffs', # shared secret for the cluster
    'location' : 'laptop', # my location
    'nodes' : ['http://localhost:8001/','http://localhost:8002/','http://localhost:8003/','http://localhost:8004/','http://localhost:8005/','http://localhost:8006/','http://localhost:8007/','http://localhost:8008/','http://localhost:8009/','http://localhost:8010/'], # other nodes in the cluster
    'nickname' : 'behemoth%d', # my nickname in the cluster
    'replication' : 3, # how many copies of each image it will try to maintain
    'location_replication' : 1, # how many locations it will try to spread those copies over
    'writeable' : True, # i can handle uploads
    'announce_frequency' : 100, # how often to re-announce self to the cluster (seconds)
    'base_url' : "http://localhost:80%02d/",
    }

""" % (n,n,n,u,n,n)
    settings_file.write(contents)
    settings_file.close()
    try:
        os.system("rm -rf /var/www/apomixis%d/uploads/" % n)
        os.makedirs("/var/www/apomixis%d/uploads/" % n)
    except:
        pass
    try:
        os.unlink("/var/www/apomixis/apomixis%d.sqlite" % n)
    except:
        pass

    try:
        p = subprocess.Popen("./manage.py syncdb --settings=settings_%d" % n, shell=True)
        sts = os.waitpid(p.pid, 0)[1]
    except Exception, e:
        print "syncdb failed"
        print str(e)

    def f(s):
        p = subprocess.Popen("./manage.py runserver --settings=settings_%d localhost:80%02d" % (s,s), shell=True)
        sts = os.waitpid(p.pid, 0)[1]

    def c(s):
        p = subprocess.Popen("./manage.py celeryd --settings=settings_%d" % (s,), shell=True)
        sts = os.waitpid(p.pid, 0)[1]

    def cb(s):
        p = subprocess.Popen("./manage.py celerybeat -S djcelery.schedulers.DatabaseScheduler --settings=settings_%d" % (s,), shell=True)
        sts = os.waitpid(p.pid, 0)[1]

    p = Process(target=f, args=(n,)).start()
    p2 = Process(target=c, args=(n,)).start()
    p3 = Process(target=cb, args=(n,)).start()

"""
a note on rabbitmq setup:

to run this cluster, rabbitmq needs vhosts node0 - node9 created and permissioned properly:

$ sudo rabbitmqctl add_vhost /node0
$ sudo rabbitmqctl set_permissions -p /node0 guest ".*" ".*" ".*"

for each
"""
