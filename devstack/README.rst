==============================
Enabling OS-Faults in DevStack
==============================

To configure DevStack and enable OS-Faults edit ``${DEVSTACK_DIR}/local.conf``
file and add the following to ``[[local|localrc]]`` section::

      enable_plugin os-faults https://opendev.org/performa/os-faults master


Run DevStack as normal::

    $ ./stack.sh

