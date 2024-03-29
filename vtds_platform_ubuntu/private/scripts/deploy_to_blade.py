#! python
#
# MIT License
#
# (C) Copyright [2024] Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# pylint: disable='consider-using-f-string'
"""Internal script intended to be run on a Virtual Blade by the Ubuntu
flavor of the vTDS Platform Layer. This installs packages and creates
Virtual Networks based on a configuration file provided as the only
argument on the command line.

"""
import sys
from subprocess import (
    Popen,
    TimeoutExpired,
    PIPE
)
from tempfile import (
    TemporaryFile,
    NamedTemporaryFile,
)
import json
import yaml


class ContextualError(Exception):
    """Exception to report failures seen and contextualized within the
    application.

    """


class UsageError(Exception):  # pylint: disable=too-few-public-methods
    """Exception to report usage errors

    """


def write_out(string):
    """Write an arbitrary string on stdout and make sure it is
    flushed.

    """
    sys.stdout.write(string)
    sys.stdout.flush()


def write_err(string):
    """Write an arbitrary string on stderr and make sure it is
    flushed.

    """
    sys.stderr.write(string)
    sys.stderr.flush()


def usage(usage_msg, err=None):
    """Print a usage message and exit with an error status.

    """
    if err:
        write_err("ERROR: %s\n" % err)
    write_err("%s\n" % usage_msg)
    sys.exit(1)


def error_msg(msg):
    """Format an error message and print it to stderr.

    """
    write_err("ERROR: %s\n" % msg)


def warning_msg(msg):
    """Format a warning and print it to stderr.

    """
    write_err("WARNING: %s\n" % msg)


def info_msg(msg):
    """Format an informational message and print it to stderr.

    """
    write_err("INFO: %s\n" % msg)


def run_cmd(cmd, args, stdin=sys.stdin, timeout=None):
    """Run a command with output on stdout and errors on stderr

    """
    exitval = 0
    try:
        with Popen(
                [cmd, *args],
                stdin=stdin, stdout=sys.stdout, stderr=sys.stderr
        ) as command:
            time = 0
            signaled = False
            while True:
                try:
                    exitval = command.wait(timeout=5)
                except TimeoutExpired:
                    time += 5
                    if timeout and time > timeout:
                        if not signaled:
                            # First try to terminate the process
                            command.terminate()
                            continue
                        command.kill()
                        print()
                        # pylint: disable=raise-missing-from
                        raise ContextualError(
                            "'%s' timed out and did not terminate "
                            "as expected after %d seconds" % (
                                " ".join([cmd, *args]),
                                time
                            )
                        )
                    continue
                # Didn't time out, so the wait is done.
                break
            print()
    except OSError as err:
        raise ContextualError(
            "executing '%s' failed - %s" % (
                " ".join([cmd, *args]),
                str(err)
            )
        ) from err
    if exitval != 0:
        fmt = (
            "command '%s' failed" if not signaled
            else "command '%s' timed out and was killed"
        )
        raise ContextualError(fmt % " ".join([cmd, *args]))


def read_config(config_file):
    """Read in the specified YAML configuration file for this blade
    and return the parsed data.

    """
    try:
        with open(config_file, 'r', encoding='UTF-8') as config:
            return yaml.safe_load(config)
    except OSError as err:
        raise ContextualError(
            "failed to load blade configuration file '%s' - %s" % (
                config_file,
                str(err)
            )
        ) from err


def prepare_package_installer():
    """Make sure that 'apt' is set up properly for installing packages
    and up to date.

    """
    run_cmd("apt", ["update"])
    run_cmd("apt", ["upgrade", "-y"])


def preconfigure_packages(settings):
    """Set up pre-configuration settings for the packages to be
    installed so that non-interactive installation works correctly.

    """
    if not settings:
        # No settings to preconfigure, done
        return

    # I know there is a way to turn the list of settings into a stream
    # and give it to 'run_cmd' as stdin, but the code for that is more
    # complex and I don't really need it, so I will use a temporary
    # file instead.
    data = [setting + "\n" for setting in settings]
    with TemporaryFile(mode='w+', encoding='UTF-8') as stdin:
        stdin.writelines(data)
        stdin.seek(0)
        run_cmd("debconf-set-selections", [], stdin)


def install_packages(packages):
    """Install the list of packages provided in the 'packages'
    argument using 'apt install'.

    """
    run_cmd("apt", ["install", "-y", *packages])


def disable_services(service_names):
    """Disable a list of services on a blade

    """
    for service_name in service_names:
        run_cmd("systemctl", ["disable", "--now", service_name])


def enable_services(service_names):
    """Enable and start a list of services on a blade

    """
    for service_name in service_names:
        run_cmd("systemctl", ["enable", "--now", service_name])


