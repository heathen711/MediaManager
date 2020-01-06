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
import urllib
import requests
import pprint
import inspect
import xml.etree.ElementTree as ET
import errno

from difflib import SequenceMatcher
from cachecontrol import CacheControl
from cachecontrol import CacheControlAdapter
from cachecontrol.heuristics import ExpiresAfter

## Create request session with caching for a day
adapter = CacheControlAdapter(heuristic=ExpiresAfter(days=1))
sess = requests.Session()
sess.mount('http://', adapter)
cached_sess = CacheControl(sess, cache_etags=False)

def reverse_enumerate(l):
    return itertools.izip(xrange(len(l)-1, -1, -1), reversed(l))
    
## Movie functions
def find_on_tmdb(name):
    # remove extension
    name = name.replace(os.path.splitext(name)[1], "")
    
    # replace special chars
    name = re.sub(r"[\:\_\-\(\)\[\]\"]", "", name)
    
    name = name.replace('.', ' ')
        
    name = re.sub(r"\d{4}", "", name)
        
    for item in config["common_terms"]:
        if item in name:
            name = name.replace(item, "")
            
    name = name.strip()
    
    logging.debug(name)
    
    # Search The Movie Database: https://www.themoviedb.org
    search_name = name
    page = 1
    while True:
        url = "https://api.themoviedb.org/3/search/movie?api_key={api}&language=en-US&query={name}&page={page}".format(
            api="c600e2bd7b5924245a6d7464b7da3458", name=urllib.quote_plus(search_name), page=page
        )
        request_handler = cached_sess.get(url)
        logging.debug(request_handler.json())
        
        total_results = request_handler.json().get("total_results", 0)
        if total_results > 0:
            for entry in request_handler.json()["results"]:
                title = entry["title"]
                # replace special chars
                title = re.sub(r"[\:\.\_\-\(\)\[\]\"]", "", title)
                ratio = SequenceMatcher(None, title, search_name).ratio()
<<<<<<< HEAD
                logging.debug("{} ~ {} ({}) => {:.2%}".format(search_name, entry["title"].encode("ascii", "replace"), title, ratio))
=======
                logging.debug("{} ~ {} => {:.2%}".format(search_name, entry["title"].encode("ascii", "replace"), ratio))
>>>>>>> 9ea16638ec4f986c9bb78daf4f84b146d273666d
                if ratio >= 0.85:
                    return entry
        search_name = " ".join(search_name.split(" ")[:-2]).strip()
        if len(search_name) < 2:
            break
        
    raise Exception("Failed to find a movie matching: {}".format(name))

def convert_movie(folder, entry):
    logging.info("Found movie at: {}".format(os.path.join(folder, entry).encode("ascii", "replace")))
    
    movie_info = find_on_tmdb(entry.encode("ascii", "ignore"))
    logging.debug("Movie info: {}".format(movie_info))
    
    new_path = os.path.join(
            config["movies_folder"], movie_info["title"].encode("ascii", "replace"), "{} ({}){}".format(
                movie_info["title"].encode("ascii", "replace"), movie_info["release_date"][:movie_info["release_date"].find("-")],
                os.path.splitext(entry)[1]
            )
        )
    badLetters = ":*?\"<>|,"
    if os.sep == "/":
        badLetters += "\\"
    if os.sep == "\\":
        badLetters += "/"
    for c in badLetters:
        new_path = new_path.replace(c, '_')
    logging.info("New path: {}".format(new_path))
    try:
        os.makedirs(os.path.split(new_path)[0])
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(os.path.split(new_path)[0]):
            pass
        else:
            raise
    shutil.move(
        os.path.join(folder, entry),
        new_path
    )
    
## TV Show functions
def _clean_out_special_chars(name):
    return re.sub("\W", "", name)

