import os
import pickle
import re
import itertools
from subprocess import Popen, PIPE
import sys

class ShaperException(Exception): pass

CONFIG_FILE = "/var/cache/shaper/shaper.data"

if not os.path.isdir("/var/cache/shaper"):
    os.makedirs("/var/cache/shaper")

DEFS = {}
DEFS["hfsc"] = {
    "qdisc-del": "qdisc del dev %(iface)s root",
    "qdisc-root": "qdisc add dev %(iface)s root handle 1: hfsc",
    "qdisc": "qdisc add dev %(iface)s parent %(parent)s handle %(qid)s sfq perturb 10",
    "class": "class add dev %(iface)s parent %(parent)s classid %(cid)s hfsc sc rate %(rate)s ul rate %(ceil)s",
    "filter4": "filter add dev %(iface)s parent %(parent)s protocol ip prio 100 u32 match ip dst %(ip)s flowid %(qid)s",
    "filter6": "filter add dev %(iface)s parent %(parent)s protocol ip6 prio 200 u32 match ip6 dst %(ip)s flowid %(qid)s",
    }
DEFS["htb"] = {
    "qdisc-del": "qdisc del dev %(iface)s root",
    "qdisc-root": "qdisc add dev %(iface)s root handle 1: htb r2q 1",
    "qdisc": "qdisc add dev %(iface)s parent %(parent)s handle %(qid)s sfq perturb 10",
    "class": "class add dev %(iface)s parent %(parent)s classid %(cid)s htb rate %(rate)s ceil %(ceil)s",
    "filter4": "filter add dev %(iface)s parent %(parent)s protocol ip prio 100 u32 match ip %(direction)s %(ip)s flowid %(qid)s",
    "filter6": "filter add dev %(iface)s parent %(parent)s protocol ip6 prio 200 u32 match ip6 %(direction)s %(ip)s flowid %(qid)s",
    }
DEF=DEFS["htb"]

GLOBAL_CID=1
GLOBAL_QID=2
INTERFACES = {
    "up": (0, 2),
    "down": (1, 3),
}

