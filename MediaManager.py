#!/opt/bin/python

import argparse
import json
import os
import sys
import shutil
import re
import time
import logging
import itertools

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt='%m/%d/%Y_%H:%M:%S', level=logging.DEBUG)

tv_show_cache = {}

def reverse_enumerate(l):
    return itertools.izip(xrange(len(l)-1, -1, -1), reversed(l))

def watch_for_media(folder):
    last_time_stamp = os.stat(folder).st_mtime
    if last_time_stamp < os.stat(folder).st_mtime:
        find_media(folder)
        last_time_stamp = os.stat(folder).st_mtime
    time.sleep(15*60)

def find_media(folder):
    for root, folders, files in os.walk(folder):

        # Filter out hidden item
        for index, entry in reverse_enumerate(folders):
            if entry.startswith(".") or entry.startswith('@'):
                del folders[index]
        for index, entry in reverse_enumerate(files):
            if entry.startswith("."):
                del files[index]

        # logging.info("Checking: {}".format(root))
        for entry in files:
            ext = os.path.splitext(entry)[1].lower()
            if ext in config["accepted_video_exts"]:
                check_media(root, entry)

def check_media(dir, entry):
    # Check if file name contains a known episode pattern
    for regex in config["episode_regexs"]:
        result = re.search(regex, entry, re.I|re.U)
        if result:
            return convert_episode(dir, entry, result)
    convert_movie(dir, entry)

def convert_episode(dir, entry, episode_match):
    logging.info("Found TV episode at: {}".format(os.path.join(dir, entry)))

    name = entry[:entry.find(episode_match.group(0))]
    print(name)


def convert_movie(dir, entry):
    # logging.info("Found movie at: {}".format(os.path.join(dir, entry)))
    pass

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--auto", action="store_true",
        help="Should go with the best guess."
    )
    arg_parser.add_argument("--watch", action="store_true",
        help="Should check folder every 15 mins."
    )

    args = vars(arg_parser.parse_args())

    global config
    with open("./config.json") as reader:
        config = json.load(reader)

    config.update(args)

    logging.info(str(config))

    if config.get("watch"):
        watch_for_media(config["watch_folder"])
    else:
        find_media(config["watch_folder"])