def find_on_tvdb(name):
    url = "http://thetvdb.com/api/GetSeries.php?seriesname={}".format(urllib.quote_plus(name))
    
    request_handler = cached_sess.get(url)
    logging.debug(request_handler.text)
    
    xml_handler = ET.fromstring(request_handler.text.encode("ascii", "ignore"))
    
    results = []
    for item in xml_handler:
        temp = {}
        if item.tag == "Series":
            for child in item.getchildren():
                temp[child.tag] = child.text
            results.append(temp)
    
    if not results:
        raise Exception("Failed to find any matching TV show for: {} via TVDB.".format(name))
            
    highest = None
    if results:
        if highest:
            highest_ratio = SequenceMatcher(None, _clean_out_special_chars(results[highest]["SeriesName"]).lower(), name).ratio
        else:
            highest_ratio = 0.0
        for index, result in enumerate(results):
            current_ratio = SequenceMatcher(None, _clean_out_special_chars(result["SeriesName"]).lower(), name).ratio()
            logging.debug("Ratio for: {} => {}: {:.2%}".format(name, result["SeriesName"], current_ratio))
            if current_ratio < 0.85:
                continue
            if current_ratio > highest_ratio:
                highest = index
                highest_ratio = SequenceMatcher(None, results[highest]["SeriesName"], name).ratio
    if highest is None:
        raise Exception("Failed to find a match close enough to: {}".format(name))
    return results[highest]
    
def update_season_episode_info(folder, entry, season_episode_info, show_info):
    if not show_info.get("seriesid"):
        if not season_episode_info.get("season"):
            season_episode_info["season"] = 1
        if season_episode_info.get("count"):
            season_episode_info["episode"] = season_episode_info["count"]
        return season_episode_info
    
    url = 'http://thetvdb.com/api/{api}/series/{series_id}/all/en.xml'.format(
        api="4E7A4FBBC8CF4D74", series_id=show_info["seriesid"]
    )
    
    request_handler = cached_sess.get(url)
    # logging.debug(request_handler.text)
    
    xml_handler = ET.fromstring(request_handler.text.encode("ascii", "ignore"))
    
    episodes = {}
    for item in xml_handler:
        if item.tag == "Episode":
            info = {}
            for entry in item.getchildren():
                if not entry.text:
                    continue
                info[entry.tag] = int(entry.text) if entry.text.isdigit() else entry.text
            if not episodes.get(str(info["SeasonNumber"])):
                episodes[str(info["SeasonNumber"])] = {}
            episodes[str(info["SeasonNumber"])][str(info["EpisodeNumber"])] = info
            
    # logging.debug("Episode info:\n{}".format(pprint.pformat(episodes)))
    
    for season in [x for x in sorted(episodes.keys(), key=lambda a: int(a), reverse=True)]:
        for episode in [x for x in sorted(episodes[season].keys(), key=lambda a: int(a), reverse=True)]:
            if episode == season_episode_info.get("episode") or episodes[season][episode].get("absolute_number") == int(season_episode_info.get("count", -1)):
                season_episode_info["season"] = int(season)
                season_episode_info["episode"] = int(episode)
                return season_episode_info
    
    return season_episode_info
        
    
def convert_episode(folder, entry, episode_match):
    logging.info(
        "Found TV episode in: {} called: {}".format(
            folder.encode("ascii", "backslashreplace"), entry.encode("ascii", "backslashreplace")
        )
    )

    # Filter name to get what is most likely the show name
    name = entry[:entry.find(episode_match.group(0))]
    logging.debug(name)
    filters = [r"\[.+?\]", r"\(.+?\)"]
    for item in filters:
        result = re.search(item, name, re.U)
        if result:
            name = name.replace(result.group(0), "")
    name = name.strip(" .").replace(".", " ").replace("_", " ").strip('- ')
    logging.debug(name)
    
    if name in config.get("renames", {}):
        name = config["renames"][name]
    
<<<<<<< HEAD
    # Search TVDB for the show
    show_info = find_on_tvdb(name)
    logging.debug("Show info: {}".format(show_info))