def list_from_packages(packages, blade_class, key):
    """Extract a flat list of elements grouped under 'key' from all of
    the package configurations found in 'packages'. This ensures that only

    """
    return [
        item
        for _, pack in packages.items()
        if pack.get('blade_classes', None) is None
        or blade_class in pack['blade_classes']
        for item in pack.get(key, [])
    ]


def setup_packages(packages, blade_class):
    """Given a dictionary full of package configurations for the
    blade, set them up on the blade as described.

    """
    # The weird list(set(...)) thing here is an easy way to make sure
    # the repositories are unique within the final list.
    prepare_package_installer()
    preconfigure_packages(
        list_from_packages(
            packages, blade_class, 'preconfig_settings'
        )
    )
    install_packages(
        list_from_packages(packages, blade_class, 'packages')
    )
    disable_services(
        list_from_packages(
            packages, blade_class, 'services_disable'
        )
    )
    enable_services(
        list_from_packages(
            packages, blade_class, 'services_enable'
        )
    )


class NetworkInstaller:
    """A class to handle declarative creation of virtual networks on a
    blade.

    """
    @staticmethod
    def _get_interfaces():
        """Retrieve information about existing interfaces structured for
        easy inspection to determine what is already in place.

        """
        with Popen(
                ["ip", "-d", "--json", "addr"],
                stdout=PIPE,
                stderr=PIPE
        ) as cmd:
            if_data = json.loads(cmd.stdout.read())
        with Popen(
                ["bridge", "--json", "fdb"],
                stdout=PIPE,
                stderr=PIPE
        ) as cmd:
            fdb_data = json.loads(cmd.stdout.read())
        interfaces = {iface['ifname']: iface for iface in if_data}
        dsts = [fdb_entry for fdb_entry in fdb_data if 'dst' in fdb_entry]
        for dst in dsts:
            if 'dst' in dst:
                iface = interfaces[dst['ifname']]
                iface['fdb_dsts'] = (
                    [dst['dst']] if 'fdb_dsts' not in iface else
                    iface['fdb_dsts'] + [dst['dst']]
                )
        return interfaces

    @staticmethod
    def _get_virtual_networks():
        """Retrieve information about existing interfaces structured for
        easy inspection to determine what is already in place.

        """
        with Popen(
                ["virsh", "net-list", "--name"],
                stdout=PIPE,
                stderr=PIPE
        ) as cmd:
            vnets = [
                line[:-1].decode('UTF-8') for line in cmd.stdout.readlines()
                if line[:-1].decode('UTF-8')
            ]
        return vnets

    def __init__(self):
        """Constructor

        """
        self.interfaces = self._get_interfaces()
        self.vxlans = {
            key: val for key, val in self.interfaces.items()
            if 'linkinfo' in val and val['linkinfo']['info_kind'] == 'vxlan'
        }
        self.bridges = {
            key: val for key, val in self.interfaces.items()
            if 'linkinfo' in val and val['linkinfo']['info_kind'] == 'bridge'
        }
        self.vnets = self._get_virtual_networks()

    def _check_conflict(self, name, bridge_name):
        """Look for conflicting existing interfaces for the named
        tunnel and bridge and error if they are found.

        """
        if name in self.interfaces and name not in self.vxlans:
            raise ContextualError(
                "attempting to create virtual network '%s' but conflicting "
                "non-virtual network interface already exists on blade" % name
            )
        if bridge_name in self.interfaces and bridge_name not in self.bridges:
            raise ContextualError(
                "attempting to create bridge for virtual network '%s' [%s] "
                "but conflicting non-bridge network interface already "
                "exists on blade" % (name, bridge_name)
            )

    def _find_underlay(self, endpoint_ips):
        """All virtual networks have a tunnel endpoint on the blades
        where they are used, so they all have a network device used as
        the point of access to the underlay network which determines
        that tunnel endpoint. This function finds the device and
        endpoint IP on the current blade that will be used to connect
        to the virtual network.

        """
        for intf, if_desc in self.interfaces.items():
            addr_info = if_desc.get('addr_info', [])
            for info in addr_info:
                if 'local' in info and info['local'] in endpoint_ips:
                    return (intf, info['local'])
        raise ContextualError(
            "no network device was found with an IP address matching any of "
            "the following endpoint IPs: %s" % (str(endpoint_ips))
        )

    @staticmethod
    def remove_link(if_name):
        """Remove an interface (link) specified by the interface name.

        """
        run_cmd("ip", ["link", "del", if_name])

    @staticmethod
    def add_new_tunnel(tunnel_name, bridge_name, vxlan_id, device):
        """Set up a VxLAN tunnel ingress using the supplied VxLAN ID,
        and set up the bridge interface mastering the tunnel onto
        which IPs and VMs can be bound.

        """
        # Make the Tunnel Endpoint
        run_cmd(
            "ip",
            [
                "link", "add", tunnel_name,
                "type", "vxlan",
                "id", vxlan_id,
                "dev", device,
                "dstport", "0",
            ]
        )
        # Make the bridge device
        run_cmd(
            "ip",
            ["link", "add", bridge_name, "type", "bridge"]
        )
        # Master the tunnel under the bridge
        run_cmd(
            "ip",
            ["link", "set", tunnel_name, "master", bridge_name]
        )

    @staticmethod
    def connect_endpoints(tunnel_name, endpoint_ips, local_ip_addr):
        """Create the static mesh interconnect between tunnel
        endpoints (blades) for the named network.

        """
        remote_ips = [
            ip_addr for ip_addr in endpoint_ips
            if ip_addr != local_ip_addr
        ]
        for ip_addr in remote_ips:
            run_cmd(
                "bridge",
                [
                    "fdb", "append", "to", "00:00:00:00:00:00",
                    "dst", ip_addr,
                    "dev", tunnel_name,
                ],
            )

    def add_virtual_network(self, network_name, bridge_name):
        """Add a network to libvirt that is bound onto the bridge that
        is mastering the tunnel for that network.

        """
        net_desc = """
<network>
  <name>%s</name>
  <forward mode="bridge" />
  <bridge name="%s" />
</network>
        """ % (network_name, bridge_name)

        with NamedTemporaryFile(mode='w+', encoding='UTF-8') as tmpfile:
            tmpfile.write(net_desc)
            tmpfile.flush()
            run_cmd("virsh", ["net-define", tmpfile.name])
        run_cmd("virsh", ["net-start", network_name])
        run_cmd("virsh", ["net-autostart", network_name])
        self.vnets.append(network_name)

    def remove_virtual_network(self, network_name):
        """Remove a network from libvirt

        """
        if network_name not in self.vnets:
            # Don't remove it if it isn't there
            return
        run_cmd("virsh", ["net-destroy", network_name])
        run_cmd("virsh", ["net-undefine", network_name])
        self.vnets.remove(network_name)

    def construct_virtual_network(self, config):
        """Create a VxLAN tunnel and bridge for a virtual network,
        populate its layer2 mesh (among the blades where it can be
        seen) and add it to the libvirt list of networks on the blade.

        """
        network_name = config.get('network_name', "")
        tunnel_name = config.get('tunnel_name', network_name)
        bridge_name = config.get('bridge_name', "br-%s" % tunnel_name)
        vxlan_id = str(config.get('tunnel_id', "0"))
        endpoint_ips = config.get('endpoint_ips', [])
        self._check_conflict(tunnel_name, bridge_name)
        if tunnel_name in self.interfaces:
            self.remove_link(tunnel_name)
        if bridge_name in self.interfaces:
            self.remove_link(bridge_name)
        device, local_ip_addr = self._find_underlay(endpoint_ips)
        self.add_new_tunnel(tunnel_name, bridge_name, vxlan_id, device)
        self.connect_endpoints(tunnel_name, endpoint_ips, local_ip_addr)
        self.remove_virtual_network(network_name)
        self.add_virtual_network(network_name, bridge_name)