class Rule(object):
    """Rule object"""

    rule_regexp1 = "^([0-9\.]*)(kbit|kbps|mbit|mbps|bit|bps)$"
    rule_regexp2 = "^([0-9\.]*)(kbit|kbps|mbit|mbps|bit|bps)/([0-9\.]*)(kbit|kbps|mbit|mbps|bit|bps)$"
    rule_regexp3 = "^([a-zA-Z0-9_\-\.]*)$"

    def __init__(self, name, rate=None, ceil=None, ip=None):
        self._name = None
        self._rate_up = None
        self._ceil_up = None
        self._rate_down = None
        self._ceil_down = None
        self._ip = None
        self._ipv6 = False # just for information
        self.childs = []

        self.name = name
        if rate:
            self.rate = rate
        if ceil:
            self.ceil = ceil
        if ip:
            self.ip = ip

    def script(self, parent, iface, direction):
        global GLOBAL_CID, GLOBAL_QID
        l = []
        data = {
            "iface": iface,
            "parent": parent,
            "cid": "1:%d" % GLOBAL_CID,
            "rate": self._rate_up if direction == "up" else self._rate_down,
            "ceil": self._ceil_up if direction == "up" else self._ceil_down,
        }
        GLOBAL_CID += 1

        l.append(DEF["class"] % data)
        if not self.childs:
            qdata = {
                "iface": iface,
                "parent": data["cid"],
                "qid": "%d:" % GLOBAL_QID
            }
            GLOBAL_QID += 1
            l.append(DEF["qdisc"] % qdata)
        if self.ip:
            fdata = {
                "iface": iface,
                "parent": "1:0",
                "direction": "dst" if direction == "down" else "src",
                "ip": self.ip,
                "qid": data["cid"],
            }
            l.append(DEF["filter6" if self._ipv6 else "filter4"] % fdata)

        for child in self.childs:
            l += child.script(data["cid"], iface, direction)
        return l

    def printable_list(self, index=0):
        l = []
        for child in self.childs:
            l.append("%s|- %s" % ("  " * index, child))
            l += child.printable_list(index+1)
        return l

    def get_childs_of_childs(self):
        return self.childs + list(itertools.chain(*[x.get_childs_of_childs() for x in self.childs]))

    def find_and_remove_child(self, name):
        for child in self.childs:
            if child.name == name:
                self.childs.remove(child)
                return True
            else:
                if child.find_and_remove_child(name):
                    return True
        return False

    def _get_value(self, value):
        s = re.search(self.rule_regexp1, value)
        value = float(s.groups()[0])
        unit = s.groups()[1]
        if unit in ("kbps", "mbps", "bps"):
            value *= 8
        if unit[0] == "k":
            value *= 1024
        if unit[0] == "m":
            value *= 1024**2
        return value

    def add_child(self, rule):
        if not self._rate_up or not self._ceil_up or not self._rate_down or not self._ceil_down:
            raise ShaperException("Error: you can't add child before you set the rate and ceil")
        if not rule._rate_up or not rule._ceil_up or not rule._rate_down or not rule._ceil_down:
            raise ShaperException("Error: you can't add child before you set the rate and ceil on child")
        if self._get_value(rule._rate_up) + sum([self._get_value(x._rate_up) for x in self.childs]) > self._get_value(self._rate_up):
            raise ShaperException("Error: Childs exceeded rate up of parent")
        if self._get_value(rule._rate_down) + sum([self._get_value(x._rate_down) for x in self.childs]) > self._get_value(self._rate_down):
            raise ShaperException("Error: Childs exceeded rate down of parent")
        if self._get_value(rule._ceil_up) > self._get_value(self._ceil_up):
            raise ShaperException("Error: Child exceeded ceil up of parent")
        if self._get_value(rule._ceil_down)  > self._get_value(self._ceil_down):
            raise ShaperException("Error: Child exceeded ceil down of parent")
        self._get_value(rule._rate_down)
        self.childs.append(rule)

    def set_rate(self, value):
        if re.match(self.rule_regexp1, value):
            self._rate_down, self._rate_up = value, value
        elif re.match(self.rule_regexp2, value):
            value = value.split("/")
            self._rate_down = value[0]
            self._rate_up = value[1]
        else:
            raise ShaperException("Syntax error: bad rate format")
        if not self._ceil_down or not self._ceil_up:
            self._ceil_down = self._rate_down
            self._ceil_up = self._rate_up
        if self._ceil_down < self._rate_down:
            raise ShaperException("Error: ceil have to be bigger than rate")
        if self._ceil_up < self._rate_up:
            raise ShaperException("Error: ceil have to be bigger than rate")
    def get_rate(self):
        return "%s/%s" % (self._rate_down, self._rate_up)
    rate = property(get_rate, set_rate)

    def set_ceil(self, value):
        if re.match(self.rule_regexp1, value):
            self._ceil_down, self._ceil_up = value, value
        elif re.match(self.rule_regexp2, value):
            value = value.split("/")
            self._ceil_down = value[0]
            self._ceil_up = value[1]
        else:
            raise ShaperException("Syntax error: bad ceil format")
        if not self._rate_down or not self._rate_up:
            self._rate_down = self._ceil_down
            self._rate_up = self._ceil_up
        if self._ceil_down < self._rate_down:
            raise ShaperException("Error: ceil have to be bigger than rate")
        if self._ceil_up < self._rate_up:
            raise ShaperException("Error: ceil have to be bigger than rate")
    def get_ceil(self):
        return "%s/%s" % (self._ceil_down, self._ceil_up)
    ceil = property(get_ceil, set_ceil)

    def get_name(self):
        return self._name
    def set_name(self, value):
        if not re.match(self.rule_regexp3, value):
            raise ShaperException("Error: name is in wrong format - %s" % self.rule_regexp3)
        self._name = value
    name = property(get_name, set_name)

    def get_ip(self):
        return self._ip
    def set_ip(self, value):
        pattern6="^(\A([0-9a-f]{1,4}:){1,1}(:[0-9a-f]{1,4}){1,6}\Z)|(\A([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,5}\Z)|(\A([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,4}\Z)|(\A([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,3}\Z)|(\A([0-9a-f]{1,4}:){1,5}(:[0-9a-f]{1,4}){1,2}\Z)|(\A([0-9a-f]{1,4}:){1,6}(:[0-9a-f]{1,4}){1,1}\Z)|(\A(([0-9a-f]{1,4}:){1,7}|:):\Z)|(\A:(:[0-9a-f]{1,4}){1,7}\Z)|(\A((([0-9a-f]{1,4}:){6})(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3})\Z)|(\A(([0-9a-f]{1,4}:){5}[0-9a-f]{1,4}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3})\Z)|(\A([0-9a-f]{1,4}:){5}:[0-9a-f]{1,4}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,1}(:[0-9a-f]{1,4}){1,4}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,3}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,2}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,1}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A(([0-9a-f]{1,4}:){1,5}|:):(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A:(:[0-9a-f]{1,4}){1,5}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)$"
        if re.match("^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}[/]{0,1}[0-9]{0,2}$", value):
            self._ipv6 = False
            self._ip = value
        elif re.match(pattern6, value):
            self._ipv6 = True
            self._ip = value
        else:
            raise ShaperException("Error: bad IP format")
    ip = property(get_ip, set_ip)

    def __str__(self):
        return "rule %s rate %s ceil %s%s" % (self.name, self.rate, self.ceil, " ip %s" % self.ip if self.ip else "")

    def __unicode__(self):
        return unicode(self.__str__())



