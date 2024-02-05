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
"""Public API module for the ubuntu platform layer, this gives callers
access to the Platform API and prevents them from seeing the private
implementation of the API.

"""

from vtds_base import ContextualError
from .private.private_platform import PrivatePlatform


class LayerAPI:
    """ Presents the Platform API to callers.

    """
    def __init__(self, stack, config, build_dir):
        """Constructor. Constructs the public API to be used for
        building and interacting with a platform layer based on the
        full stack of vTDS layers loaded, the 'config' data structure
        provided and an absolute path to the 'build_dir' which is a
        scratch area provided by the caller for any platform layer
        build activities to take place.

        """
        self.stack = stack
        platform_config = config.get('platform', None)
        if platform_config is None:
            raise ContextualError(
                "no platform configuration found in top level configuration"
            )
        self.private = PrivatePlatform(stack, platform_config, build_dir)

    def prepare(self):
        """Prepare the platform for deployment.

        """
        self.private.prepare()

    def validate(self):
        """Run any configuration validation that may be appropriate
        for the platform layer.

        """
        self.private.validate()

    def deploy(self):
        """Deploy the platform (must call prepare() prior to this
        call.

        """
        self.private.deploy()

    def remove(self):
        """Remove operation. This will remove all resources
        provisioned for the platform layer.

        """
        self.private.remove()
