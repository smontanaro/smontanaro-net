#!/usr/bin/env python3

"Keep track of recent website access log activity."

import curses
import datetime
import os
import pickle
import shelve
import socket
import sys
import time

import regex as re
from ua_parser import parse_user_agent


# Standard combined log format regex with named groups
LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) - \S+ \[(?P<date>[^\]]+)\] '
    r'"(?P<request>[^"]*)" (?P<status>\d{3}) (?P<size>\d+) '
    r'"(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
)


def getrecentlog(files, nlines):
    """Return the most recent nlines lines from the list of log files.

    Log files are currently assumed to be in chronological order.
    """

    lines = []
    for f in files:
        with open(f, "r", encoding="utf-8") as inf:
            lines.extend(inf.readlines())
    return lines[-nlines:]


def summarize_ua(uastring):
    "Identify user agent class using ua_parser module."

    ua_dict = shelve.open(os.path.expanduser("~/tmp/uastrings"))
    with open(os.path.expanduser("~/tmp/ua_misses"), "a", encoding="utf8") as misses:
        try:
            if uastring not in ua_dict:
                result = parse_user_agent(uastring)
                if result is not None:
                    result = result.family
                else:
                    misses.write(f"{uastring}\n")
                    result = uastring.strip('"').strip("'").split()[0][:15]
                ua_dict[uastring] = result
            return ua_dict[uastring]
        finally:
            ua_dict.close()


def summarize_records(lines):
    """Extract IP address, response status and user agent from log records.
    
    Ignore a handful of status codes. (Should probably be a paramenter.)
    """

    condensed = {}
    for line in lines:
        record = LOG_PATTERN.match(line)
        if record["status"] in ["304", "403", "405", "444"]:
            continue
        net = f'{".".join(record["ip"].split(".")[0:3])}.0/24'
        key = (net, record["status"], record["user_agent"])
        bot_info = condensed.get(key)
        if bot_info is None:
            bot_info = [0, set([record["ip"]])]
        else:
            bot_info[0] += 1
        condensed[key] = bot_info
    return condensed


HMS_FMT = "%d/%b/%Y:%H:%M:%S"

def main(scr):
    "Bring it all together."

    socket.setdefaulttimeout(2.0)
    hpck = os.path.expanduser("~/tmp/hostnames.pck")
    if os.path.exists(hpck):
        with open(hpck, "rb") as pck:
            hosts = pickle.load(pck)
    else:
        hosts = {}
    while True:
        scr.clear()
        lines = getrecentlog(files=["/var/log/nginx/access.log.1",
                                "/var/log/nginx/access.log"],
                             nlines=2000)
        first_record = LOG_PATTERN.match(lines[0])
        date = datetime.datetime.strptime(first_record["date"],
                                          f"{HMS_FMT} %z")
        scr.addstr(0, 0, f"{date.strftime(HMS_FMT)} ->"
                f" {datetime.datetime.now().strftime(HMS_FMT)}",
                   curses.A_BOLD)
        scr.addstr(1, 0, f"{'count':6s} {'IPs':5s} {'net/ip':16s} "
                   f"{'status':6s} {'bot name':16s} host name",
                   curses.A_BOLD)
        condensed = summarize_records(lines)
        row = 2
        for (bot_info, record) in sorted(zip(condensed.values(),
                                          condensed.keys()))[-35:]:
            (count, ips) = bot_info
            ips = list(ips)
            name = hosts.get(record[0])
            if name is None:
                try:
                    name = socket.gethostbyaddr(ips[0])[0]
                except (socket.timeout, socket.herror):
                    name = "no name"
                hosts[record[0]] = name

            # arbitrarily lop off the last quad
            net = f'{".".join(record[0].split(".")[0:3])}.0/24'
            botname = summarize_ua(record[2])
            if len(ips) == 1:
                net_ip = ips[0]
            else:
                net_ip = net
            out = f"{count:6d} {len(ips):5d} {net_ip:16s} {record[1]:6s} {botname:16s} {name}"
            scr.addstr(row, 0, out)
            row += 1
        with open(hpck, "wb") as pck:
            pickle.dump(hosts, pck)
        scr.move(1, 0)
        scr.refresh()
        time.sleep(39)

    return 0

if __name__ == "__main__":
    sys.exit(curses.wrapper(main))