class Shaper(object):
    """Shaper object"""

    def __init__(self, iface, rate, ceil):
        self.root = Rule("root")
        self.root.rate = rate
        self.root.ceil = ceil
        self.iterator = 0
        self.iface = iface

        self.filters = []

    def find_child(self, name, exception=True):
        rule = [x for x in [self.root]+self.root.get_childs_of_childs() if x.name == name]
        if not rule:
            if exception:
                raise ShaperException("Error: can't find rule with this name (%s)" % name)
            else:
                return None
        return rule[0]

    def tree(self):
        return self.root.printable_list(1)

    def rules_to_script(self, iface, direction):
        if direction not in ("up", "down"):
            raise ShaperException("Error: direction has to be up or down")
        l = []
        l.append(DEF["qdisc-del"] % {"iface": iface})
        l.append(DEF["qdisc-root"] % {"iface": iface})
        l += self.root.script("1:0", iface, direction)
        return l

    def commit(self):
        iface_up = "imq%d" % INTERFACES["up"][self.iterator % 2]
        iface_down = "imq%d" % INTERFACES["down"][self.iterator % 2]
        error = False

        for rule in self.rules_to_script(iface_up, "up") + self.rules_to_script(iface_down, "down"):
            cmd = "/sbin/tc %s" % rule
            stdout, stderr = run(cmd)
            if stderr and stderr != "RTNETLINK answers: No such file or directory" and "qdisc del dev" not in cmd:
                print stderr
                sys.stderr.write("%s\n" % cmd)
                sys.stderr.write("%s\n" % stderr)
                error = True
            if stdout: print stdout

        stdout, stderr = run("/sbin/iptables -t mangle -L -n")
        if not stdout or  "Chain SHAPER" not in stdout:
            run("/sbin/iptables -t mangle -N SHAPER")
            run("/sbin/ip6tables -t mangle -N SHAPER")
            run("/sbin/iptables -t mangle -A PREROUTING -j SHAPER")
            run("/sbin/iptables -t mangle -A POSTROUTING -j SHAPER")
            run("/sbin/ip6tables -t mangle -A PREROUTING -j SHAPER")
            run("/sbin/ip6tables -t mangle -A POSTROUTING -j SHAPER")

        run("/sbin/iptables -t mangle -F SHAPER")
        run("/sbin/ip6tables -t mangle -F SHAPER")
        run("/sbin/iptables -t mangle -A SHAPER -i %s -j IMQ --todev %d" % (self.iface, INTERFACES["down"][self.iterator % 2]))
        run("/sbin/iptables -t mangle -A SHAPER -o %s -j IMQ --todev %d" % (self.iface, INTERFACES["up"][self.iterator % 2]))
        run("/sbin/ip6tables -t mangle -A SHAPER -i %s -j IMQ --todev %d" % (self.iface, INTERFACES["down"][self.iterator % 2]))
        run("/sbin/ip6tables -t mangle -A SHAPER -o %s -j IMQ --todev %d" % (self.iface, INTERFACES["up"][self.iterator % 2]))

        self.iterator += 1
        return not error

    def shutdown(self, iface):
        print DEF["qdisc-del"] % {"iface": iface}

    def add_rule(self, parent_name, name, rate, ceil, ip=None):
        if self.find_child(name, exception=False):
            raise ShaperException("Error: rule with name %s is already exists" % name)
        rule = self.find_child(parent_name)
        new_rule = Rule(name, rate, ceil, ip)
        rule.add_child(new_rule)

    def del_rule(self, name):
        self.root.find_and_remove_child(name)

    def __str__(self):
        return ""

    def __unicode__(self):
        return unicode(self.__str__())


