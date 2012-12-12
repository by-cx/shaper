#!/usr/bin/env python

import re
import sys
import json
import shlex
import datetime
from subprocess import PIPE, Popen, CalledProcessError

def log(message):
    message_formated = "%s: %s" % (datetime.datetime.now(), message)
    print message_formated
    f = open("/var/log/shaper.log", "a")
    f.write(message_formated)
    f.close()


class config(object):
    source = "/etc/ipv6.conf"
    ignore = ["eth0", ]


class System(object):
    def get_addresses(self):
        p = Popen(["ip", "-6", "a"], stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if stderr:
            print stderr
        return [x.strip() for x in stdout.split("\n")]

    def parse(self):
        data = self.get_addresses()
        interface = None
        out = {}
        for line in data:
            match = re.match("[0-9]*: ([a-z0-9@]*):", line)
            if match:
                interface = match.groups()[0]
                if "@" in interface:
                    interface = interface.split("@")[0]
                if interface not in out:
                    out[interface] = []
                continue
            elif interface == "lo":
                continue
            elif "inet6" in line:
                addr = line.split()[1].split("/")[0]
                prefix = line.split()[1].split("/")[1]
                if not "fe80:" in addr:
                    out[interface].append((addr, int(prefix)))
        return out

def sync():
    with open(config.source) as f:
        addrs_database = json.load(f)
    system = System()
    addrs_local = system.parse()
 
    if "debug" in  sys.argv:
        for interface in addrs_local:
            print interface
            if interface in addrs_database: print "database", addrs_database[interface]
            else: print "database", []
            if interface in addrs_local: print "local   ", addrs_local[interface]
            else: print "local   ", []
            print "-------"

    cmds = []
    for interface in addrs_database:
        if interface in config.ignore: continue
        for ip in addrs_database[interface]:
            addrs = addrs_local[interface] if interface in addrs_local else []
            if ip not in addrs:
                cmds.append("ip a a %s/%d dev %s" % (ip[0], ip[1], interface))
    for interface in addrs_local:
        if interface in config.ignore: continue
        for ip in addrs_local[interface]:
            addrs = addrs_database[interface] if interface in addrs_database else []
            if ip not in addrs:
                cmds.append("ip a d %s/%d dev %s" % (ip[0], ip[1], interface))
    return cmds

def main():
    for x in sync():
        print x
        p = Popen(x.split(), stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if stdout: print stdout
        if stderr: print stderr

if __name__ == "__main__":
    try:
        main()
    except IOError, e:
        log("Can't open config file")
        sys.exit(1)
    except OSError, e:
        log("Can't execute some file")
        sys.exit(1)
    except ValueError, e:
        log("No properly parametrs for Popen")
        sys.exit(1)
    except CalledProcessError, e:
        log("Error occured while external program running")
        sys.exit(1)
