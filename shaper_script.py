#!/usr/bin/env python
import re
import os
import json

# 650  2xpce
# 1200 3h
# 800  2h shapercli
# 1600 4h


def print_error(msg):
    print msg

class ShaperException(Exception): pass

class ShaperConfig(object):
    #TODO: config check (number of imqs)
    def config(self):
        default = {
            "interface": "eth0",
            "imqs_up": ["imq0", "imq1"],
            "imqs_down": ["imq2", "imq3"],
            "iptables_chain": "SHAPER",
            "change_counter": 0,
            "shaper_script": "/etc/shaper.conf",
        }
        if not os.path.isdir("/var/lib/shapertool"):
            os.makedirs("/var/lib/shapertool")
        if not os.path.isfile("/var/lib/shapertool/config.json"):
            with open("/var/lib/shapertool/config.json", "w") as f:
                f.write(json.dumps(default, indent=4))
            return default
        else:
            with open("/var/lib/shapertool/config.json") as f:
                data = json.loads(f.read())
            # TODO: better checks, own class propably
            if not "interface" in data:
                raise ShaperException("Error: missing interface field in config")
            if not "imqs_up" in data:
                raise ShaperException("Error: missing imqs_up field in config")
            if not "imqs_down" in data:
                raise ShaperException("Error: missing imqs_down field in config")
            if not "iptables_chain" in data:
                raise ShaperException("Error: missing iptables_chain field in config")
            if not "change_counter" in data:
                raise ShaperException("Error: missing change_counter field in config")
            return data

    def counter(self):
        data = self.config()
        data["change_counter"] += 1
        with open("/var/lib/shapertool/config.json", "w") as f:
                f.write(json.dumps(data, indent=4))

