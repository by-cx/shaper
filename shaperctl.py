#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, datetime
from optparse import OptionParser, OptionGroup, TitledHelpFormatter

##Parsování parametrů
parser = OptionParser()
parser.add_option("-a", "--add", dest="add", help="Add new rule", action="store_true")
parser.add_option("-d", "--direction", dest="direction", help="Direction", metavar="UP/DOWN")
parser.add_option("-t", "--target", dest="target", help="Target (IP(v6) address, network)", metavar="IP/NETMASK")
parser.add_option("-m", "--mark", dest="mark", help="Filter by iptables mark (not supported now)", metavar="MARK")
parser.add_option("-p", "--parent", dest="parent", help="Parent of rule", metavar="NAME")
parser.add_option("-n", "--name", dest="name", help="Rule identificator", metavar="NAME")
parser.add_option("-r", "--rate", dest="rate", help="Rate (guaranteed speed)", metavar="NUMBER")
parser.add_option("-c", "--ceil", dest="ceil", help="Ceil (maximal speed)", metavar="NUMBER")
parser.add_option("-g", "--commit", dest="commit", help="Commit the changes", action="store_true")
parser.add_option("-s", "--shutdown", dest="shutdown", help="Shutdown the shapes", action="store_true")
parser.add_option("--print", dest="print", help="Print the shapes", action="store_true")


(options, args) = parser.parse_args()

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
