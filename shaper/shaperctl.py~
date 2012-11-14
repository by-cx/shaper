#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, datetime
from optparse import OptionParser, OptionGroup, TitledHelpFormatter

##Parsování parametrů
from shaper_script import ShaperScript, ShaperConfig, ShaperException

parser = OptionParser()
parser.add_option("-a", "--add", dest="add", help="Add new rule", action="store_true")
parser.add_option("--remove", dest="remove", help="Remove rule", action="store_true")
parser.add_option("-d", "--direction", dest="direction", help="Direction", metavar="UP/DOWN")
parser.add_option("-t", "--target", dest="target", help="Target (IP(v6) address, network)", metavar="IP/NETMASK")
parser.add_option("-m", "--mark", dest="mark", help="Filter by iptables mark (not supported now)", metavar="MARK")
parser.add_option("-p", "--parent", dest="parent", help="Parent of rule", metavar="NAME")
parser.add_option("-n", "--name", dest="name", help="Rule identificator", metavar="NAME")
parser.add_option("-r", "--rate", dest="rate", help="Rate (guaranteed speed)", metavar="NUMBER")
parser.add_option("-c", "--ceil", dest="ceil", help="Ceil (maximal speed)", metavar="NUMBER")
parser.add_option("-g", "--commit", dest="commit", help="Commit the changes", action="store_true")
parser.add_option("-s", "--shutdown", dest="shutdown", help="Shutdown the shapes", action="store_true")
parser.add_option("--print", dest="print_shapes", help="Print the shapes", action="store_true")

(options, args) = parser.parse_args()

shaper_config = ShaperConfig()

if options.add:
    errors = []
    if not options.name:
        errors.append("missing name")
    #if not options.target:
    #    errors.append("No target")
    if not options.rate:
        errors.append("missing rate")
    if not options.ceil:
        errors.append("missing ceil")
    if errors:
        raise ShaperException("Error: %s" % ",".join(errors))

    config = shaper_config.config()

    item = {
        "name": options.name,
        "ceil": options.ceil,
        "rate": options.rate,
    }
    if options.target:
        item["ip"] = options.target

    shaper_script = ShaperScript(config["shaper_script"], "", "")
    shaper_script.add_rule(item, parent=options.parent)
    shaper_script.save()

    sys.exit(0)
elif options.remove:
    errors = []
    if not options.name:
        errors.append("missing name")
    if errors:
        raise ShaperException("Error: %s" % ",".join(errors))
    config = shaper_config.config()
    shaper_script = ShaperScript(config["shaper_script"], "", "")
    shaper_script.rm_rule(name=options.name)
    shaper_script.save()
    sys.exit(0)
elif options.shutdown:
    config = shaper_config.config()

    interfaces = config["imqs_down"] + config["imqs_up"]
    for interface in interfaces:
        print ShaperScript(config["shaper_script"], interface, "").shutdown()

    sys.exit(0)
elif options.print_shapes:
    config = shaper_config.config()

    in_interface = config["imqs_down"][config["change_counter"] % 2]
    out_interface = config["imqs_up"][config["change_counter"] % 2]
    for interface, direction in ((in_interface, "dst"), (out_interface, "src")):
        shaper_script = ShaperScript(config["shaper_script"], interface, direction)
        shaper_script.parse()
        shaper_script.print_tree()
    shaper_script = ShaperScript(config["shaper_script"], "", "")
    shaper_script.parse()

    sys.exit(0)
elif options.commit:
    config = shaper_config.config()

    in_interface = config["imqs_down"][config["change_counter"] % 2]
    out_interface = config["imqs_up"][config["change_counter"] % 2]
    for interface, direction in ((in_interface, "dst"), (out_interface, "src")):
        shaper_script = ShaperScript(config["shaper_script"], interface, direction)
        shaper_script.parse()
        rules = shaper_script.translate()
        for rule in rules:
            print rule
    shaper_config.counter()
    sys.exit(0)

parser.print_help()
print
print "Usage:"

print "\t# main rule"
print "\t%s -a -n main -r 10m -c 10m" % sys.argv[0]
print "\t# rules for the clients"
print "\t%s -a -p main -n client1 -r 1m -c 5m -t 192.168.1.1" % sys.argv[0]
print "\t%s -a -p main -n client2 -r 3m -c 5m -t 192.168.1.2" % sys.argv[0]
print "\t%s -a -p main -n client3 -r 3m -c 5m -t 192.168.1.3" % sys.argv[0]
print "\t# commit all changes"
print "\t%s -g" % sys.argv[0]
print "\t# shutdown the shaper"
print "\t%s -s" % sys.argv[0]
