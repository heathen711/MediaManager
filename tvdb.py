#!/usr/bin/env python
import os
import sys
import urllib
import xml.etree.ElementTree as ET

from url_functions import getOnlineContent

class season():
    def keys(self):
        tempKeys = sorted(self.episodes.keys(), key=lambda key: int(key))
        for key in xrange(len(tempKeys)):
            tempKeys[key] = int(tempKeys[key])
        return tempKeys

    def __getitem__(self, episode):
        if str(episode) in self.episodes.keys():
            return self.episodes[str(episode)]
        else:
            return False

    def __repr__(self):
        return "Season: " + self.episodes[self.episodes.keys()[0]]['SeasonNumber'] + " with " + str(len(self.episodes.keys())) + " episodes.\n"

    def __init__(self, episodes):
        self.episodes = episodes

class show():
    def keys(self):
        tempKeys = sorted(self.seasons.keys(), key=lambda key: int(key))
        for key in xrange(len(tempKeys)):
            tempKeys[key] = int(tempKeys[key])
        return tempKeys

    def showKeys(self):
        return self.seriesInfo.keys()

    def __len__(self):
        return len(self.seasons)

    def __getitem__(self, index):
        if str(index) in self.seasons.keys():
            return self.seasons[str(index)]
        elif index in self.seriesInfo.keys():
            return self.seriesInfo[index]
        elif index == 'topSeason':
            return int(self.keys()[-1])
        elif index == 'bottomSeason':
            return int(self.keys()[0])
        else:
            return []

    def __repr__(self):
        info = self.seriesInfo['SeriesName'] + " with " + str(len(self.seasons.keys())) + " seasons.\n"
        sortedKeys = sorted(self.seasons.keys(), key=lambda key: int(key))
        for key in sortedKeys:
            info += str(self.seasons[str(key)])
        return info

    def __init__(self, seriesInfo, sortedInfo):
        self.seriesInfo = seriesInfo
        self.seasons = {}
        for key in sortedInfo.keys():
            self.seasons[key] = season(sortedInfo[key])

class TVDB:
    def logger(self, data):
        if self.debug:
            fileHandler = open(os.path.join(os.path.dirname(__file__), "history.log"), "a")
            fileHandler.write(str(data)+'\n')
            fileHandler.close()

    def sortEpisodes(self, episodes):
        sortedEpisodes = {}
        if self.debug:
            print "Sorting full list of episode(s) into seasons -> episode(s)."
            print len(episodes)
        for episode in episodes:
            if episode['SeasonNumber'] in sortedEpisodes.keys():
                sortedEpisodes[episode['SeasonNumber']][episode['EpisodeNumber']] = episode
            else:
                sortedEpisodes[episode['SeasonNumber']] = {}
                sortedEpisodes[episode['SeasonNumber']][episode['EpisodeNumber']] = episode
        if self.debug:
            print len(sortedEpisodes)
            print "Done."
        return sortedEpisodes

    def xmlShowToDict(self, xmlString):
        with open("last.xml", "wb") as temp:
            temp.write(xmlString)
        try:
            tree = ET.fromstring(xmlString)
        except Exception as error:
            print "Error: Failed to convert XML data:", error
            return {}
        data = {}
        data["series"] = {}
        data["episodes"] = []
        for item in tree:
            if item.tag == "Series":
                for child in item.getchildren():
                    data["series"][child.tag] = child.text
            elif item.tag == "Episode":
                temp = item.getchildren()
                for child in temp:
                    if child.tag == "SeasonNumber":
                        SeasonNumber = int(child.text)
                    if child.tag == "EpisodeNumber":
                        EpisodeNumber = int(child.text)
                data["episodes"].append({})
                for child in temp:
                    data["episodes"][-1][child.tag] = child.text
        return data

    def xmlSeriesToDict(self, xmlString):
        with open("last.xml", "wb") as temp:
            temp.write(xmlString)
        tree = ET.fromstring(xmlString)
        data = []
        for item in tree:
            temp = {}
            if item.tag == "Series":
                for child in item.getchildren():
                    temp[child.tag] = child.text
                data.append(temp)
        return data

    def getShowInfo(self, seriesID):
        result = False
        rawData = False
        if self.debug:
            print "Retriving online info for series ID: " + seriesID
        path = '/series/{}/all/en.xml'.format(seriesID)
        if os.path.exists(os.path.join("/tmp/", path)):
            with open(os.path.join("/tmp/", path), mode='r') as cacheReader:
                rawData = cacheReader.read()
            print "Using cached xml data."
        if not rawData:
            rawData = getOnlineContent('http://thetvdb.com/api/{}{}'.format(self.apikey, path))
        if rawData:
            os.makedirs(os.path.dirname(os.path.join("/tmp/", path)))
            with open(os.path.join("/tmp/", path), "wb") as cacheWriter:
                cacheWriter.write(rawData)
            rawData = rawData.replace("&", "and")
            data = self.xmlShowToDict(rawData)
            if "episodes" in data.keys():
                data["episodes"] = self.sortEpisodes(data["episodes"])
                result = show(data["series"], data["episodes"])
                if self.debug:
                    print result
        return result

    def search(self, showTitle):
        if len(showTitle) > 0:
            URL = "http://thetvdb.com/api/GetSeries.php?seriesname={}".format(urllib.quote_plus(showTitle))
            if self.debug:
                print "Accessing tvdb: " + URL
            rawData = getOnlineContent(URL)
            if rawData:
                rawData = rawData.replace("&", "and")
                if self.debug:
                    print "Get search results."
                shows = []
                if self.debug:
                    print "Parsing search results..."
                shows = self.xmlSeriesToDict(rawData)
                if self.debug:
                    print "Done."
                return shows
            else:
                return False
        else:
            return False

    def askForShow(self, showTitle = False):
        while True:
            if not showTitle:
                showTitle = raw_input("Enter in show title: ")
            if self.debug:
                print "Searching for: " + showTitle
            shows = self.searchForShow(showTitle)
            if shows:
                print "Got search results."
                if len(shows) > 1:
                    for index in xrange(len(shows)):
                        print str(index+1).zfill(2) + ": " + shows[index]['SeriesName']
                    print str(len(shows)+1).zfill(2) + ": Exit"
                    while True:
                        choice = raw_input("Enter in selection: ")
                        if len(choice) > 0:
                            if choice.isdigit():
                                choice = int(choice) - 1
                                if choice >= 0:
                                    if choice == len(shows):
                                        return False
                                    else:
                                        return shows[choice]
                                else:
                                    print "Invalid selection, please try again."
                            else:
                                print "Invalid selection, please try again."
                        else:
                            print "Invalid input, please try again."
                else:
                    print "Retrieved only one show result."
                    return shows[0]
            else:
                print "No shows found, please try again."
                showTitle = False

    def __init__(self, apiKey, debug = True):
        self.debug = debug
        if os.path.exists(os.path.join(os.path.dirname(__file__), "history.log")):
            os.remove(os.path.join(os.path.dirname(__file__), "history.log"))
        self.apikey = apiKey

if __name__ == '__main__':
    debug = True
    tvdbHandler = TVDB('4E7A4FBBC8CF4D74', debug)
    showInfo = tvdbHandler.search("Doctor Who (2005)")
    if showInfo:
        seriesID = showInfo[0]['seriesid']
        showInfo = tvdbHandler.getShowInfo(seriesID)
        if showInfo:
            print showInfo[1][1]
