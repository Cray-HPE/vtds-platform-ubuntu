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
    info_msg
)
from vtds_base.layers.platform import PlatformAPI

from . import (
    DEPLOY_SCRIPT_PATH,
    DEPLOY_SCRIPT_NAME
)


class Platform(PlatformAPI):
    """PrivatePlatform class, implements the ubuntu platform layer
    accessed through the python Platform API.

    """
    def __init__(self, stack, config, build_dir):
        """Constructor, stash the root of the platfform tree and the
        digested and finalized platform configuration provided by the
        caller that will drive all activities at all layers.

        """
        self.__doc__ = PlatformAPI.__doc__
        self.config = config.get('platform', None)
        if self.config is None:
            raise ContextualError(
                "no platform configuration found in top level configuration"
            )
        self.stack = stack
        self.provider_api = None
        self.build_dir = build_dir
        self.blade_config_path = path_join(
            self.build_dir, 'blade_platform_config.yaml'
        )
        self.prepared = False

    @staticmethod
    def __clean_deleted_py_modules(python_modules):
        """Returns a dictionary of python modules that contains only
        modules for which the 'delete' field is either missing or
        False.

        """
        return {
            key: description for key, description in python_modules.items()
            if not description.get('delete', False)
        }

    def consolidate(self):
        self.provider_api = self.stack.get_provider_api()
        python_config = self.config.get('python', {})
        python_config['modules'] = self.__clean_deleted_py_modules(
            python_config.get('modules', {})
        )

    def prepare(self):
        blade_config = self.config
        with open(self.blade_config_path, 'w', encoding='UTF-8') as conf:
            safe_dump(blade_config, stream=conf)
        self.prepared = True

    def validate(self):
        if not self.prepared:
            raise ContextualError(
                "cannot validate an unprepared platform, call prepare() first"
            )

    def deploy(self):
        if not self.prepared:
            raise ContextualError(
                "cannot deploy an unprepared platform, call prepare() first"
            )
        # Open up connections to all of the vTDS Virtual Blades so I can
        # reach SSH (port 22) on each of them to copy in files and run
        # the deployment script.
        virtual_blades = self.provider_api.get_virtual_blades()
        with virtual_blades.ssh_connect_blades() as connections:
            info_msg(
                "copying '%s' to all Virtual Blades at "
                "'/root/blade_platform_config.yaml'" % (
                    self.blade_config_path
                )
            )
            connections.copy_to(
                self.blade_config_path, "/root/blade_platform_config.yaml",
                False, "upload-platform-config-to"
            )
            info_msg(
                "copying '%s' to all Virtual Blades at '/root/%s'" % (
                    DEPLOY_SCRIPT_PATH, DEPLOY_SCRIPT_NAME
                )
            )
            connections.copy_to(
                DEPLOY_SCRIPT_PATH, "/root/%s" % DEPLOY_SCRIPT_NAME,
                False, "upload-platform-deploy-script-to"
            )
            cmd = (
                "chmod 755 ./%s;"
                "python3 ./%s {{ blade_class }} blade_platform_config.yaml" % (
                    DEPLOY_SCRIPT_NAME,
                    DEPLOY_SCRIPT_NAME
                )
            )
            info_msg("running '%s' on all Virtual Blades" % cmd)
            connections.run_command(cmd, "run-platform-deploy-script-on")

    def remove(self):
        if not self.prepared:
            raise ContextualError(
                "cannot remove an unprepared platform, call prepare() first"
            )

    def get_blade_venv_path(self):
        python_config = self.config.get('python', {})
        return python_config.get('blade_venv_path', "/root/blade-venv")

    def get_blade_python_executable(self):
        # NOTE: do not use path_join() here to construct the path. The
        # path here is being constructed for a Linux environment,
        # where path separators are always '/' and which might not
        # match the system this code is running on.
        return "%s/bin/python3" % self.get_blade_venv_path()