## Basics

def run(cmd):
    print cmd
    return None, None
    #p = Popen(cmd.split(cmd), stdout=PIPE, stderr=PIPE)
    #return p.communicate()

def save(shaper):
    with open(CONFIG_FILE, "w") as f:
        pickle.dump(shaper, f)


def load():
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return pickle.load(f)
    return None


def init(iface, rate, ceil):
    shaper = Shaper(iface, rate, ceil)
    save(shaper)
    return shaper


## User interface

CMDS = [
    "^(init) rate ([^ ]*) ceil ([^ ]*) iface ([^ ]*)$",
    "^(rule) (add) parent ([^ ]*) name ([^ ]*) rate ([^ ]*) ceil ([^ ]*)$",
    "^(rule) (add) parent ([^ ]*) name ([^ ]*) rate ([^ ]*) ceil ([^ ]*) ip ([^ ]*)$",
    "^(rule) (del) name ([^ ]*)$",
    "^(commit)$",
    "^(list)$",
    "^(help)$",
    "^(script) ([^ ]*) ([^ ]*)$",
]

def usage():
    print "Usage"
    print "    init rate <RATE> ceil <CEIL> iface <IFACE>"
    print "    rule add parent <NAME> name <NAME> rate <RATE> ceil <CEIL>"
    print "    rule add parent <NAME> name <NAME> rate <RATE> ceil <CEIL> ip <IP>"
    print "    rule del name <NAME>"
    print "    commit"
    print "    list"
    print "    help"
    print
    print "Units: bps,kbps,mbps,bit,kbit,mbit"
    print "IP: regular IPv4 with or without (default /32) mask, regular IPv6 with or without prefix (default /128)"
    print "NAME: without spaces and special characters"
    print
    print "init - initialize shaper"
    print "commit - generate scripts and execute them (remove all rules and make new ones)"
    print "list - show your rules in tree"
    print
    print "Beside that you need:"
    print "    * Interfaces imq0(down) imq1(up) imq2(down) imq3(up)"
    print "    * iptables chain SHAPER_UP in mangle table"
    print "    * iptables chain SHAPER_DOWN in mangle table"
    print
    print "Exit statuses"
    print "    0 - everything is ok"
    print "    1 - shaper is not initialized, nothing to save, use init command"
    print "    2 - caught exception, state is saved"
    print "    3 - error during script execution, state is not saved"

def cmd_loop():
    shaper = load()
    if not shaper and not (len(sys.argv) >= 2 and sys.argv[1] == "init"):
        sys.stderr.write("There is no shaper initialized, you have to start with init command.\n\n")
        usage()
        sys.exit(1)

    match = False
    for cmd in CMDS:
        parms = re.match(cmd, " ".join(sys.argv[1:]))
        if parms:
            match = True
            if parms.groups()[0] == "init":
                shaper = init(parms.groups()[3], parms.groups()[1], parms.groups()[2])
            elif parms.groups()[0] == "rule" and parms.groups()[1] == "add" and len(parms.groups()) == 7:
                shaper.add_rule(parms.groups()[2], parms.groups()[3], parms.groups()[4], parms.groups()[5], parms.groups()[6])
            elif parms.groups()[0] == "rule" and parms.groups()[1] == "add":
                shaper.add_rule(parms.groups()[2], parms.groups()[3], parms.groups()[4], parms.groups()[5])
            elif parms.groups()[0] == "rule" and parms.groups()[1] == "del":
                shaper.del_rule(parms.groups()[2])
            elif parms.groups()[0] == "commit":
                if not shaper.commit():
                    sys.stderr.write("Occured errors during tc script, i am not saving the state\n")
                    sys.exit(3)
            elif parms.groups()[0] == "script":
                for x in shaper.rules_to_script(parms.groups()[1], parms.groups()[2]):
                    print "/sbin/tc %s" % x
            elif parms.groups()[0] == "list":
                print shaper.root
                for child in shaper.tree():
                    print child

    save(shaper)
    if not match:
        usage()


def main():
    try:
        cmd_loop()
    except ShaperException as e:
        sys.stderr.write("%s\n" % e)
        sys.exit(2)

if __name__ == "__main__":
    try:
        main()
    except ShaperException as e:
        sys.stderr.write("%s\n" % e)
        sys.exit(2)