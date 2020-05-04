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

import unittest

import mock

from os_faults.api.node_collection import Host
from os_faults.api.node_collection import NodeCollection
from os_faults.drivers.services.process import ServiceAsProcess


class TestServiceAsProcess(unittest.TestCase):

    def setUp(self):
        super(TestServiceAsProcess, self).setUp()

        config = {
            'grep': 'test-service',
            'port': ['tcp', 8000],
        }
        self.cloud_management = mock.Mock()
        self.hosts = [Host('10.1.1.10')]
        self.service = ServiceAsProcess(
            'test-service', config, mock.Mock(), self.cloud_management)
        node_collection = NodeCollection(
            cloud_management=self.cloud_management, hosts=self.hosts)
        self.service.get_nodes = mock.Mock(return_value=node_collection)

    def test_unplug(self):
        # run the command
        self.service.unplug()

        # verify
        expected_task = {
            'iptables': {
                'chain': 'INPUT',
                'protocol': 'tcp',
                'jump': 'DROP',
                'destination_port': '8000',
                'action': 'insert',
                'state': 'present',
                'comment': 'Added by os-faults',
            },
            'become': 'yes',
        }
        self.cloud_management.execute_on_cloud.assert_called_once_with(
            self.hosts, expected_task)

    def test_unplug_with_other_port(self):
        # run the command
        self.service.unplug(direction='egress', other_port=['udp', 10000])

        # verify
        expected_task = {
            'iptables': {
                'chain': 'OUTPUT',
                'protocol': 'udp',
                'jump': 'DROP',
                'destination_port': '10000',
                'action': 'insert',
                'state': 'present',
                'comment': 'Added by os-faults',
            },
            'become': 'yes',
        }
        self.cloud_management.execute_on_cloud.assert_called_once_with(
            self.hosts, expected_task)

    def test_plug(self):
        # run the command
        self.service.plug()

        # verify
        expected_task = {
            'iptables': {
                'chain': 'INPUT',
                'protocol': 'tcp',
                'jump': 'DROP',
                'destination_port': '8000',
                'state': 'absent',
                'comment': 'Added by os-faults',
            },
            'become': 'yes',
        }
        self.cloud_management.execute_on_cloud.assert_called_once_with(
            self.hosts, expected_task)

    def test_plug_port_is_required_in_config(self):
        config = {
            'grep': 'test-service',
        }
        service = ServiceAsProcess(
            'test-service', config, mock.Mock(), mock.Mock())
        node_collection = NodeCollection(
            cloud_management=self.cloud_management, hosts=[])
        service.get_nodes = mock.Mock(return_value=node_collection)

        self.assertRaises(NotImplementedError, service.plug)

    def test_unplug_port_is_required_in_config(self):
        config = {
            'grep': 'test-service',
        }
        service = ServiceAsProcess(
            'test-service', config, mock.Mock(), mock.Mock())
        node_collection = NodeCollection(
            cloud_management=self.cloud_management, hosts=[])
        service.get_nodes = mock.Mock(return_value=node_collection)

        self.assertRaises(NotImplementedError, service.unplug)
