#!/usr/bin/env python

import re
import json


def print_error(msg):
    print msg


class ShaperScript(object):
    def __init__(self, script, interface, global_rate, global_ceil, ip_type="dst"):
        self.script = script
        self.interface = interface
        self.global_ceil = global_ceil
        self.global_rate = global_rate
        self.ip_type = ip_type  # dst | src

    def load(self):
        with open(self.script) as f:
            return [x.strip("\n") for x in f.readlines() if x.strip("\n")]

    def parse(self):
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
                            #print index, rule
                            # TODO: check name=value pairs
                            for x in rule.split():
                                key = x.split("=")[0]
                                value = x.split("=")[1]
                                item[key] = value
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

        rules = self.load()
        tree = line_parse2(rules)
        return tree

    def translate(self):
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

        handler = "htb"
        qid_counter = 1
        cid_counter = 1

        def make_rules(subtree, cid_counter, qid_counter):
            parent_cid = cid_counter
            rules = []
            for rule in subtree:
                cid_counter += 1
                rules.append(defs[handler]["class"] % {
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
                    rules.append(defs[handler]["qdisc"] % {
                        "iface": self.interface,
                        "parent": "1:%d" % cid_counter,
                        "qid": "%d:" % qid_counter,
                    })
                    rules.append(defs[handler]["filter4" if "." in rule["ip"] else "filter6"] % {
                        "iface": self.interface,
                        "parent": "1:",
                        "ip": rule["ip"],
                        #"qid": "%d:" % qid_counter,
                        "qid": "1:%d" % cid_counter,
                        "ip_type": self.ip_type,
                    })
            return cid_counter, qid_counter, rules

        rules = [
            defs[handler]["qdisc-del"] % {"iface": self.interface},
            defs[handler]["qdisc-root"] % {"iface": self.interface},
            defs[handler]["class"] % {
                "iface": self.interface,
                "parent": "1:",
                "cid": "1:1",
                "rate": self.global_rate,
                "ceil": self.global_ceil,
            },
        ]

        index, tree = self.parse()
        cid_counter, qid_counter, subrules = make_rules(tree, cid_counter, qid_counter)

        def command_map(line):
            return "/sbin/tc %s" % line

        return map(command_map, rules + subrules)


if __name__ == "__main__":
    shaper_script = ShaperScript("shaper_script", "wlan0", "10000", "10000", "src")
    #index, data = shaper_script.parse()
    #print json.dumps(data, indent=4)
    rules = shaper_script.translate()
    for rule in rules:
        print rule
