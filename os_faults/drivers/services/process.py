# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from os_faults.ansible import executor
from os_faults.api import error
from os_faults.api import service
from os_faults.drivers import shared_schemas
from os_faults import utils


LOG = logging.getLogger(__name__)


class ServiceAsProcess(service.Service):
    """Service as process

    "process" is a basic service driver that uses `ps` and `kill` in
    actions like kill / freeze / unfreeze. Commands for start / restart
    / terminate should be specified in configuration, otherwise
    the commands will fail at runtime.

    **Example configuration:**

    .. code-block:: yaml

        services:
          app:
            driver: process
            args:
              grep: my_app
              restart_cmd: /bin/my_app --restart
              terminate_cmd: /bin/stop_my_app
              start_cmd: /bin/my_app
              port: ['tcp', 4242, 'ingress']

    parameters:

    - **grep** - regexp for grep to find process PID
    - **restart_cmd** - command to restart service (optional)
    - **terminate_cmd** - command to terminate service (optional)
    - **start_cmd** - command to start service (optional)
    - **port** - tuple with two or three values - protocol, port number,
      direction (optional)

    Note that network operations are based on iptables. They are applied
    to the whole host and not restricted to a single process.
    """

    NAME = 'process'
    DESCRIPTION = 'Service as process'
    CONFIG_SCHEMA = {
        'type': 'object',
        'properties': {
            'grep': {'type': 'string'},
            'start_cmd': {'type': 'string'},
            'terminate_cmd': {'type': 'string'},
            'restart_cmd': {'type': 'string'},
            'port': shared_schemas.PORT_SCHEMA,
        },
        'required': ['grep'],
        'additionalProperties': False,
    }

    def __init__(self, *args, **kwargs):
        super(ServiceAsProcess, self).__init__(*args, **kwargs)
        self.grep = self.config['grep']
        self.start_cmd = self.config.get('start_cmd')
        self.terminate_cmd = self.config.get('terminate_cmd')
        self.restart_cmd = self.config.get('restart_cmd')
        self.port = self.config.get('port')

    def _run_task(self, nodes, task, message):
        nodes = nodes if nodes is not None else self.get_nodes()
        if len(nodes) == 0:
            raise error.ServiceError(
                'Service %s is not found on any nodes' % self.service_name)

        LOG.info('%s service %s on nodes: %s',
                 message, self.service_name, nodes.get_ips())

        return self.cloud_management.execute_on_cloud(nodes.hosts, task)

    def discover_nodes(self):
        nodes = self.cloud_management.get_nodes()
        cmd = 'bash -c "ps ax | grep -v grep | grep \'{}\'"'.format(self.grep)
        results = self.cloud_management.execute_on_cloud(
            nodes.hosts, {'command': cmd}, False)
        success_ips = [r.host for r in results
                       if r.status == executor.STATUS_OK]
        hosts = [h for h in nodes.hosts if h.ip in success_ips]
        LOG.debug('Service %s is discovered on nodes %s',
                  self.service_name, hosts)
        return self.node_cls(cloud_management=self.cloud_management,
                             hosts=hosts)

    @utils.require_variables('restart_cmd')
    def restart(self, nodes=None):
        self._run_task(nodes, {'shell': self.restart_cmd}, 'Restart')

    @utils.require_variables('terminate_cmd')
    def terminate(self, nodes=None):
        self._run_task(nodes, {'shell': self.terminate_cmd}, 'Terminate')

    @utils.require_variables('start_cmd')
    def start(self, nodes=None):
        self._run_task(nodes, {'shell': self.start_cmd}, 'Start')

    def kill(self, nodes=None):
        task = {
            'kill': {
                'grep': self.grep, 'sig': 'SIGKILL'
            },
            'become': 'yes',
        }
        self._run_task(nodes, task, 'Kill')

    def freeze(self, nodes=None, sec=None):
        if sec:
            task = {
                'freeze': {
                    'grep': self.grep, 'sec': sec
                },
                'become': 'yes',
            }
        else:
            task = {
                'kill': {
                    'grep': self.grep, 'sig': 'SIGSTOP'
                },
                'become': 'yes',
            }
        message = "Freeze %s" % (('for %s sec ' % sec) if sec else '')
        self._run_task(nodes, task, message)

    def unfreeze(self, nodes=None):
        task = {
            'kill': {
                'grep': self.grep, 'sig': 'SIGCONT'
            },
            'become': 'yes',
        }
        self._run_task(nodes, task, 'Unfreeze')

    def plug(self, nodes=None, direction=None, other_port=None):
        nodes = nodes if nodes is not None else self.get_nodes()

        if other_port:
            port = other_port
        else:
            # work with local service port
            if not self.port:
                msg = '{} required for {}.{}'.format(
                    'port', self.__class__.__name__, 'plug')
                raise NotImplementedError(msg)

            port = self.port
            direction = self.port[2] if len(self.port) > 2 else 'ingress'

        protocol = port[0]
        port_number = port[1]

        message = "Open %s traffic to %s port %d" % (
            direction, protocol, port_number)

        task = {
            'iptables': {
                'chain': 'INPUT' if direction == 'ingress' else 'OUTPUT',
                'protocol': protocol,
                'jump': 'DROP',
                'destination_port': '%d' % port_number,
                'state': 'absent',
                'comment': 'Added by os-faults',
            },
            'become': 'yes',
        }
        self._run_task(nodes, task, message)

    def unplug(self, nodes=None, direction=None, other_port=None):
        nodes = nodes if nodes is not None else self.get_nodes()

        if other_port:
            port = other_port
        else:
            # work with local service port
            if not self.port:
                msg = '{} required for {}.{}'.format(
                    'port', self.__class__.__name__, 'plug')
                raise NotImplementedError(msg)

            port = self.port
            direction = self.port[2] if len(self.port) > 2 else 'ingress'

        protocol = port[0]
        port_number = port[1]

        message = "Block %s traffic to %s port %d" % (
            direction, protocol, port_number)

        task = {
            'iptables': {
                'chain': 'INPUT' if direction == 'ingress' else 'OUTPUT',
                'protocol': protocol,
                'jump': 'DROP',
                'destination_port': '%d' % port_number,
                'action': 'insert',
                'state': 'present',
                'comment': 'Added by os-faults',
            },
            'become': 'yes',
        }
        self._run_task(nodes, task, message)
