#!/opt/bin/python

import argparse
import json
import os
import sys
import shutil
import re
import time
import logging

def watch_for_media(folder):
    last_time_stamp = os.stat(folder).st_mtime
    if last_time_stamp < os.stat(folder).st_mtime:
        find_media(folder)
        last_time_stamp = os.stat(folder).st_mtime
    time.sleep(15*60)

def find_media(folder):
    for root, folders, files in os.walk(folder):
        logging.info("Checking: {}".format(root))
        for entry in files:
            ext = os.path.splitext(entry)
            if ext in config["accepted_video_exts"]:
                check_media(root, entry)

def check_media(dir, entry):
    # Check if file name contains a known episode pattern
    for regex in config["episode_regexs"]:
        result = re.search(regex, entry, re.I|re.U)
        if result:
            convert_episode(dir, entry, result)
    convert_movie(dir, entry)

def convert_episode(dir, entry, episode_match):
    logging.info("Found TV episode at: {}".format(os.path.join(dir, entry)))

def convert_movie(dir, entry):
    logging.info("Found movie at: {}".format(os.path.join(dir, entry)))

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

    logging.warning(str(config))

    if config.get("watch"):
        watch_for_media(config["watch_folder"])
    else:
        find_media(config["watch_folder"])
