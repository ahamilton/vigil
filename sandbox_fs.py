

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import subprocess
import tempfile


class OverlayfsMount():

    def __init__(self, lower_dir, mount_point):
        self.lower_dir = lower_dir
        self.mount_point = mount_point
        self.upper_dir = tempfile.mkdtemp()
        self.work_dir = tempfile.mkdtemp()
        option_string = ("lowerdir=%s,upperdir=%s,workdir=%s" %
                         (self.lower_dir, self.upper_dir, self.work_dir))
        subprocess.check_call(["sudo",  "mount", "-t", "overlayfs", "-o",
                               option_string, "overlayfs", self.mount_point],
                              stderr=subprocess.PIPE)

    def __repr__(self):
        return "<OverlayfsMount:%r over %r>" % (self.mount_point,
                                                self.lower_dir)

    def umount(self):
        subprocess.check_call(["sudo", "umount", "--lazy", self.mount_point])
        subprocess.check_call(["sudo", "rm", "-rf", self.upper_dir,
                               self.work_dir])


def _in_chroot(mount_point, command):
    return ["sudo", "chroot", "--userspec=%s" % os.environ["USER"],
            mount_point] + command


_IN_DIRECTORY_SCRIPT = os.path.join(os.path.dirname(__file__), "in-directory")


def _in_directory(directory_path, command):
    return [_IN_DIRECTORY_SCRIPT, directory_path] + command


def _parse_proc_mounts():
    with open("/proc/mounts") as file_:
        for line in file_:
            yield line.split()


class SandboxFs:

    def __init__(self, mount_point):
        self.mount_point = mount_point
        self.overlay_mounts = []

    def __repr__(self):
        return "<SandboxFs:%r mounts:%r>" % (self.mount_point,
                                             len(self.overlay_mounts))

    def _find_mounts(self):
        all_mounts = set(part[1] for part in _parse_proc_mounts())
        obvious_mount_points = {"/", "/usr", "/bin", "/etc", "/lib", "/dev",
                                "/proc", "/home", "/boot", "/opt", "/run",
                                "/sys", "/root", "/var", "/tmp"}
        return all_mounts.intersection(obvious_mount_points)

    def mount(self):
        self.overlay_mounts = [OverlayfsMount(mount_point,
                                              self.mount_point + mount_point)
                               for mount_point in sorted(self._find_mounts())]

    def umount(self):
        for mount in reversed(self.overlay_mounts):
            mount.umount()
        self.overlay_mounts = []

    def Popen(self, command, env=None):
        full_command = _in_chroot(self.mount_point,
                                  _in_directory(os.getcwd(), command))
        return subprocess.Popen(full_command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env)

    def run_command(self, command, env=None):
        process = self.Popen(command, env)
        stdout, stderr = process.communicate()
        return stdout, stderr, process.returncode