=======
    try:
        # Search TVDB for the show
        show_info = find_on_tvdb(name)
        logging.debug("Show info: {}".format(show_info))
    except Exception as error:
        logging.error(error)
        show_info = {
            "SeriesName": name
        }
>>>>>>> 9ea16638ec4f986c9bb78daf4f84b146d273666d
        
    # Get the season/episode info we matched earlier
    season_episode_info = episode_match.groupdict()
    logging.debug("season_episode_info: {}".format(season_episode_info))
    
    if season_episode_info.get("count"):
        season_episode_info = update_season_episode_info(folder, entry, season_episode_info, show_info)
    if not (season_episode_info.get("season") and season_episode_info.get("episode")):
        season_episode_info = update_season_episode_info(folder, entry, season_episode_info, show_info)
    
    if not (season_episode_info.get("season") and season_episode_info.get("episode")):
        raise Exception("Failed to find season/episode information for: {}".format(os.path.join(folder, entry)))
        
    new_path = os.path.join(
            config["tv_shows_folder"], show_info["SeriesName"], 
            "{} - S{:02}E{:02}{}".format(
                show_info["SeriesName"], int(season_episode_info["season"]), 
                int(season_episode_info["episode"]), os.path.splitext(entry)[1]
            )
        )
    badLetters = ":*?\"<>|,"
    if os.sep == "/":
        badLetters += "\\"
    if os.sep == "\\":
        badLetters += "/"
    for c in badLetters:
        new_path = new_path.replace(c, '_')
    logging.info("New path: {}".format(new_path))
    try:
        os.makedirs(os.path.split(new_path)[0])
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(os.path.split(new_path)[0]):
            pass
        else:
            raise
    shutil.move(
        os.path.join(folder, entry),
        new_path
    )


## MediaManager functions
def watch_for_media(folder):
    find_media(folder)
    last_time_stamp = os.stat(folder).st_mtime
    while True:
        if last_time_stamp < os.stat(folder).st_mtime:
            find_media(folder)
            last_time_stamp = os.stat(folder).st_mtime
        time.sleep(15)

def find_media(folder):
    for root, folders, files in os.walk(folder):

        # Filter out hidden items
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
                # exit()

def check_media(folder, entry):
    if "sample" in entry.lower():
        os.remove(os.path.join(folder, entry))
        return
    
    if os.path.getsize(os.path.join(folder, entry)) < config["minimum_file_size"]:
        os.remove(os.path.join(folder, entry))
        return
    
    # Check if file name contains a known episode pattern
    for regex in config["episode_regexs"]:
        result = re.search(regex, entry, re.I|re.U)
        if result:
            try:
                convert_episode(folder, entry, result)
            except Exception as error:
                if config.get("debug"):
                    pprint.pprint(inspect.trace())
                logging.error(error)
            return
    try:
        convert_movie(folder, entry)
    except Exception as error:
        if config.get("debug") or True:
            pprint.pprint(inspect.trace())
        logging.error(error)

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--auto", action="store_true",
        help="Should go with the best guess."
    )
    arg_parser.add_argument("--watch", action="store_true",
        help="Should check folder every 15 mins."
    )
    arg_parser.add_argument("--debug", action="store_true",
        help="Print out debug messages."
    )
    arg_parser.add_argument("--save", action="store_true",
        help="Log output to file."
    )

    args = vars(arg_parser.parse_args())

    global config
    with open("./config.json") as reader:
        config = json.load(reader)

    config.update(args)
    
    logging.basicConfig(
        filename="media_manager.log" if config.get("save") else None,
        format='%(asctime)s: %(message)s', datefmt='%m/%d/%Y_%H:%M:%S', 
        level=logging.DEBUG if config.get("debug") else logging.INFO
    )

    logging.debug(str(config))

    if config.get("watch"):
        watch_for_media(config["watch_folder"])
    else:
        find_media(config["watch_folder"])
