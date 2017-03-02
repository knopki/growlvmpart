#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""
LVM partition resizer
"""

import argparse
import json
import os
import subprocess
import sys

# patch env
MY_ENV = os.environ.copy()
MY_ENV["PATH"] = "/usr/sbin:/sbin:" + MY_ENV["PATH"]

def convert_units(str):
    """ Convert some string with binary prefix to int bytes"""
    unit = ''.join(ele for ele in str if not ele.isdigit()).strip().lower()
    return int(''.join(ele for ele in str if ele.isdigit()))*{
        "b": 1,
        "B": 1,
        "k": 2**10,
        "kb": 2**10,
        "m": 2**20,
        "mb": 2**20,
        "g": 2**30,
        "gb": 2**30,
        "t": 2**40,
        "tb": 2**40
    }.get(unit, 1)

def get_arguments():
    """ Parse arguments """
    parser = argparse.ArgumentParser(
        description="""
          Quick and dirty python script to automatically detecting disk resize, expand lvm partitions and fs
        """
    )
    parser.add_argument('--mountpoint', '--path', required=True, help='target mountpoint')
    parser.add_argument('--min', required=True, help='minimum free space')
    parser.add_argument('--max', help='maximum free space')
    args = parser.parse_args()

    # is path exits
    if not os.path.isdir:
        print "path not exists!"
        parser.print_help()
        sys.exit(1)

    # normalize values
    if not args.max:
        args.max = args.min
    try:
        args.min = convert_units(args.min)
        args.max = convert_units(args.max)
        if args.max < args.min:
            args.max = args.min
    except ValueError:
        parser.print_help()
        sys.exit(1)

    return args.mountpoint, args.min, args.max

def disk_usage(path):
    """Return disk usage associated with path."""

    st = os.statvfs(path)
    free = (st.f_bavail * st.f_frsize)
    total = (st.f_blocks * st.f_frsize)
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    try:
        percent = ret = (float(used) / total) * 100
    except ZeroDivisionError:
        percent = 0
    # NB: the percentage is -5% than what shown by df due to
    # reserved blocks that we are currently not considering:
    # http://goo.gl/sWGbH
    return {
        "total": total,
        "used": used,
        "free": free,
        "percent": round(percent, 1)
    }

def lv_info(dev):
    """Return LV info"""
    try:
        lvs = json.loads(
            subprocess.check_output(
                ["lvs", "--reportformat=json", "-o", "lv_name,lv_size,vg_name,lv_path",
                 "--units=b", dev],
                env=MY_ENV))
    except:
        return None
    lv = lvs['report'][0]['lv'][0]
    return {
        "name": lv['lv_name'],
        "size": int(lv['lv_size'][0:-1]),
        "path": lv['lv_path'],
        "vg_name": lv['vg_name']
    }

def vg_info(name):
    """Return VG info"""
    try:
        vgs = json.loads(
            subprocess.check_output(
                ["vgs", "--reportformat=json", "-o",
                 "vg_name,vg_size,vg_free,pv_name", "--units=b", name],
                env=MY_ENV))
    except:
        return None
    vg = vgs['report'][0]['vg'][0]
    return {
        "name": vg['vg_name'],
        "size": int(vg['vg_size'][0:-1]),
        "free": int(vg['vg_free'][0:-1]),
        "pv_name": vg['pv_name']
    }

def pv_info(name):
    """Return VG info"""
    try:
        pvs = json.loads(
            subprocess.check_output(
                ["pvs", "--reportformat=json", "-o", "pv_name,pv_size,pv_free", "--units=b", name],
                env=MY_ENV))
    except:
        return None
    pv = pvs['report'][0]['pv'][0]
    return {
        "name": pv['pv_name'],
        "size": int(pv['pv_size'][0:-1]),
        "free": int(pv['pv_free'][0:-1])
    }

def disk_partition(mountpoint):
    """Return mountpoint nameduple."""

    # get mount and partition info
    phydevs = []
    f = open("/proc/filesystems", "r")
    for line in f:
        if not line.startswith("nodev"):
            phydevs.append(line.strip())
    f.close()

    part = None
    f = open('/etc/mtab', "r")
    for line in f:
        fields = line.split()
        device = fields[0]
        mount = fields[1]
        fstype = fields[2]
        if fstype not in phydevs:
            continue
        if mount != mountpoint:
            continue
        if device == 'none':
            device = ''
        part = {
            "device": device,
            "mountpoint": mount,
            "fstype": fstype
        }
        break
    f.close()
    if not part:
        return None

    # get disk usage
    part['usage'] = disk_usage(part['mountpoint'])

    # get LV info
    part['lv'] = lv_info(device)
    if 'lv' not in part:
        return part

    # get VG info
    part['vg'] = vg_info(part['lv']['vg_name'])
    if 'vg' not in part:
        return part

    # get PV info
    part['pv'] = pv_info(part['vg']['pv_name'])
    if 'pv' not in part:
        return part

    return part

def rescan_devices():
    "Rescan scsi devices"
    import glob
    for file in glob.glob("/sys/class/scsi_device/*/device/rescan"):
        f = open(file, 'w')
        f.write("1")
        f.close()

    for file in glob.glob("/sys/class/scsi_host/host*/scan"):
        f = open(file, 'w')
        f.write("- - -")
        f.close()

def growpart(dev):
    """Extend partiton"""
    disk = dev[0:-1]
    partnum = dev[-1]
    try:
        subprocess.check_output(["growpart", "-u", "auto", disk, partnum], env=MY_ENV)
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            pass
        else:
            raise e


def pvresize(dev):
    """Extend PV"""
    subprocess.check_output(["pvresize", dev], env=MY_ENV)

def lvresize(dev, size):
    """ Extend LV with FS """
    subprocess.check_output(["lvresize", "-r", "--size", str(size)+"b", dev], env=MY_ENV)

def main():
    """ Entry point """
    # parse args
    mountpoint, min, max = get_arguments()

    # get partition info
    part = disk_partition(mountpoint)

    # if not lvm
    if 'lv' not in part or 'vg' not in part or 'pv' not in part:
        print "Not LVM partition?"
        sys.exit(1)

    # resize not needed -> exit
    if part['usage']['free'] >= min:
        sys.exit(0)

    # rescan scsi hosts
    rescan_devices()

    # grow partition
    growpart(part['pv']['name'])

    # pvresize
    pvresize(part['pv']['name'])

    # refresh part info
    part = disk_partition(mountpoint)

    # if not lvm (strange!)
    if 'lv' not in part or 'vg' not in part or 'pv' not in part:
        print "Not LVM partition?"
        sys.exit(1)

    # determine new size of lv
    new_size = part['usage']['used'] + max
    if new_size > (part['lv']['size'] + part['vg']['free']):
        new_size = part['lv']['size'] + part['vg']['free']

    if new_size < part['lv']['size'] and part['fstype'] == 'xfs':
        sys.exit(0)

    # resize lv with fs
    lvresize(part['lv']['path'], new_size)


if __name__ == "__main__":
    main()
