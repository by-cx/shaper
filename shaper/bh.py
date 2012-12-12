#!/usr/bin/env python

import os
import sys
import requests
import base64
import json
import time
import shlex
import sys
import socket
from subprocess import Popen, PIPE
import datetime
import syslog

OFF=False

shaper_initiated = False
TIMEOUT = 10
last_loop = -1
counter = 0
counter_threshold = 600
perform_refresh = False


class GeneralError(Exception): pass
class CmdError(Exception): pass
class RESTError(Exception): pass


class Config(object):
    def __init__(self):
        self.config_file = "/etc/shaper_config.json"
        self.load_config()

    def load_config(self):
        with open(self.config_file) as f:
            data = json.load(f)
        for key in data:
            self.__setattr__(key, data[key])
config = Config()


def log(message):
    message_formated = "%s: %s" % (datetime.datetime.now(), message)
    print message_formated
    f = open(config.logfile, "a")
    f.write(message_formated)
    f.close()


def confirm_clients(timestamp):
    url = config.url + "shaper-client-reload/timestamp/%d" % timestamp
    r = requests.put(url, auth=tuple(config.userpass), timeout=TIMEOUT)
    if r.status_code != 200:
        raise RESTError("Wrong status code returned (%d)" % r.status_code)


def load_command():
    url = config.url + "shaper-status"
    r = requests.get(url, auth=tuple(config.userpass), timeout=TIMEOUT)
    if r.status_code != 200:
        raise RESTError("Wrong status code returned (%d)" % r.status_code)
    data = json.loads(r.text)
    return data

        
def confirm_command(status):
    url = config.url + "shaper-status/id/%s" % status
    r = requests.put(url, auth=tuple(config.userpass), timeout=TIMEOUT)
    if r.status_code != 200:
        raise RESTError("Wrong status code returned (%d)" % r.status_code)
        

def run(cmd):
    if OFF:
        print "[cmd]:", cmd
        return "", ""
    cmd_list = shlex.split(cmd)
    p = Popen(cmd_list, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    if stdout or stderr:
        print "[cmd]:", cmd
    if stdout:
        print "[stdout]:", stdout
    if stderr:
        print "[stderr]:", stderr
    return stdout, stderr


def load(url):
    r = requests.get(url, auth=tuple(config.userpass), timeout=TIMEOUT)
    if r.status_code != 200:
        raise RESTError("Wrong status code returned (%d)" % r.status_code)
    confirm_clients(time.time())
    data = json.loads(r.text)
    return data    


def process_clients():
    clients = ["up_rate=%d up_ceil=%d down_rate=%d down_ceil=%d name=main" % (config.max_speed, config.max_speed, config.max_speed, config.max_speed)]
    ipv6 = {}
    ban = []
    data = load(config.url + "shaper-client-reload")
    cmds = []
    cmds.append("ipset -F whitelist")
    cmds.append("ipset -F pay")
    cmds.append("ipset -F blacklist")

    for client in data:
        for ip_dict in client["ip"]:
            ip = ip_dict["ip"]
            interface = ip_dict["ipi"]
            #ban 
            if client["up"] <= 0 or client["dl"] <= 0:
                ban.append(ip)
                if "." in ip:
                    cmds.append("ipset -A blacklist %s" % ip)
                continue
            elif client["ty"] == "off":
                ban.append(ip)
                if "." in ip:
                    cmds.append("ipset -A blacklist %s" % ip)
                continue
            elif client["ty"] == "pay":
                ban.append(ip)
                if "." in ip:
                    cmds.append("ipset -A pay %s" % ip)
                continue
            elif client["ty"] == "vir":
                ban.append(ip)
                if "." in ip:
                    cmds.append("ipset -A blacklist %s" % ip)
                continue
            else:
                clients.append("    ip=%s down_rate=64 down_ceil=%d up_rate=64 up_ceil=%d" % (ip.strip().replace("/23","").replace("/27",""), client["dl"], client["up"]))
                if "." in ip:
                    cmds.append("ipset -A whitelist %s" % ip)
                if":" in ip and interface and len(ip.split("/")) == 2:
                    prefix = int(ip.split("/")[1])
                    ip = ip.split("/")[0]

                    if interface in ipv6:
                        ipv6[interface].append((ip, prefix))
                    else:
                        ipv6[interface] = [(ip, prefix)]

    for cmd in cmds:
        run(cmd)

    with open(config.ips_filename, "w") as f:
        f.write("\n".join(clients))
        f.close()
    with open(config.ipv6_setting_filename, "w") as f:
        f.write(json.dumps(ipv6))
        f.close()

def switch_off():
    run("%s stop" % config.shaper_script)
    #if "Chain %s" % config.ban_chain in run("iptables -L -n", True)[0]:
    #    run("iptables -D FORWARD -o %s -j %s" % (config.outgoing_interface, config.ban_chain))
    run("iptables -F %s" % config.ban_chain)
    #    run("iptables -X %s" % config.ban_chain)
    #if "Chain %s" % config.ban_chain in run("ip6tables -L -n", True)[0]:
    #    run("ip6tables -D FORWARD -o %s -j %s" % (config.outgoing_interface, config.ban_chain))
    run("ip6tables -F %s" % config.ban_chain)
    #    run("ip6tables -X %s" % config.ban_chain)


def loop():
    global shaper_initiated
    global counter
    global last_loop
    global perform_refresh

    def refresh():
        process_clients()
        print "Shaper reload"
        #run shaper
        run("shaper -g")
        run("shaper_ipv6sync")
        log("Reload/init performed")
    if last_loop != -1:
        counter += time.time() - last_loop
        
    if counter > counter_threshold:
        counter = 0
        if perform_refresh:
            refresh()
            perform_refresh = False

    status = load_command()
    log("Status: %s | Counter: %.2f/%d | Waiting to refresh: %s" % (status["id"], counter, counter_threshold, "Yes" if perform_refresh else "No"))
    if status["id"] =="off":
        switch_off()
        log("%s performed" % status["id"])
    elif status["id"] == "on" and not shaper_initiated:
        refresh()
        shaper_initiated = True
    elif status["id"] == "refresh" and not shaper_initiated:
        refresh()
        shaper_initiated = True
    elif status["id"] == "refresh":
        perform_refresh = True
    elif status["id"] == "refresh-now":
        refresh()
        perform_refresh = False
    confirm_command(status["id"])
    last_loop = time.time()


def main():
    while 1:
        try:
            loop()
            time.sleep(config.sleep_time)
        except RESTError, e:
            log("Error during communication with REST api server (%s)" % e)
            time.sleep(config.sleep_time)
        except requests.exceptions.ConnectionError, e:
            log("Lost connection")
        except ValueError, e:
            log("Error during response parse")
        except KeyboardInterrupt:
            sys.exit(0)
        except requests.exceptions.Timeout, e:
            log("Lost connection (timeout)")


if __name__ == "__main__":
    main()
