#!/usr/bin/env python

import re
import json


def print_error(msg):
    print msg


class ShaperScript(object):
    def __init__(self, script, interface, max_rate, max_ceil):
        self.script = script
        self.interface = interface
        self.max_ceil = max_ceil
        self.max_rate = max_rate

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
            defs = {
                "qdisc-del": "qdisc del dev %(iface)s root",
                "qdisc-root": "qdisc add dev %(iface)s root handle 1: hfsc",
                "qdisc": "qdisc add dev %(iface)s parent %(parent)s handle %(qid)s: sfq perturb 10",
                "class": "class add dev %(iface)s parent %(parent)s classid %(cid)s hfsc sc rate %(rate)skbit ul rate %(ceil)skbit",
                "filter4": "filter add dev %(iface)s parent %(parent)s protocol ip prio 100 u32 match ip dst %(ip)s flowid %(qid)s",
                "filter6": "filter add dev %(iface)s parent %(parent)s protocol ip6 prio 200 u32 match ip6 dst %(ip)s flowid %(qid)s",
            }

            def make_rules(subtree, cid_counter, qid_counter):
                rules = []
                for rule in subtree:
                    rule
                    if "subtree" in rule and rule["subtree"]:
                        rules += make_rules(rule["subtree"])
                return rules

            rules = [
                defs["qdisc-del"] % {"iface": self.interface},
                defs["qdisc-root"] % {"iface": self.interface},
                defs["class"] % {
                    "iface": self.interface,
                    "parent": "1:",
                    "cid": "1:1",
                    "qid": "",
                    "rate": "",
                    "ceil": "",
                },
            ]
            qid_counter = 1
            cid_counter = 1

            tree = self.parse()
            rules += make_rules(tree, cid_counter, qid_counter)


if __name__ == "__main__":
    shaper_script = ShaperScript("shaper_script")
    index, data = shaper_script.parse()
    print json.dumps(data, indent=4)
