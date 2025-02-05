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
from os import (
    sep,
    environ
)
from os.path import join as path_join
from subprocess import (
    Popen,
    TimeoutExpired
)
from tempfile import (
    TemporaryFile,
    TemporaryDirectory
)
from time import sleep
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


def run_cmd(cmd, args, stdin=sys.stdin, timeout=None, check=True, **kwargs):
    """Run a command with output on stdout and errors on stderr

    """
    exitval = 0
    try:
        with Popen(
                [cmd, *args],
                stdin=stdin, stdout=sys.stdout, stderr=sys.stderr,
                **kwargs
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
    if exitval != 0 and check:
        fmt = (
            "command '%s' failed" if not signaled
            else "command '%s' timed out and was killed"
        )
        raise ContextualError(fmt % " ".join([cmd, *args]))
    return exitval


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
    env = environ.copy()
    env['NEEDRESTART_MODE'] = 'a'
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    retries = 10
    while retries > 0:
        if run_cmd("apt", ["update"], check=False, env=env) != 0:
            sleep(5)
            info_msg("retrying apt update")
            retries -= 1
            continue
        if run_cmd("apt", ["upgrade", "-y"], check=False, env=env) != 0:
            sleep(5)
            info_msg("retrying apt upgrade")
            retries -= 1
            continue
        break
    if retries == 0:
        raise ContextualError("too many retries in apt update / upgrade")
    # For some reason I got a failure when this wasn't done even though
    # it shouldn't need to be done. Sticking it in without checking its
    # result just in case.
    run_cmd("apt", ["install", "-y", "apt-utils", "apt"], check=False, env=env)


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
    env = environ.copy()
    env['NEEDRESTART_MODE'] = 'a'
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    run_cmd("apt", ["install", "-y", *packages], env=env)


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


class BladeVENV:
    """Class for creating and setting up the Blade Python virtual
    environment that is shared with other layers.

    """
    def __init__(self, config):
        """Constructor

        """
        self.python_conf = config.get('python', {})
        self.venv_path = self.python_conf.get(
            'blade_venv_path', path_join(sep, 'root', 'blade-venv')
        )
        self.python_binary = path_join(self.venv_path, 'bin', 'python3')

        # This can't be run as the venv python3 because that has not been
        # created yet, so just use the system python3. We are assuming that
        # python and python-venv packages have been installed (as set up in
        # the config) if that is not true, this will fail.
        run_cmd("python3", ['-m', 'venv', self.venv_path])

    def __pypi_install_py_module(self, module_name, description):
        """Install a python module from a PyPI style repository based on
        the location and version found in the descriptio metadata.

        """
        metadata = description.get('metadata', {})
        url = metadata.get('url', None)
        version = metadata.get('version', None)
        args = ['--index-url', url] if url is not None else []
        args += (
            [module_name + version]
            if version is not None
            else [module_name]
        )
        run_cmd(self.python_binary, ['-m', 'pip', 'install'] + args)

    def __git_install_py_module(self, module_name, description):
        """Install a python module from a Git repository containing source
        code for the module based on the Git repository URL and branch or
        tag version found in the description metadata.

        """
        metadata = description.get('metadata', {})
        url = metadata.get('url', None)
        version = metadata.get('version', None)
        if url is None:
            raise ContextualError(
                "no git repository URL provided for python "
                "module '%s'" % module_name
            )
        with TemporaryDirectory(
                suffix='-' + module_name
        ) as tmpdir:
            run_cmd("git", ['clone', url, tmpdir])
            if version is not None:
                run_cmd("git", ['checkout', version], cwd=tmpdir)
            run_cmd(
                self.python_binary,
                ['-m', 'pip', 'install', '-V', '.'], cwd=tmpdir
            )

    def install_python_modules(self):
        """Based on the 'python_modules' section of the configuration,
        install the specified python modules.

        """
        python_modules = self.python_conf.get('modules', {})
        for name, description in python_modules.items():
            module_name = description.get('module_name', None)
            if module_name is None:
                raise ContextualError(
                    "python module description for '%s' [%s] "
                    "contains no 'module_name' field" % (
                        name, str(description)
                    )
                )
            source_type = description.get('source_type', 'pypi')
            if source_type == 'pypi':
                self.__pypi_install_py_module(module_name, description)
            elif source_type == 'git':
                self.__git_install_py_module(module_name, description)
            else:
                raise ContextualError(
                    "unknown python module source type '%s' for "
                    "python module '%s'" % (source_type, name)
                )


def main(argv):
    """Main function...

    """
    # Arguments are 'blade_class' the name of the blade class to which
    # this blade belongs and 'config_path' the path to the
    # configuration file used for this deployment.
    if not argv:
        raise UsageError("no arguments provided")
    if len(argv) < 2:
        raise UsageError("too few arguments")
    if len(argv) > 2:
        raise UsageError("too many arguments")
    blade_class = argv[0]
    config = read_config(argv[1])
    packages = config.get('packages', {})
    setup_packages(packages, blade_class)
    # Set up the blade python virtual environment...
    venv = BladeVENV(config)
    venv.install_python_modules()
    return 0


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
usage: deploy_to_blade blade_class config_path

Where:

    blade_class is the name of the Virtual Blade class to which this
                Virtual Blade belongs.
    config_path is the path to a YAML file containing the blade
                configuration to apply.
"""[1:-1]
    entrypoint(USAGE_MSG, main)
