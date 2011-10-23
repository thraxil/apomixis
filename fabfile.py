from fabric.api import run, sudo,local,cd,env

env.hosts = ['thraxil.org','behemoth.ccnmtl.columbia.edu','worker.thraxil.org']

def restart_celery():
    sudo("cd /etc/supervisor/; supervisorctl restart apomixiscelery")

def restart_celerybeat():
    sudo("cd /etc/supervisor/; supervisorctl restart apomixiscelerybeat")

def prepare_deploy():
    local("./manage.py test")

def deploy():
    code_dir = "/var/www/apomixis/apomixis"
    with cd(code_dir):
        run("git pull origin master")
        run("./bootstrap.py")
        run("touch apache/django.wsgi")
    restart_celery()
    restart_celerybeat()
