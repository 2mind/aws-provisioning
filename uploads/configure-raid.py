""" configure-raid.py Assembles a RAID array from a group of physical devices.

Usage:
python configure-raid.py [raid type] [device list]

Example:
python configure-raid.py raid-10 /dev/xvdf,/dev/xvdg,/dev/xvdh,/dev/xvdi

Configures a RAID 10 Array using 4 devices /dev/xvd[f-i]. The RAID array is configured as a single device, /dev/md0,
which is then mapped to a volume group, vg0. A single logical volume, ebs is created within the volume group.
The logical volume, /dev/vg0/ebs, supports ext4 and is mounted as /mnt/ebs.

"""
__author__ = 'dixonwh'

from sys import argv
import subprocess
from time import sleep

# RAID Type Codes (raid-type)
RAID_0 = 'raid-0'
RAID_1 = 'raid-1'
RAID_10 = 'raid-10'

# Mapping from RAID Type Code to RAID Level
RAID_MAP = {
    RAID_0: 0,
    RAID_1: 1,
    RAID_10: 10
}

# AWS EBS Device Names
SUPPORTED_DEVICES = ('/dev/xvdf', '/dev/xvdg', '/dev/xvdh', '/dev/xvdi', '/dev/xvdj', '/dev/xvdk', '/dev/xvdl',
                     '/dev/xvdm', '/dev/xvdn', '/dev/xvdo', '/dev/xvdp')

RAID_DEVICE_NAME = '/dev/md0'

def _configure_raid(raid_type, devices, raid_device):
    """ Creates a RAID device using mdadm.

    parameters:
    raid_type -- indicates the type of RAID(0,1,10) to configure
    devices -- comma delimited list of devices to use in the RAID array
    raid_device -- the name of the RAID device
    """
    _validate_raid_configuration(raid_type, devices)
    _configure_raid_device(raid_type, devices, raid_device)
    _configure_volumes(raid_device)

def _configure_volumes(raid_device):
    """ Maps the RAID device to a logical volume.

    parameters:
    raid_device -- the RAID device name to use
    """
    subprocess.call('dd if=/dev/zero of={0} bs=512 count=1'.format(raid_device), shell=True)
    subprocess.call('pvcreate {0}'.format(raid_device), shell=True)
    subprocess.call('vgcreate vg0 {0}'.format(raid_device), shell=True)
    subprocess.call('lvcreate -l 100%vg -n ebs vg0', shell=True)
    subprocess.call('mke2fs -t ext4 -F /dev/vg0/ebs', shell=True)
    subprocess.call('mkdir /mnt/ebs', shell=True)
    subprocess.call('echo "/dev/vg0/ebs /mnt/ebs ext4 defaults,auto,noatime,noexec 0 0" | sudo tee -a /etc/fstab', shell=True)
    subprocess.call('mount /dev/vg0/ebs /mnt/ebs', shell=True)


def _configure_raid_device(raid_type, devices, raid_device):
    """ Creates the RAID device/array from physical devices.

    parameters:
    raid_type -- indicates the type of RAID(0,1,10) to configure
    devices -- comma delimited list of devices to use
    raid_device -- the name of the RAID device to use
    """
    number_devices = len(devices.split(','))
    device_args = devices.replace(',', ' ')

    raid_cmd = 'mdadm --verbose --create {0} --chunk=256 --level={1} --raid-devices={2} {3}'.format(
        raid_device, RAID_MAP[raid_type], number_devices, device_args)

    print('MDADM CMD: {0}'.format(raid_cmd))

    subprocess.call(raid_cmd, shell=True)

    # wait for RAID sync to complete before continuing
    is_syncing = True
    while is_syncing:
        is_syncing = True if subprocess.call('grep resync /proc/mdstat', shell=True) == 0 else False
        sleep(30)

    print('RAID sync complete')

    # persist RAID configuration
    subprocess.call('echo "DEVICE {0}" | tee -a /etc/mdadm/mdadm.conf'.format(device_args), shell=True)
    subprocess.call('mdadm --detail --scan | tee -a /etc/mdadm/mdadm.conf', shell=True)

    # set block device read-ahead cache
    device_list = [raid_device]
    device_list.extend(devices.split(','))

    for device in device_list:
        subprocess.call('blockdev --setra 128 {0}'.format(device), shell=True)



def _validate_raid_configuration(raid_type, devices):
    """ Validates raid type against the number of devices.
    Ensures that the device argument is valid given the requested RAID type.

    Validations include:

    raid-type is one of the supported codes.
    device list doesn't contain duplicates or invalid names (AWS has specific device names for EBS volumes in EC2)
    the number of devices is compatible with the requested RAID level

    parameters:
    raid_type -- The raid type code: raid-0, raid-1, raid-10, etc
    devices -- comma delimited list of devices for the raid array
    """
    if raid_type not in RAID_MAP.keys():
        raise ValueError('Invalid Raid Type. Supported raid-types: {0},{1}, or {2}'.format(RAID_0, RAID_1, RAID_10))

    device_list = devices.split(',')

    if len(device_list) == 0 or not set(device_list).issubset((SUPPORTED_DEVICES)):
        raise ValueError('Invalid devices list.\n Valid devices are: {0}'.format(SUPPORTED_DEVICES))

    if len(device_list) != len(set(device_list)):
        raise ValueError('Duplicate devices found: {0}'.format(devices))

    if raid_type in (RAID_0, RAID_1) and len(device_list) < 2:
        raise ValueError('RAID 0 and 1 require at least 2 devices')

    if raid_type == RAID_10 and len(device_list) not in (4,8):
        raise ValueError('RAID 10 is only supported with 4 or 8 devices')

def _main(args):
    """ Entry point for the script.

    Validates the number of arguments before passing them along to _configure_raid.

    parameters:
    args -- the arguments passed into the script. Arguments are: script name, raid type, and comma delimited device list
    """
    args = argv[1:]

    if len(args) < 2:
        raise RuntimeError('Invalid Arguments.\n Usage: configure.raid.py [raid type] [device list]')

    raid_type = args[0]
    devices = args[1]

    print('Creating RAID Device: {0}: {1}'.format(raid_type, devices))

    _configure_raid(raid_type, devices, RAID_DEVICE_NAME)

if __name__ == '__main__':
    _main(argv)