class ShaperScript(object):
    defs = {}
    defs["hfsc"] = {
        "qdisc-del": "qdisc del dev %(iface)s root",
        "qdisc-root": "qdisc add dev %(iface)s root handle 1: hfsc",
        "qdisc": "qdisc add dev %(iface)s parent %(parent)s handle %(qid)s sfq perturb 10",
        "class": "class add dev %(iface)s parent %(parent)s classid %(cid)s hfsc sc rate %(rate)skbit ul rate %(ceil)skbit",
        "filter4": "filter add dev %(iface)s parent %(parent)s protocol ip prio 100 u32 match ip dst %(ip)s flowid %(qid)s",
        "filter6": "filter add dev %(iface)s parent %(parent)s protocol ip6 prio 200 u32 match ip6 dst %(ip)s flowid %(qid)s",
        }
    defs["htb"] = {
        "qdisc-del": "qdisc del dev %(iface)s root",
        "qdisc-root": "qdisc add dev %(iface)s root handle 1: htb r2q 30",
        "qdisc": "qdisc add dev %(iface)s parent %(parent)s handle %(qid)s sfq perturb 10",
        "class": "class add dev %(iface)s parent %(parent)s classid %(cid)s htb rate %(rate)skbit ceil %(ceil)skbit",
        "filter4": "filter add dev %(iface)s parent %(parent)s protocol ip prio 100 u32 match ip %(ip_type)s %(ip)s flowid %(qid)s",
        "filter6": "filter add dev %(iface)s parent %(parent)s protocol ip6 prio 200 u32 match ip6 %(ip_type)s %(ip)s flowid %(qid)s",
        }

    def __init__(self, script, interface, ip_type="dst"):
        self.script = script
        self.interface = interface
        #self.global_ceil = global_ceil
        #self.global_rate = global_rate
        self.ip_type = ip_type  # dst | src
        self.data = []
        self.handler = "htb"
        self._load()
    def _load(self):
        "load script from the file"
        with open(self.script) as f:
            return [x.strip("\n") for x in f.readlines() if x.strip("\n")]

    def _format(self, items, deep=0):
        lines = []
        for item in items:
            line = []
            subtree = []
            for key in item.keys():
                value = item[key]
                if key == "subtree":
                    subtree = value
                else:
                    line.append("%s=%s" % (key, value))
            lines.append("%s%s" % ("    " * deep, " ".join(line)))
            if subtree:
                lines += self._format(subtree, deep + 1)
        return lines

    def shutdown(self):
        return self.defs[self.handler]["qdisc-del"] % {"iface": self.interface}

    def save(self):
        "Save script to the file"
        with open(self.script, "w") as f:
            f.write("\n".join(self._format(self.data)))

    def print_tree(self):
        "Print tc calls on stdout"
        print "\n".join(self._format(self.data))

    def _rule_syntax(self, item):
        errors = []
        if not "name" in item and not "ip" in item:
            errors.append("No name or ip")
        if not "ceil" in item:
            errors.append("Ceil is missing")
        if not "rate" in item:
            errors.append("Rate is missing")
        if "rate" in item:
            if not re.match("^[0-9kmKM]*$", item["rate"]):
                errors.append("Rate is in wrong format")
        if "ceil" in item:
            if not re.match("^[0-9kmKM]*$", item["ceil"]):
                errors.append("Ceil is in wrong format")
        if errors:
            raise ShaperException("Syntax error: %s (%s)" % (" | ".join(errors), item))

    def add_rule(self, new_item, parent=None):
        "Add new rule"
        self._rule_syntax(new_item)
        def find(tree):
            for item in tree:
                if ("name" in item and item["name"] == parent) or \
                    ("ip" in item and item["ip"] == parent):
                    #TODO: check for rate, ceil values (compare to parent)
                    if not "subtree" in item:
                        item["subtree"] = []
                    item["subtree"].append(new_item)
                    return True
                elif "subtree" in item:
                    if find(item["subtree"]):
                        return True
            return False
        if not parent and self.data:
            raise ShaperException("Error: there is already main rule")
        elif not parent:
            self.data.append(new_item)
        else:
            if not find(self.parse()):
                raise ShaperException("Error: parent '%s' doesn't exists" % parent)

    def rm_rule(self, name):
        "Remove any rule and tree under it"
        def find(tree):
            for item in tree:
                if ("name" in item and item["name"] == name) or \
                    ("ip" in item and item["ip"] == name):
                    tree.remove(item)
                    return True
                elif "subtree" in item:
                    if find(item["subtree"]):
                        return True
            return False
        return find(self.parse())

    def parse(self):
        "Parse tree from the file. Content from self.script is loaded here."
        def line_parse2(data, index=0, deep=0):
            subtree = []
            while True:
                if index + 1 > len(data):
                    break
                item = {}
                rule = data[index]
                s = re.search("^([ ]*)", rule)
                if s:
                    if len(s.group()) % 4 == 0:
                        if len(s.group()) / 4 == deep:
                            # TODO: check values
                            for x in rule.split():
                                key = x.split("=")[0]
                                value = x.split("=")[1]
                                if key not in ("rate", "ceil","ip", "name"):
                                    raise ShaperException("Wrong parametr %s on line %d" % (key, index))
                                item[key] = value
                            self._rule_syntax(item)
                        elif len(s.group()) / 4 > deep:
                            # TODO: check right deep
                            subindex, subtree[-1]["subtree"] = line_parse2(data, index, deep + 1)
                            #print subindex
                            index = subindex
                            continue
                        else:
                            break
                    else:
                        print_error("You can use just %4 spaces (%s)" % rule)
                if item:
                    subtree.append(item)
                index += 1
            return index, subtree

        rules = self._load()
        tree = line_parse2(rules)
        self.data = tree[1]
        return tree[1]

    def translate(self):
        "Translate JSON format into "
        qid_counter = 1
        cid_counter = 0

        def make_rules(subtree, cid_counter, qid_counter):
            parent_cid = cid_counter
            rules = []
            for rule in subtree:
                cid_counter += 1
                rules.append(self.defs[self.handler]["class"] % {
                    "iface": self.interface,
                    "parent": "1:%d" % parent_cid,
                    "cid": "1:%d" % cid_counter,
                    "rate": rule["rate"],
                    "ceil": rule["ceil"],
                })
                if "subtree" in rule and rule["subtree"]:
                    cid_counter, qid_counter, subrules = make_rules(rule["subtree"], cid_counter, qid_counter)
                    rules += subrules
                elif "ip" in rule and rule["ip"]:
                    qid_counter += 1
                    rules.append(self.defs[self.handler]["qdisc"] % {
                        "iface": self.interface,
                        "parent": "1:%d" % cid_counter,
                        "qid": "%d:" % qid_counter,
                    })
                    rules.append(self.defs[self.handler]["filter4" if "." in rule["ip"] else "filter6"] % {
                        "iface": self.interface,
                        "parent": "1:",
                        "ip": rule["ip"],
                        #"qid": "%d:" % qid_counter,
                        "qid": "1:%d" % cid_counter,
                        "ip_type": self.ip_type,
                    })
            return cid_counter, qid_counter, rules

        rules = [
            self.defs[self.handler]["qdisc-del"] % {"iface": self.interface},
            self.defs[self.handler]["qdisc-root"] % {"iface": self.interface},
            #self.defs[self.handler]["class"] % {
            #    "iface": self.interface,
            #    "parent": "1:",
            #    "cid": "1:1",
            #    "rate": self.global_rate,
            #    "ceil": self.global_ceil,
            #},
        ]

        tree = self.parse()
        cid_counter, qid_counter, subrules = make_rules(tree, cid_counter, qid_counter)

        def command_map(line):
            return "/sbin/tc %s" % line

        return map(command_map, rules + subrules)


if __name__ == "__main__":
    shaper_script = ShaperScript("shaper_script", "wlan0", "10000", "10000", "src")
    #data = shaper_script.parse()
    #print json.dumps(data, indent=4)
    shaper_script.parse()
    #print shaper_script.config()
    #shaper_script.rm_rule("89.111.104.71")
    #shaper_script.add_rule({"rate": "1000", "ceil": "2000", "ip": "192.168.1.5/32"}, "tube_a")
    shaper_script.print_tree()

    #rules = shaper_script.translate()
    #for rule in rules:
    #    print rule