def main(argv):
    """Main function...

    """
    if not argv:
        raise UsageError("too few arguments")
    config = read_config(argv[0])
    networks = config.get('networks', {})
    packages = config.get('packages', {})
    blade_class = config.get('blade_class', None)
    setup_packages(packages, blade_class)
    network_installer = NetworkInstaller()
    network_installer.remove_virtual_network("default")
    for _, network in networks.items():
        network_installer.construct_virtual_network(network)


def entrypoint(usage_msg, main_func):
    """Generic entrypoint function. This sets up command line
    arguments for the invocation of a 'main' function and takes care
    of handling any vTDS exceptions that are raised to report
    errors. Other exceptions are allowed to pass to the caller for
    handling.

    """
    try:
        main_func(sys.argv[1:])
    except ContextualError as err:
        error_msg(str(err))
        sys.exit(1)
    except UsageError as err:
        usage(usage_msg, str(err))


if __name__ == '__main__':
    USAGE_MSG = """
<<<<<<< HEAD
usage: deploy_to_blade blade_type config_path

Where:

    blade_class is the name of the Virtual Blade class to which this
                Virtual Blade belongs.
=======
usage: prepare_blade config_path

Where:

>>>>>>> add blade deploy script
    config_path is the path to a YAML file containing the blade
                configuration to apply.
"""[1:-1]
    entrypoint(USAGE_MSG, main)
