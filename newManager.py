#!/usr/local/bin/python
"""Central script for MediaManager"""

import collections
import datetime
import inspect
import os
import plistlib
import pprint
import re
import shlex
import shutil
import string
import subprocess

from difflib import SequenceMatcher as SM
from random import randint
from time import sleep

from tvdb import TVDB
from url_functions import getOnlineContent

from IMDBAPI import IMDB

imdb = IMDB()

folderInfo = collections.namedtuple("folderInfo", "folderPath tvShows movies", verbose=False)

subtitle = collections.namedtuple("subtitle", "slot, lang, style, default", verbose=False)

# IMDB_Search = collections.namedtuple("IMDB_Search", "ID, name, year, info, match", verbose=False)
# IMDB_Movie = collections.namedtuple("IMDB_Movie", "ID, name, year, plot", verbose=False)

streamInfo = collections.namedtuple(
    "streamInfo", "id, lang, type, info, unsupported", verbose=False)


def history(message):
    if type(message) != str:
        message = str(message)
    logger = open("history.log", 'a')
    logger.write(message + '\n')
    logger.close()
    print(message)


def error(message):
    if type(message) != str:
        message = str(message)
    logger = open("error.log", 'a')
    logger.write(message + '\n')
    logger.close()


def checkPath(value):
    value = unicodeToString(value)
    badLetters = ":*?\"<>|,"
    if os.sep == "/":
        badLetters += "\\"
    if os.sep == "\\":
        badLetters += "/"
    for c in badLetters:
        value = value.replace(c, '_')
    return value


def checkFileName(value):
    value = unicodeToString(value)
    badLetters = ":*?\"<>|,\\/"
    for c in badLetters:
        value = value.replace(c, '_')
    return value


def unicodeToString(text):
    if isinstance(text, unicode):
        return str(text.encode("ascii", "replace"))
    else:
        return str(unicode(text).encode("ascii", "replace"))


