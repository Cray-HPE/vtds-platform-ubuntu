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
"""Private layer implementation module for the ubuntu platform.

"""

from os.path import join as path_join
from yaml import safe_dump

from vtds_base import (
    ContextualError,
    run,
    log_paths,
    info_msg
)

from . import (
    DEPLOY_SCRIPT_PATH,
    DEPLOY_SCRIPT_NAME
)


class PrivatePlatform:
    """PrivatePlatform class, implements the ubuntu platform layer
    accessed through the python Platform API.

    """
    def __init__(self, stack, config, build_dir):
        """Constructor, stash the root of the platfform tree and the
        digested and finalized platform configuration provided by the
        caller that will drive all activities at all layers.

        """
        self.config = config
        self.stack = stack
        self.provider_api = None
        self.build_dir = build_dir
        self.blade_config_path = path_join(
            self.build_dir, 'blade_config.yaml'
        )
        self.prepared = False

    def __add_endpoint_ips(self, network):
        """Go through the list of connected blade classes for a
        network and use the list of endpoint IPs represented by all of
        the blades in each of those classes to compose a comprehensive
        list of endpoint IPs for the overlay network we are going to
        build for the network. Add that list under the 'endpoint_ips'
        key in the network and return the modified network to the
        caller.

        """
        virtual_blades = self.provider_api.get_virtual_blades()
        try:
            interconnect = network['blade_interconnect']
        except KeyError as err:
            raise ContextualError(
                "network configuration '%s' does not specify "
                "'blade_interconnect'" % str(network)
            ) from err
        blade_classes = network.get('connected_blade_classes', None)
        blade_classes = (
            virtual_blades.blade_types()
            if blade_classes is None
            else blade_classes
        )
        network['endpoint_ips'] = [
            virtual_blades.blade_ip(blade_class, instance, interconnect)
            for blade_class in blade_classes
            for instance in range(0, virtual_blades.blade_count(blade_class))
        ]
        return network

    def prepare(self):
        """Prepare operation. This drives creation of the platform
        layer definition and any configuration that need to be driven
        down into the platform layer to be ready for deployment.

        """
        self.provider_api = self.stack.get_provider_api()
        blade_config = self.config
        networks = self.config.get('networks', {})
        blade_config['networks'] = {
            key: self.__add_endpoint_ips(network)
            for key, network in networks.items()
        }
        with open(self.blade_config_path, 'w', encoding='UTF-8') as conf:
            safe_dump(blade_config, stream=conf)
        self.prepared = True

    def validate(self):
        """Run the terragrunt plan operation on a prepared ubuntu
        platform layer to make sure that the configuration produces a
        useful result.

        """
        if not self.prepared:
            raise ContextualError(
                "cannot validate an unprepared platform, call prepare() first"
            )

    def deploy(self):
        """Deploy operation. This drives the deployment of platform
        layer resources based on the layer definition. It can only be
        called after the prepare operation (prepare()) completes.

        """
        if not self.prepared:
            raise ContextualError(
                "cannot deploy an unprepared platform, call prepare() first"
            )
        # Open up connections to all of the vTDS Virtual Blades so I can
        # reach SSH (port 22) on each of them to copy in files and run
        # the deployment script.
        #
        # PERFORMANCE OPTIMIZATION: this would be faster if the
        # deployment scripts could run in parallel and be gathered at
        # the end. Currently they run serially, and use one connection
        # at a time.
        virtual_blades = self.provider_api.get_virtual_blades()
        for blade_type in virtual_blades.blade_types():
            for instance in range(0, virtual_blades.blade_count(blade_type)):
                with virtual_blades.connect_blade(
                        22, blade_type, instance
                ) as connection:
                    blade_type = connection.blade_type()
                    local_ip = connection.local_ip()
                    port = connection.local_port()
                    _, private_key_path = virtual_blades.blade_ssh_key_paths(
                        blade_type
                    )
                    options= [
                        '-o', 'BatchMode=yes',
                        '-o', 'NoHostAuthenticationForLocalhost=yes',
                        '-o', 'StrictHostKeyChecking=no',
                        '-o', 'Port=%s' %str(port),
                    ]
                    run(
                        [
                            'scp', '-i', private_key_path, *options,
                            self.blade_config_path,
                            'root@%s:blade_config.yaml' % local_ip
                        ],
                        log_paths(
                            self.build_dir,
                            "copy-config-to-%s" % connection.blade_hostname()
                        )
                    )
                    run(
                        [
                            'scp', '-i', private_key_path, *options,
                            DEPLOY_SCRIPT_PATH,
                            'root@%s:%s' % (local_ip, DEPLOY_SCRIPT_NAME)
                        ],
                        log_paths(
                            self.build_dir,
                            "copy-deploy-script-to-%s" % (
                                connection.blade_hostname()
                            )
                        )
                    )
                    info_msg(
                        "setting up platform on '%s'" % (
                            connection.blade_hostname()
                        )
                    )
                    run(
                        [
                            'ssh', '-i', private_key_path, *options,
                            'root@%s' % local_ip,
                            "chmod 755 ./%s; "
                            "python3 ./%s %s blade_config.yaml" % (
                                DEPLOY_SCRIPT_NAME,
                                DEPLOY_SCRIPT_NAME,
                                blade_type
                            )
                        ],
                        log_paths(
                            self.build_dir,
                            "run-deploy-script-on-%s" % (
                                connection.blade_hostname()
                            )
                        )
                    )

    def remove(self):
        """Remove operation. This will remove all resources
        provisioned for the platform layer.

        """
        if not self.prepared:
            raise ContextualError(
                "cannot deploy an unprepared platform, call prepare() first"
            )
