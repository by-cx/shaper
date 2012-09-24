#!/usr/bin/env python

import re
import json


def print_error(msg):
    print msg


class ShaperScript(object):
    def __init__(self, script):
        self.script = script

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

if __name__ == "__main__":
    shaper_script = ShaperScript("shaper_script")
    index, data = shaper_script.parse()
    print json.dumps(data, indent=4)
