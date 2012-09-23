#!/usr/bin/env python

import re


def print_error(msg):
    print msg


class ShaperScript(object):
    def __init__(self, script):
        self.script = script

    def load(self):
        with open(self.script) as f:
            return [x.strip("\n") for x in f.readlines() if x.strip("\n")]

    def parse(self):
        def line_parse(data, deep=0):
            subtree = []
            for i, rule in enumerate(data):
                item = {}
                s = re.search("^([ ]*)", rule)
                if s:
                    if len(s.group()) % 4 == 0:
                        if len(s.group()) / 4 == deep:
                            # TODO: check name=value pairs
                            parsed_line = [(x.split("=")[0], x.split("=")[1]) for x in rule.split(" ") if rule.split("=") == 2]
                            for x in parsed_line:
                                # TODO: check right item name
                                # TODO: check right item values
                                item[x[0]] = x[1]
                        else:
                            # TODO: check right deep
                            print "\n".join(data[i + 1:])
                            subtree[-1]["subtree"] = line_parse(data[i + 1:], deep + 1)
                    else:
                        print_error("You can use just %4 spaces (%s)" % rule)
                subtree.append(item)
            return subtree

        rules = self.load()
        tree = line_parse(rules)
        return tree

if __name__ == "__main__":
    shaper_script = ShaperScript("shaper_script")
    shaper_script.parse()
