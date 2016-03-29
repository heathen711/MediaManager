from __future__ import print_function
import unicodedata
import os
import sys
import re
import string
import shlex
import subprocess
import collections
import shutil
import urllib
import threading
import datetime
import fractions
from threading import Thread
from time import sleep
from tvdb import Tvdb
from difflib import SequenceMatcher as SM
from random import randint

folderInfo = collections.namedtuple("folderInfo", "folderPath tvShows movies", verbose=False)

subtitle = collections.namedtuple("subtitle", "slot, lang, style, default", verbose=False)

IMDB_Search = collections.namedtuple("IMDB_Search", "ID, name, year, info, match", verbose=False)
IMDB_Movie = collections.namedtuple("IMDB_Movie", "ID, name, year, plot", verbose=False)

streamInfo = collections.namedtuple("streamInfo", "id, lang, type, info, unsupported", verbose=False)

def unicodeToString(text):
    if type(text) != str:
        return str(unicodedata.normalize("NFKD", text).encode('ascii','ignore'))
    else:
        return text

def checkPath(value):
    value = unicodeToString(value)
    badLetters = ":*?\"<>|,"
    if os.sep == "/":
        badLetters += "\\"
    if os.sep == "\\":
        badLetters += "/"
    for c in badLetters :
        value = value.replace(c,'_')
    return value

def checkFileName(value):
    value = unicodeToString(value)
    badLetters = ":*?\"<>|,\\/"
    for c in badLetters :
        value = value.replace(c,'_')
    return value

def convertVideo(originalVideo, outputFile, tempFolder, subCommand = False, keepMetaData = True, mainSettings = "-profile main -level 3.1", debug = False, dts = False):
    error = False
    from random import randint
    tempFile = os.path.join(tempFolder, str(randint(0,5000)) + ".mp4")
    if not os.path.exists(tempFolder):
        try:
            os.makedirs(tempFolder)
        except:
            error = True
            print("Error in creatings temp folder. Please check permissions and try again.")
    if not error:
        print("Converting " + originalVideo + " in temp folder...\n")
        command = "ffmpeg -i \"" + originalVideo + "\" " + mainSettings + ' '
        if subCommand:
            command += subCommand
        if not keepMetaData:
            command += "-map_metadata -1 "
        if dts:
            command += "-acodec aac -strict -2 "
        command += "\"" + tempFile + "\""
        if debug:
            raw_input(command)
        command = shlex.split(command)
        ffmpeg = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        converting = False
        duration = "Unknown"
        location = -1
        while ffmpeg.poll() == None:
            line = ''
            while True:
                letter = ffmpeg.stderr.read(1)
                if letter == '\n' or letter == '\r' or letter == '':
                    break
                else:
                    line += letter

            ## Get length of video
            if "Duration:" in line:
                duration = re.search("\d\d:\d\d:\d\d\.\d\d", line)
                if duration:
                    print('Duration: ' + duration.group(0))

            ## Check if ffmpeg is converting
            if line.startswith("frame="):
                if debug:
                    print(line, end='')
                    print('\b' * len(line), end='')
                else:
                    status = " Current: " + re.search("\d\d:\d\d:\d\d\.\d{1,2}", line).group(0)
                    print(status + '\b' * len(status), end='')
            elif debug:
                print(line)
        exitCode = ffmpeg.returncode
        if debug:
            print(exitCode)
        if exitCode != 0:
            error = True
            print('Error converting, ffmpeg did mot close correctly. Please try again.')
            try:
                os.remove(tempFile)
            except:
                pass
        else:
            print("Done.")

        if not error:
            if debug:
                print("Moving temp file to final destination:")
                print(tempFile)
                print(outputFile)
            try:
                shutil.move(tempFile, outputFile)
                return True
            except:
                error = True
                print("Failed to move temp file to final destination. Check folder/file permissions.")
        else:
            return False
    else:
        return False

def getOnlineData(URL, regEx = False):
    try:
        data = urllib.urlopen(URL).read()
    except:
        print('Error retriving online information about this show. Please check internet connection to the TvDB.')
        return False
    if regEx:
        result = re.search(regEx, data)
        if result:
            return result.groups()
        return False
    else:
        return data

def imdbMovieInfo(movieID):
    URL = "http://www.imdb.com/title/tt" + movieID + "/"
    try:
        data = urllib.urlopen(URL).read()
    except:
        print('Error retriving online information about this show. Please check internet connection to the TvDB.')
        return False

    data = data.replace("\n", "").replace("\r", "")

    sectionStart = data.find("<h1 class=\"header\">")
    sectionEnd = data.find("</h1>", sectionStart)

    basicInfo = data[sectionStart:sectionEnd]
    basicInfo = basicInfo.split(' ')
    basicInfo = ' '.join(basicInfo)

    try:
        name = re.search("<span class=\"itemprop\" itemprop=\"name\">(.+?)</span>", basicInfo).group(1)
    except:
        return False
    try:
        year = re.search(">(\d\d\d\d)<", basicInfo).group(1)
    except:
        year = ''

    descriptionIndicator = "<p itemprop=\"description\">"
    sectionStart = data.find(descriptionIndicator)
    sectionEnd = data.find("</p>", sectionStart)
    description = data[sectionStart+len(descriptionIndicator):sectionEnd]
    if '<' in description:
        while True:
            start = 0
            end = len(description)-1
            start = description.find('<')
            if start == -1:
                break
            end = description.find('>', start)
            description = description.replace(description[start:end+1], '')
    description = description.replace("&nbsp;", "").replace("&raquo;", "").replace("See full summary", '')

    description = description.strip()

    return IMDB_Movie(movieID, name, year, description)

def imdbSearch(title):
    URL = "http://www.imdb.com/find?q=" + title +"&s=tt"
    #print(URL)
    try:
        data = urllib.urlopen(URL).read()
        data = data.replace("\n", "")
    except:
        print('Error retriving online information about this show. Please check internet connection to the TvDB.')
        return False

    if "No results found for "+title in data:
        print('No results from search. Please try again.')
        return False
    results = ''
    if data:
        searchRegEx = '<td class="result_text">\ <a href=\"/title/tt(\d+?)/.+?\"\ >(.+?)</a>\ (.*?)<'
        results = re.findall(searchRegEx, data)
        if results:
            print("Search results retrived...")
    else:
        return False

    exclude = [ '(in development)', 'tv', 'episode']
    if results:
        index = 0
        end = 10
        searchResults = []
        while True:
            keep = True
            for offset in range(0,len(exclude)):
                if exclude[offset].lower() in results[index][2].lower():
                    keep = False
            if keep:
                year = re.search("\((\d\d\d\d)\)", results[index][2])
                if year:
                    searchResults.append(IMDB_Search(results[index][0], results[index][1], year.group(1), results[index][2].replace('(' + year.group(1) + ')', '')))
                else:
                    searchResults.append(IMDB_Search(results[index][0], results[index][1], '', results[index][2]))
            if len(searchResults) == 10:
                break
            elif index == len(results)-1:
                break
            index += 1
        if len(searchResults) > 0:
            return searchResults
        else:
            return False