class videoClass:
    def convertVideo(self):
        tempFile = os.path.join(self.config['tempFolder'], str(randint(0, 5000)) + ".mp4")
        if not os.path.exists(self.config['tempFolder']):
            os.makedirs(self.config['tempFolder'])
        self.command += "\"{}\"".format(tempFile)
        print self.command
        self.commandSplit = shlex.split(self.command)
        ffmpeg = subprocess.Popen(self.commandSplit, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        converting = False
        duration = "Unknown"
        location = -1
        timeout = datetime.datetime.now() + datetime.timedelta(hours=6)
        while ffmpeg.poll() == None:
            line = ''
            while True:
                letter = ffmpeg.stderr.read(1)
                if letter == '\n' or letter == '\r' or letter == '':
                    break
                else:
                    line += letter

            # Get length of video
            if "Duration:" in line:
                duration = re.search("\d\d:\d\d:\d\d\.\d\d", line)

            print line
            if datetime.datetime.now() > timeout:
                ffmpeg.kill()
                sleep(10)
                try:
                    os.remove(tempFile)
                except:
                    pass
                raise Exception(
                    "FFMpeg converstion has been running for more then 6 hours, killing it.")
        if ffmpeg.returncode != 0:
            try:
                os.remove(tempFile)
            except:
                pass
            raise Exception(
                "FFMpeg convert did not exit with all clear. Exited with: {}".format(ffmpeg.returncode))

        try:
            shutil.move(tempFile, self.outputFile)
            return True
        except Exception as error:
            raise Exception(
                "Failed to move temp file: {} -> {} with error: {}".format(self.originalVideo, self.outputFile, error))

    def convertFile(self):
        # Check if the videoFile already exsists
        if os.path.exists(self.outputFile):
            raise Exception("Video with the same destination already exists, skipping.")

        # Prepare for the folder path for the move
        if not os.path.exists(self.destination):
            os.makedirs(self.destination)

        # Move subtitles and place it in the destination folder
        if self.subFiles:
            subOutputFile = "{}.{}".format(self.outputFile[:self.outputFile.rfind(
                '.')], self.subFiles[self.subFiles.rfind('.'):])
            shutil.move(self.subFiles, subOutputFile)

        self.convertVideo()

        os.remove(self.originalVideo)

    def mapFileStreams(self):
        results = []

        streams = []
        # ffprobe -analyzeduration 5000 %file$
        self.command = "/usr/bin/env ffprobe -analyzeduration 5000 \"{}\"".format(
            self.originalVideo)
        self.command = shlex.split(self.command)
        ffprobe = subprocess.check_output(self.command, stderr=subprocess.STDOUT).split("\n")
        for line in ffprobe:
            if "Stream" in line:
                info = re.search("Stream\ \#(\d{1,2}\:\d{1,2})(.*?)\:\ (.+?)\:\ (.*)", line)
                unsupported = False
                streams.append(streamInfo(info.group(1), info.group(2).replace(
                    '(', '').replace(')', ''), info.group(3), info.group(4), unsupported))
            if "Unsupported codec with id " in line:
                streamID = re.search("stream\ (\d+?)", line)
                streamID = streamID.group(1)
                if streamID.isdigit():
                    streamID = int(streamID)
                    streams[streamID]._replace(unsupported=True)

        sortedStreams = {
            'audio': [],
            'subtitle': [],
            'video': []
        }
        for stream in streams:
            if stream.type == 'Audio':
                sortedStreams['audio'].append(stream)
            if stream.type == 'Subtitle':
                for entry in self.config['acceptableSubtitleTypes']:
                    if stream.info.startswith(entry):
                        sortedStreams['subtitle'].append(stream)
            if stream.type == 'Video':
                for entry in self.config['acceptableVideoTypes']:
                    if stream.info.startswith(entry):
                        sortedStreams['video'].append(stream)

        self.streams = sortedStreams

        self.buildCommand()

        if self.forceConvert:
            self.conversionLevel = 3
        elif self.requiredConversion['video']:
            self.conversionLevel = 3
        elif self.requiredConversion['audio']:
            self.conversionLevel = 2
        elif self.requiredConversion['subtitle']:
            self.conversionLevel = 1
        else:
            self.conversionLevel = 0

    def buildCommand(self):
        # self.forceConvert = True
        self.requiredConversion = dict(video=False, audio=False, subtitle=False)
        if self.config['cpuLimit']:
            self.command = "/usr/bin/env nice -n 8 "
        else:
            self.command = ""

        self.command += "/usr/bin/env ffmpeg -i \"{}\" ".format(self.originalVideo)

        if self.streams['video']:
            for stream in self.streams['video']:
                self.command += "-map {} ".format(stream.id)
                if not self.forceConvert:
                    resolution = re.search("\ (\d+?)x(\d+?)[\ \,]", stream.info)
                    if resolution:
                        width = int(resolution.group(1))
                        height = int(resolution.group(2))
                        if width <= 1300 and height <= 750 and "h264" in stream.info:
                            self.command += "-vcodec copy "
                        else:
                            # self.command += "-profile:v main -level 3.1 -maxrate 2m "
                            self.command += "-profile:v main -level 3.1 -maxrate 3m -vf 'scale=-2:720:flags=lanczos' "
                            self.requiredConversion['video'] = True

        if self.streams['audio']:
            for stream in self.streams['audio']:
                self.command += "-map {} ".format(stream.id)
                if not self.forceConvert:
                    if "aac" in stream.info:
                        self.command += "-acodec copy "
                    else:
                        self.command += "-strict -2 -acodec aac -maxrate 256k "
                        self.requiredConversion['audio'] = True

        if self.forceConvert:
            self.command += "-profile main -level 3.1 -maxrate 3m scale=-1:720 "

        if len(self.streams['subtitle']) > 0:

            for stream in self.streams['subtitle']:
                self.command += "-map {} ".format(stream.id)
                if "mov_text" in stream.info:
                    self.command += "-scodec copy "
                else:
                    self.command += "-scodec mov_text "
                    self.requiredConversion['subtitle'] = True

        self.command += "-map_metadata -1 "

    def checkForSubFiles(self):
        self.subFiles = []
        beginning = self.videoFile
        beginning = beginning[:beginning.rfind('.')]
        if self.videoPath != self.config['watchedFolder']:
            walker = os.walk(self.videoPath)
            for path in walker:
                for file in path[2]:
                    if file[file.rfind('.'):] in self.config['subtitleExtensions']:
                        if file != self.videoFile:
                            self.subFiles.append(os.path.join(path[0], file))
        else:
            self.subFiles = os.listdir(self.config['watchedFolder'])
            for item in range(len(self.subFiles)-1, -1, -1):
                if not self.subFiles[item].startswith(beginning) or self.subFiles[item][self.subFiles[item].rfind('.'):].lower() not in self.config['subtitleExtensions']:
                    self.subFiles.pop(item)

    def start(self, config, videoPath, videoFile):
        self.config = config
        self.videoPath = videoPath
        if self.videoPath[-1] != os.sep:
            self.videoPath = self.videoPath + os.sep
        self.videoFile = videoFile
        self.originalVideo = os.path.join(self.videoPath, self.videoFile)
        self.forceConvert = False

        # ffprobe video for info
        self.mapFileStreams()
        if self.config['mode']:
            if self.conversionLevel > self.config['mode']:
                raise Exception(
                    "Conversion level is higher then mode, video will not be converted.")
        self.checkForSubFiles()
        return True


class tvEpisode(videoClass):
    def __init__(self, config, videoPath, videoFile, selectedTvShow, anime):
        self.config = config

        self.start(config, videoPath, videoFile)
        self.showInfo = selectedTvShow
        self.SeEp = [1, 1]
        self.anime = anime

        if 'ova' in self.videoFile.lower():
            self.ova = True
        else:
            self.ova = False

        self.showNumbers = []
        for expression in range(0, len(self.config['episodeRegEx'])):
            result = re.search(self.config['episodeRegEx'][expression],
                               " {} ".format(self.videoFile.lower()))
            if result:
                for item in result.groups()[1:]:
                    if item.isdigit():
                        self.showNumbers.append(int(item))
                    else:
                        raise Exception("Regex groupings '()' should only be digits.")
                break
        if not self.showNumbers:
            result = re.search("((\d\d)(\d\d))", self.videoFile.lower())
            if result:
                for item in result.groups()[1:]:
                    if item.isdigit():
                        self.showNumbers.append(int(item))
                    else:
                        raise Exception("Error: regex groupings '()' should only be digits.")

        self.seasonEpisodeFilter()

        self.outputFileName = "{} - S{:02}E{:02} - {}.mp4".format(
            self.showInfo['SeriesName'], self.SeEp[0], self.SeEp[1], self.tvShowEpisodeInfo['EpisodeName'])

        self.outputFileName = checkFileName(self.outputFileName)
        if self.anime:
            self.outputFile = self.config['animeShowFolder']
        else:
            self.outputFile = self.config['tvShowsFolder']
        self.outputFile += os.path.join(checkPath(
            self.showInfo['SeriesName']), "Season {:02}".format(self.SeEp[0]))
        self.destination = self.outputFile
        self.outputFile = checkPath(os.path.join(self.outputFile, self.outputFileName))

        self.videoTitle = self.outputFileName

        print "{} -> {}".format(videoFile, self.videoTitle)

    def check(self):
        result = self.showInfo[self.SeEp[0]][self.SeEp[1]]
        if result:
            self.tvShowEpisodeInfo = result
            return True
        return False

    def findByEpisodeNumber(self, needle):
        if self.ova:
            if needle <= self.showInfo[0].keys()[-1]:
                return [0, needle]
        else:
            for season in self.showInfo.keys():
                for episode in self.showInfo[season].keys():
                    if self.showInfo[season][episode]['absolute_number']:
                        if int(self.showInfo[season][episode]['absolute_number']) == int(needle):
                            return [season, episode]

    def seasonEpisodeFilter(self):
        self.seasonInfo = []
        bottomSeason = self.showInfo.keys()[0]
        topSeason = self.showInfo.keys()[-1]
        if bottomSeason != 0:
            for filler in range(0, bottomSeason):
                self.seasonInfo.append(0)
        for entry in range(bottomSeason, topSeason+1):
            self.seasonInfo.append(self.showInfo[entry].keys()[-1])

        self.SeEp = ['', '']
        slot = -1
        seasonWasInPath = False

        if self.showNumbers and self.ova:
            self.SeEp[0] = 0
            self.SeEp[1] = self.showNumbers[0]
        elif self.showNumbers:
            if len(self.showNumbers) == 2:
                self.SeEp[0] = self.showNumbers[0]
                self.SeEp[1] = self.showNumbers[1]
                return
            elif len(self.showNumbers) == 1:
                found = False
                topEpisode = 0
                for season in self.seasonInfo:
                    topEpisode += int(season)

                # check folder path for season number
                # Remove excess puncuation
                punctuation = string.punctuation.replace('(', '').replace(')', '')
                for char in range(0, len(punctuation)):
                    if punctuation[char] in self.videoPath:
                        self.videoPath = self.videoPath.replace(punctuation[char], "")

                filePathFilters = ["([\.\ \_\-]*?s(\d{1,3})[\.\ \_\-\/]*?)",
                                   "([\.\ \_\-]*?season[\.\ \_\-](\d{1,3})[\.\ \_\-\/]*?)"]
                for phrase in filePathFilters:
                    seasonInPath = re.search(phrase, self.videoPath.lower())
                    if seasonInPath:
                        result = seasonInPath.groups()
                        self.SeEp[0] = int(result[1])
                        self.SeEp[1] = self.showNumbers[0]
                        if self.check():
                            return

                self.SeEp[0] = 1
                self.SeEp[1] = self.showNumbers[0]
                if self.check():
                    return

                # assume the number is a full sequencial count not season and Episode
                result = self.findByEpisodeNumber(self.showNumbers[0])
                if result:
                    self.SeEp = result
                    if self.check():
                        return

                if len(str(self.showNumbers[0])) == 3:
                    self.SeEp[0] = int(str(self.showNumbers[0])[0])
                    self.SeEp[1] = int(str(self.showNumbers[0])[1:])
                    if self.check():
                        return
            else:
                raise Exception("Unhandled length to showNumbers: {}".format(self.showNumbers))
        raise Exception("Failed to find Season/Episode information.")


class tvShow:
    def getShowConfirmation(self):
        try:
            self.summary()
        except:
            return False

        self.selectedTvShow = self.showEpisodeInfo
        return True

    def summary(self):
        self.showEpisodeInfo = self.config['tvdbHandler'].getShowInfo(self.showInfo['seriesid'])
        self.tvShowEpisodeInfo = self.showEpisodeInfo[self.SeEp[0]][self.SeEp[1]]

        description = ""

        if "SeriesName" in self.showInfo.keys():
            description += self.showInfo["SeriesName"]
        if "FirstAired" in self.showInfo.keys():
            description += " - {}".format(str(self.showInfo["FirstAired"]).split('-')[0])
        description += " - Season {:02} Episode {:02}".format(self.SeEp[0], self.SeEp[1])
        if "Network" in self.showInfo.keys():
            description += " - {}".format(self.showInfo["Network"])

        if "Overview" in self.tvShowEpisodeInfo.keys():
            try:
                description += " - {}".format(self.tvShowEpisodeInfo["Overview"])
            except:
                description += " - No overview listed."
        return description

    def lookup(self):
        # Check deduced title against previous cached show results.
        for entry in self.config['cachedTvShows']:
            if '(' in entry:
                match = SM(None, self.tvShowTitle.lower(), entry.lower()).ratio()
                tempEntry = entry[:entry.rfind('(')-1]
                match2 = SM(None, self.tvShowTitle.lower(), tempEntry.lower()).ratio()
                if match2 > match:
                    match = match2
            else:
                match = SM(None, self.tvShowTitle.lower(), entry.lower()).ratio()
            if match > 0.90:
                self.tvShowTitle = entry
                break

        results = self.config['tvdbHandler'].search(self.tvShowTitle)
        if results:
            firstTitle = results[0]["SeriesName"]

            # Necessary??
            if firstTitle[0] == ' ':
                firstTitle = firstTitle[1:]
            if firstTitle[-1] == ' ':
                firstTitle = firstTitle[:-1]
            # END

            # TVdb disallows some tv broadcasted shows that no not count as tv series.
            if firstTitle == '** 403: Series Not Permitted **':
                self.config['movies'].append(self.config['movieHandler'](
                    self.config, self.folderPath, self.episode))
                raise RuntimeError("Video is a movie.")
            else:
                # Filter first result and compare looking for a >90% match
                punctuation = string.punctuation.replace('(', '').replace(')', '')
                for char in range(0, len(punctuation)):
                    if punctuation[char] in firstTitle:
                        firstTitle = firstTitle.replace(punctuation[char], "")
                checkOthers = True
                match = SM(None, self.tvShowTitle.lower(), firstTitle.lower()).ratio()
                if (match > .90) or (len(results) == 1):
                    self.showInfo = results[0]
                    if self.getShowConfirmation():
                        if firstTitle not in self.config['cachedTvShows']:
                            self.config['cachedTvShows'].append(firstTitle)
                        checkOthers = False
                    else:
                        raise Exception("Failed to find a match for: {}".formaT(
                            self.tvShowTitle.lower()))
                else:
                    raise Exception(
                        "Failed to find a >90% match: {} <-> {}".format(self.tvShowTitle.lower(), firstTitle.lower()))
        else:
            # Step through remaining words and search online until we get some results.
            foundName = False
            tempTvShowTitle = self.tvShowTitle.lower().split()
            for index in range(len(tempTvShowTitle), 0, -1):
                try:
                    results = self.config['tvdbHandler'].search(' '.join(tempTvShowTitle[:index]))
                except Exception as error:
                    raise Exception(
                        "Error communicating with the tvdb, error: {}".fromat(error))
                if results:
                    if len(results) > 0:
                        self.tvShowTitle = ' '.join(tempTvShowTitle[:index])
                        foundName = True
                        break
            if not foundName:
                print "Episode:", self.episode
                print "From:", self.folderPath
                print "No results for", self.tvShowTitle
                raise Exception("Unable to find a close match to title.")
            else:
                self.lookup()

    def nameFilter(self):

        # Add space buffers for regex searching
        self.tvShowTitle = " {} ".format(self.tvShowTitle)

        # User regex to remove the season and episode info from the file title.
        for expression in range(0, len(self.config['episodeRegEx'])):
            result = re.search(self.config['episodeRegEx'][expression], self.tvShowTitle)
            if result:
                self.tvShowTitle = self.tvShowTitle.replace(result.group(0), ' SeEp ')
                break

        if "ova" in self.tvShowTitle.lower():
            self.tvShowTitle = self.tvShowTitle.lower().replace('ova', '').replace(' seep ', ' SeEp ')

        # Filter out alternative space marks
        altSpace = ['.', '_']
        for alt in altSpace:
            self.tvShowTitle = self.tvShowTitle.replace(alt, ' ')

        self.tvShowTitle = ' '.join(self.tvShowTitle.split())

        if len(self.tvShowTitle) > 0:
            # Remove uploader name from beginning
            if self.tvShowTitle[0] == '(':
                self.tvShowTitle = self.tvShowTitle[self.tvShowTitle.find(')')+1:]

            if self.tvShowTitle[0] == '[':
                self.tvShowTitle = self.tvShowTitle[self.tvShowTitle.find(']')+1:]

            self.tvShowTitle = self.tvShowTitle.replace('(', "").replace(')', "")

            # Use common descprtion terms to find end of tvShow title

            stop = len(self.tvShowTitle)
            for term in self.config['commonTerms']:
                if " {} ".format(term.lower()) in " {} ".format(self.tvShowTitle):
                    place = self.tvShowTitle.find(term.lower())
                    if place < stop:
                        stop = place
            self.tvShowTitle = self.tvShowTitle[:stop]

            if 'SeEp' in self.tvShowTitle:
                self.tvShowTitle = self.tvShowTitle[:self.tvShowTitle.find('SeEp')]

        # After filtering if we dont have anything else lets check the folder path, incase the file name is only the episode number but show and season are in the path.
        if len(self.tvShowTitle) <= 1 and self.checkingPath == False:
            tempFolderPath = self.folderPath
            if self.config['watchedFolder'] in self.folderPath:
                tempFolderPath = tempFolderPath.replace(self.config['watchedFolder'], '')
            else:
                raise Exception(
                    "Error in removing original path from file path for processing. Error in path/linking.")
            tempFolderPath = tempFolderPath.replace(os.sep, ' ')
            self.tvShowTitle = tempFolderPath
            self.checkingPath = True
            self.nameFilter()

        # Handle odd leet speak, by capturing full words and replaceing as needed
        result = re.findall("([\s]\d*[\s])", self.tvShowTitle)
        if result:
            place = self.tvShowTitle.find(result[0])
            tempTitle = self.tvShowTitle.replace(result[0], '')
        else:
            tempTitle = self.tvShowTitle

        tempTitle = tempTitle.replace('0', 'o')
        tempTitle = tempTitle.replace('3', 'e')
        tempTitle = tempTitle.replace('4', 'a')
        tempTitle = tempTitle.replace('5', 's')

        if result:
            tempTitle = tempTitle[:place] + result[0] + tempTitle[place:]

        self.tvShowTitle = tempTitle

        # Remove excess puncuation
        punctuation = string.punctuation.replace('(', '').replace(')', '')
        for char in range(0, len(punctuation)):
            if punctuation[char] in self.tvShowTitle:
                self.tvShowTitle = self.tvShowTitle.replace(punctuation[char], "")

        if len(self.tvShowTitle) > 0:
            if self.tvShowTitle[0] == ' ':
                self.tvShowTitle = self.tvShowTitle[1:]
            if self.tvShowTitle[-1] == ' ':
                self.tvShowTitle = self.tvShowTitle[:-1]

    def isAnime(self):
        genres = self.showInfo.get('Genre', "").split('|')
        if 'Animation' in genres:
            self.anime = True
        else:
            self.anime = False

    def buildQueue(self):
        self.queues = [[], [], [], []]
        for episode in self.episodes:
            self.queues[episode.conversionLevel].append(episode)

        return self.queues

    def __init__(self, config, folder, episodes):
        self.selectedTvShow = False
        self.checkingPath = False
        self.config = config
        self.episodes = []

        if not isinstance(episodes, list):
            self.episode = episodes
        else:
            self.episode = episodes[0]

        self.folderPath = os.path.join(self.config['watchedFolder'], folder)

        self.SeEp = [1, 1]
        self.showInfo = None
        self.anime = False

        self.tvShowTitle = episodes[0].lower()
        self.nameFilter()
        self.tvShowTitle = self.tvShowTitle.title()

        self.lookup()
        self.isAnime()

        for index in xrange(len(episodes)):
            try:
                print "Managing: {}".format(episodes[index])
                self.episodes.append(tvEpisode(
                    self.config, self.folderPath, episodes[index], self.selectedTvShow, self.anime))
            except Exception as error:
                # pprint.pprint(inspect.trace())
                print "Failed to manage: {} with error: {}".format(episodes[index], error)


class movie(videoClass):
    def __init__(self, config, videoPath, videoFile):
        self.config = config
        self.start(config, videoPath, videoFile)

        self.nameFilter()

        # Use filtered name for online search and confirmation
        self.getOnlineInfo()

        # Use confirmed movie info for destination and title
        self.movieTitle = checkFileName(self.movieInfo["title"])
        if len(self.movieInfo["releaseDate"][:5]) > 0:
            self.movieTitle += ' (' + str(self.movieInfo["releaseDate"][:5]) + ')'

        self.movieTitle += ".mp4"
        self.movieTitle = checkPath(self.movieTitle)

        self.destination = os.path.join(
            checkPath(self.config['moviesFolder']), self.movieTitle[:self.movieTitle.rfind('.')])
        self.outputFile = os.path.join(self.destination, self.movieTitle)

    def generateSummary(self):
        self.summary = ""

        self.summary += self.movieInfo["title"]
        if len(self.movieInfo["releaseDate"][:5]) > 0:
            self.summary += " -", self.movieInfo["releaseDate"][:5]
        if len(self.movieInfo["summary"]) > 0:
            self.summary += " -", self.movieInfo["summary"]
        else:
            self.summary += " - No Plot listed."

    def clearShowInfo(self):
        # Empty the parameters for new searching
        self.curMovie = None
        self.movieInfo = None
        self.summary = None
        self.destination = None

    def getConfirmation(self, curMovie, assume=False):
        # Obtain movie summary and prompt user for confirmation to use the selected info
        result = self.imdbMovieInfo(curMovie.ID)
        if result:
            self.curMovie = curMovie
            self.movieInfo = result
            return True
        else:
            return False

    def nameFilter(self):
        self.videoTitle = self.videoFile
        # Remove uploader name from beginning
        if self.videoTitle[0] == '(':
            self.videoTitle = self.videoTitle[self.videoTitle.find(')')+1:]
        if self.videoTitle[0] == '[':
            self.videoTitle = self.videoTitle[self.videoTitle.find(']')+1:]

        # Remove extra parentesies from around years or anything
        self.videoTitle = self.videoTitle.replace('(', "").replace(')', "")

        # Filter out alternative space marks
        altSpace = ['.', '_']
        for alt in altSpace:
            self.videoTitle = self.videoTitle.replace(alt, ' ')

        # Use common descprtion terms to find end of movie title
        self.videoTitle = self.videoTitle.lower().split()

        stop = len(self.videoTitle)
        for term in self.config['commonTerms']:
            if term.lower() in self.videoTitle:
                place = self.videoTitle.index(term.lower())
                if place < stop:
                    stop = place

        self.videoTitle = ' '.join(self.videoTitle[:stop])

        # Add/restore parentesies around the year if it's left after filtering.
        # year = re.search("\ \d\d\d\d\ ", self.videoTitle)
        # try:
        #     self.videoTitle = self.videoTitle.replace(
        #         year.group(0), " (" + year.group(0)[1:-1] + ") ")
        # except:
        #     pass

    # def imdbMovieInfo(self, movieID):
    #     URL = "http://www.imdb.com/title/tt" + movieID + "/"
    #     data = getOnlineContent(URL)
    #
    #     data = data.replace("\n", "").replace("\r", "")
    #
    #     # try:
    #     # <h1 itemprop="name" class="">UFC Fight Night: Silva vs. Bisping&nbsp;            </h1>
    #     search = re.search("<h1 itemprop=\"name\"(?:.*?)>([\s\w\W]*?)</h1>", data)
    #     name = search.group(1)
    #     name = name.replace("&nbsp;", "").replace("&raquo;", "")
    #     name = name.strip()
    #     if '<' in name:
    #         name = name[:name.find('<')]
    #     if 'titleYear' in search.group(1):
    #         year = re.search(">(\d\d\d\d)<", search.group(1)).group(1)
    #     else:
    #         year = ''
    #
    #     descriptionIndicator = "<div class=\"summary_text\" itemprop=\"description\">"
    #     sectionStart = data.find(descriptionIndicator)
    #     sectionEnd = data.find("</div>", sectionStart)
    #     description = data[sectionStart+len(descriptionIndicator):sectionEnd]
    #     if '<' in description:
    #         while True:
    #             start = 0
    #             end = len(description)-1
    #             start = description.find('<')
    #             if start == -1:
    #                 break
    #             end = description.find('>', start)
    #             description = description.replace(description[start:end+1], '')
    #     description = description.replace("&nbsp;", "").replace(
    #         "&raquo;", "").replace("See full summary", '')
    #
    #     description = description.strip()
    #
    #     return IMDB_Movie(movieID, name, year, description)
    #
    # def imdbSearch(self, title):
    #     URL = "http://www.imdb.com/find?q={}&s=tt".format(title)
    #     data = getOnlineContent(URL)
    #     with open("{}.html".format(title), "w") as dump:
    #         dump.write(data)
    #     data = data.replace("\n", "")
    #
    #     if "No results found for {}".format(title) in data:
    #         raise RuntimeError('No results from IMDB search for {}'.format(title))
    #
    #     searchRegEx = r'<td class="result_text">\ <a href=\"/title/tt(\d+?)/.+?\"\ >(.+?)</a>\ (.*?)<'
    #     results = re.findall(searchRegEx, data)
    #
    #     exclude = ['(in development)']
    #     index = 0
    #     end = 10
    #     searchResults = []
    #     while True:
    #         keep = True
    #         for offset in range(0, len(exclude)):
    #             if exclude[offset].lower() in results[index][2].lower():
    #                 keep = False
    #         if keep:
    #             year = re.search("\((\d\d\d\d)\)", results[index][2])
    #             if year:
    #                 videoTitle = results[index][1] + '(' + year.group(1) + ')'
    #                 match = SM(None, title.lower(), videoTitle.lower()).ratio()
    #                 searchResults.append(IMDB_Search(results[index][0], results[index][1], year.group(
    #                     1), results[index][2].replace('(' + year.group(1) + ')', ''), match))
    #             else:
    #                 videoTitle = results[index][1]
    #                 match = SM(None, title.lower(), videoTitle.lower()).ratio()
    #                 searchResults.append(IMDB_Search(
    #                     results[index][0], results[index][1], '', results[index][2], match))
    #         if len(searchResults) == 10:
    #             break
    #         elif index == len(results)-1:
    #             break
    #         index += 1
    #
    #     movieMatch = []
    #     otherMatch = []
    #
    #     for index in xrange(len(searchResults)):
    #         if 'tv' not in searchResults[index].info:
    #             movieMatch.append(searchResults[index])
    #         else:
    #             otherMatch.append(searchResults[index])
    #
    #     movieMatch = sorted(movieMatch, key=lambda entry: entry.match, reverse=True)
    #     otherMatch = sorted(otherMatch, key=lambda entry: entry.match, reverse=True)
    #
    #     searchResults = []
    #     for entry in movieMatch:
    #         searchResults.append(entry)
    #     for entry in otherMatch:
    #         searchResults.append(entry)
    #
    #     return searchResults

    def getOnlineInfo(self, ask=False):
        print "Video Title: {}".format(self.videoTitle)
        search = False

        # Prompt user for new title if needed
        if ask:
            while True:
                userInput = raw_input("Enter in title to search: ")
                if not userInput:
                    self.videoTitle = userInput
                    break
                else:
                    print "Invalid input. Please try again."

        movie_id = None
        try:
            movie_id = imdb.getIdFromName(self.videoTitle)
        except:
            pass

        if movie_id:
            self.movieInfo = imdb.getMovieByImdbId(movie_id)
            print "Movie info:"
            pprint.pprint(self.movieInfo)
        else:
            # Step through the file name words and search after each step till we get some results
            foundName = False
            tempvideoTitle = self.videoTitle.lower().split()
            for index in range(len(tempvideoTitle), 0, -1):
                results = imdb.getIdFromName(' '.join(tempvideoTitle[:index]))
                if results:
                    self.videoTitle = ' '.join(tempvideoTitle[:index])
                    foundName = True
                    break
            if foundName:
                self.getOnlineInfo()
            else:
                if self.config['auto']:
                    self.config['tvShows'].append(self.config['tvShowHandler'](
                        self.config, self.videoPath, self.videoFile))
                    raise Exception("Sending video over to TV Shows...")
                else:
                    self.getOnlineInfo(True)


class MediaManager(object):
    def collectionBuilder(self, data, basePath):
        for index in xrange(len(data)):
            data[index] = data[index].replace(basePath, "")

        data.sort(reverse=True)

        folderSets = []

        for line in data:
            folderSets.append({"folder": os.path.dirname(line), "files": [os.path.basename(line)]})

        collectedSets = []
        while len(folderSets) > 0:
            tempSet = folderSets[-1]
            folderSets.pop(-1)
            if tempSet["folder"]:
                for index in range(len(folderSets)-1, -1, -1):
                    if folderSets[index]["folder"] == tempSet["folder"]:
                        tempSet["files"].append(folderSets[index]["files"][0])
                        folderSets.pop(index)
                collectedSets.append(tempSet)
            else:
                for index in range(len(folderSets)-1, -1, -1):
                    match = SM(None, tempSet["files"][0], folderSets[index]["files"][0]).ratio()
                    if folderSets[index]["folder"] == tempSet["folder"] and match >= 0.80:
                        tempSet["files"] += folderSets[index]["files"]
                        folderSets.pop(index)
                collectedSets.append(tempSet)

        for index in xrange(len(collectedSets)):
            commonPrefix = os.path.commonprefix(collectedSets[index]["folder"])
            if commonPrefix:
                tempSet = [collectedSets[index]["folder"], []]
                testChar = collectedSets[index]["files"][0][0]
                for file_index in range(len(collectedSets[index]["files"])-1, 0, -1):
                    if collectedSets[index]["files"][file_index][0] != testChar:
                        tempSet[1].append(collectedSets[index]["files"][file_index])
                        collectedSets[index]["files"].pop(file_index)
                collectedSets.append(tempSet)

        collectedSets.sort()
        return collectedSets

    def isVideo(self, fileName):
        fileName = fileName.lower()
        for ext in self.config['acceptedVideoExtensions']:
            if fileName.endswith(ext.lower()):
                return True
        return False

    def getFilesToCheck(self):
        self.filesToCheck = []
        walker = os.walk(self.config['watchedFolder'])
        for path in walker:
            if ".@__thumb" in path[0] or "@Recycle" in path[0]:
                continue
            else:
                for fileName in path[2]:
                    if not self.isVideo(fileName):
                        continue
                    skipThisFile = False
                    for term in self.config['excludedTerms']:
                        if (term.lower() in fileName.lower()):
                            skipThisFile = True
                            break
                        elif (term.lower() in path[0].lower()):
                            skipThisFile = True
                            break
                    if skipThisFile:
                        continue

                    fileSize = os.path.getsize(os.path.join(path[0], fileName))
                    if fileSize < self.config['minFileSize']:
                        continue

                    found = False
                    for expression in self.config['episodeRegEx']:
                        if re.search(expression, " {} ".format(fileName.lower())):
                            curFile = os.path.join(path[0], fileName)
                            self.rawTvShows.append(curFile)
                            found = True
                            break
                    if not found:
                        curFile = os.path.join(path[0], fileName)
                        self.rawMovies.append(curFile)

    def parseFilesToCheck(self):
        self.rawTvShows = self.collectionBuilder(self.rawTvShows, self.config['watchedFolder'])

        for index in xrange(len(self.rawTvShows)):
            try:
                self.config['tvShows'].append(self.config['tvShowHandler'](
                    self.config, self.rawTvShows[index]["folder"], self.rawTvShows[index]["files"]))
            except Exception as error:
                # pprint.pprint(inspect.trace())
                print "Failed to manage: {} with error {}".format(
                    self.rawTvShows[index]["files"][0], error)

        for index in xrange(len(self.rawMovies)):
            print "Managing: {}".format(self.rawMovies[index])
            try:
                self.config['movies'].append(self.config['movieHandler'](self.config, os.path.dirname(
                    self.rawMovies[index]), os.path.basename(self.rawMovies[index])))
            except Exception as error:
                pprint.pprint(inspect.trace())
                print "Failed to manage: {} with error {}".format(
                    os.path.basename(self.rawMovies[index]), error)

    def parseFilesToConvert(self):
        masterQueue = [[], [], [], []]

        if self.config['movies']:
            for video in self.config['movies']:
                masterQueue[video.conversionLevel].append(video)

        if self.config['tvShows']:
            for show in self.config['tvShows']:
                queue = show.buildQueue()
                for index in xrange(4):
                    for slot in xrange(len(queue[index])):
                        masterQueue[index].append(queue[index][slot])

        for level in masterQueue:
            for video in level:
                try:
                    video.convertFile()
                except Exception as error:
                    print "Failed to convert video: {} with error: {}".format(
                        video.videoTitle, error)

    def __init__(self, config):
        self.config = config
        self.config['tvShowHandler'] = tvShow
        self.config['movieHandler'] = movie
        self.config['tvdbHandler'] = TVDB(self.config['tvdbAPIkey'], self.config['debug'])

        self.config['commonTerms'] += self.config['acceptedVideoExtensions']

        self.config['movies'] = []
        self.config['tvShows'] = []

        self.rawMovies = []
        self.rawTvShows = []

        if os.path.isdir(self.config['watchedFolder']):
            self.getFilesToCheck()
            self.parseFilesToCheck()
            self.parseFilesToConvert()


if __name__ == "__main__":
    print "Media Manager v2\n\n"

    try:
        config = plistlib.readPlist(os.path.join(os.path.dirname(__file__), "config.plist"))
    except Exception:
        print "Error: Failed to read in config plist."
        exit(-1)

    # Clear TVDB cache folderInfo
    shutil.rmtree("/tmp/series/", ignore_errors=True, onerror=None)

    previousStamp = False
    while True:
        curStamp = os.stat(config['watchedFolder']).st_mtime
        if curStamp != previousStamp:
            root = MediaManager(config)
            previousStamp = os.stat(config['watchedFolder']).st_mtime
        else:
            sleep(60*5)
