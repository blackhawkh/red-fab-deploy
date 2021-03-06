import sys
from fabric.api import run, sudo, execute, env
from fabric.tasks import Task

from fab_deploy import functions
from fab_deploy.ubuntu.setup import *

from api import get_ec2_connection


class LBSetup(Task):
    """
    Set up load balancer

    Create an elastic load balancer, read connections info from server.ini,
    get ip address and look for corresponding ec2 instances, and register
    the instances with load balancer.

    you may define the following optional arguments in env:
    * **lb_name**:  name of load_balancer. If not defined, load balancer will
                    be named after the name of your project directory.
    * **listeners**:  listeners of load balancer, a list of tuple
                      (lb port, instance port, protocol).
                      If not provided, only port 80 will be registered.
    * **hc_policy**:  a dictionary defining the health check policy, keys can be
                      interval, target, healthy_threshold, timeout
                      and unhealthy_threshold

                      default value is
                          hc_policy = {
                            'interval': 30,
                            'target':   'HTTP:80/index.html', }
    """

    name = 'lb_server'
    config_section = 'load-balancer'

    hc_policy = {
                'interval': 30,
                'target':   'HTTP:80/index.html', }

    listeners =  [(80, 80, 'http',)]

    def get_instance_id_by_ip(self, ip, **kwargs):
        """
        get ec2 instance id based on ip address
        """
        instances = []
        conn = get_ec2_connection(server_type='ec2', **kwargs)
        reservations = conn.get_all_instances()
        for resv in reservations:
            for instance in resv.instances:
                if instance.ip_address == ip or instance.public_dns_name == ip:
                    instances.append(instance.id)
        return instances

    def _get_elb(self, conn, lb_name):
        lbs = conn.get_all_load_balancers()
        for lb in lbs:
            if lb.name == lb_name:
                return lb
        return None

    def run(self, section, **kwargs):
        conn = get_ec2_connection(server_type='ec2', **kwargs)
        elb_conn = get_ec2_connection(server_type='elb', **kwargs)

        zones = [ z.name for z in conn.get_all_zones()]

        lb_name = env.get('lb_name')
        if not lb_name:
            lb_name = env.project_name

        listeners = env.get('listeners')
        if not listeners:
            listeners = self.listeners

        connections = env.config_object.get_list(section,
                                                 env.config_object.CONNECTIONS)
        ips = [ ip.split('@')[-1] for ip in connections]
        for ip in ips:
            instances = self.get_instance_id_by_ip(ip, **kwargs)
            if len(instances) == 0:
                print "Cannot find any ec2 instances match your connections"
                sys.exit(1)

        elb = self._get_elb(elb_conn, lb_name)
        print "find load balancer %s" %lb_name
        if not elb:
            elb = elb_conn.create_load_balancer(lb_name, zones, listeners,
                                                security_groups=['lb_sg'])
            print "load balancer %s successfully created" %lb_name

        elb.register_instances(instances)
        print "register instances into load balancer"
        print instances

        hc_policy = env.get('hc_policy')
        if not hc_policy:
            hc_policy = self.hc_policy
        print "Configure load balancer health check policy"
        print hc
        hc = HealthCheck(**hc_policy)
        elb.configure_health_check(hc)


app_server = AppSetup()
dev_server = DevSetup()
db_server = DBSetup()
slave_db = SlaveSetup()
lb_server = LBSetup()
