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
    'announce_frequency' : 300, # how often to re-announce self to the cluster (seconds)
    }
""" % (n,n,u,n)
    settings_file.write(contents)
    settings_file.close()
    try:
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

    p = Process(target=f, args=(n,)).start()

