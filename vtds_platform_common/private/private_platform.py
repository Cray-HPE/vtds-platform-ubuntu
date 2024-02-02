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
"""Private layer implementation module for the common platform.

"""

from vtds_base import (
    ContextualError,
)


class PrivatePlatform:
    """PrivatePlatform class, implements the common platform layer
    accessed through the python Platform API.

    """
    def __init__(self, stack, config, build_dir):
        """Constructor, stash the root of the platfform tree and the
        digested and finalized platform configuration provided by the
        caller that will drive all activities at all layers.

        """
        self.config = config
        self.stack = stack
        self.build_dir = build_dir
        self.prepared = False

    def prepare(self):
        """Prepare operation. This drives creation of the platform
        layer definition and any configuration that need to be driven
        down into the platform layer to be ready for deployment.

        """
        self.prepared = True
        print("Preparing vtds-platform-common")

    def validate(self):
        """Run the terragrunt plan operation on a prepared common
        platform layer to make sure that the configuration produces a
        useful result.

        """
        if not self.prepared:
            raise ContextualError(
                "cannot validate an unprepared platform, call prepare() first"
            )
        print("Validating vtds-platform-common")

    def deploy(self):
        """Deploy operation. This drives the deployment of platform
        layer resources based on the layer definition. It can only be
        called after the prepare operation (prepare()) completes.

        """
        if not self.prepared:
            raise ContextualError(
                "cannot deploy an unprepared platform, call prepare() first"
            )
        print("Deploying vtds-platform-common")

    def remove(self):
        """Remove operation. This will remove all resources
        provisioned for the platform layer.

        """
        if not self.prepared:
            raise ContextualError(
                "cannot deploy an unprepared platform, call prepare() first"
            )
        print("Removing vtds-platform-common")
