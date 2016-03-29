import sys
import os
from shared import *
from videoClass import *
from movieClasses import movie
from tvShowClasses import tvShow
            
class MediaManager:
    def failed(self):
        return self.config['failedConverts']
    
    def collectionBuilder(self, data, basePath):
        for index in xrange(len(data)):
            data[index] = data[index].replace(basePath, os.sep)
            
        data.sort(reverse=True)
        
        if self.config['debug']:
            print(data)

        folderSets = []
        
        for line in data:
            videoFile = [ line[ line.rfind(os.sep)+1 : ]]
            directory = line[ 1 : line.rfind(os.sep) ]
            singleSet = [ directory, videoFile]
            folderSets.append(singleSet)
        
        if self.config['debug']:
            print(folderSets)
        
        collectedSets = []
        while len(folderSets) > 0:
            tempSet = folderSets[-1]
            folderSets.pop(-1)
            if tempSet[0] != '':
                for index in range(len(folderSets)-1, -1, -1):
                    if folderSets[index][0] == tempSet[0]:
                        tempSet[1].append(folderSets[index][1][0])
                        folderSets.pop(index)
                collectedSets.append(tempSet)
            else:
                for index in range(len(folderSets)-1, -1, -1):
                    match = SM(None, tempSet[1][0], folderSets[index][1][0]).ratio()
                    if self.config['debug']:
                        print([tempSet[0], tempSet[1][0], folderSets[index][1][0], match])
                    if folderSets[index][0] == tempSet[0] and match >= 0.80:
                        tempSet[1].append(folderSets[index][1][0])
                        folderSets.pop(index)
                collectedSets.append(tempSet)
        
        if self.config['debug']:
            print(collectedSets)
        
        index = 0
        while index < len(collectedSets):
            commonPrefix = os.path.commonprefix(collectedSets[index][1])
            if self.config['debug']:
                print commonPrefix
            if commonPrefix == '':
                tempSet = [ collectedSets[index][0], [] ]
                testChar = collectedSets[index][1][0][0]
                for index2 in range(len(collectedSets[index][1])-1, 0, -1):
                    if collectedSets[index][1][index2][0] != testChar:
                        tempSet[1].append(collectedSets[index][1][index2])
                        collectedSets[index][1].pop(index2)
                collectedSets.append(tempSet)
            index += 1
            
        collectedSets.sort()
        return collectedSets
        
    def isVideo(self, fileName):
        fileName = fileName.lower()
        for ext in self.config['acceptedVideoExtensions']:
            if fileName.endswith(ext.lower()):
                return True
        return False
        
    def parseFilesToConvert(self):
        masterQueue = [ [], [], [], [] ]
        
        if len(self.config['movies']) > 0:
            for video in self.config['movies']:
                masterQueue[video.convserionLevel()].append(video)
                    
        if len(self.config['tvShows']) > 0:
            for show in self.config['tvShows']:
                queue = show.buildQueue()
                for index in xrange(4):
                    for slot in xrange(len(queue[index])):
                        masterQueue[index].append(queue[index][slot])
                        
        if self.config['debug']:
            print(masterQueue[0])
            print(masterQueue[1])
            print(masterQueue[2])
            print(masterQueue[3])
            
        for level in masterQueue:
            for video in level:
                video.convertFile()
                if self.config['debug']:
                    print(video.hasError())
                if video.hasError():
                    self.config['failedConverts'].append(video.origFile())
        
    def parseFilesToCheck(self):
        self.rawTvShows = self.collectionBuilder(self.rawTvShows, self.config['watchedFolder'])
            
        for index in xrange(len(self.rawTvShows)):
            if self.config['debug']:
                print self.rawTvShows[index][0]
                print self.rawTvShows[index][1]
            self.config['tvShows'].append(self.config['tvShowHandler'](config, self.rawTvShows[index][0], self.rawTvShows[index][1]))
            
        for index in xrange(len(self.rawMovies)):
            folder = self.rawMovies[index][:self.rawMovies[index].rfind(os.sep)]
            inFile = self.rawMovies[index][self.rawMovies[index].rfind(os.sep)+1:]
            self.config['movies'].append(self.config['movieHandler'](config, folder, inFile))
        
    def getFilesToCheck(self):
        self.filesToCheck = []
        print("Searching folder: " + self.config['watchedFolder'])
        walker = os.walk(self.config['watchedFolder'])
        for path in walker:
            if ".@__thumb" not in path[0]:
                if "@Recycle" not in path[0]:
                    print("Parsing: " + path[0])
                    for fileName in path[2]:
                        error = False
                        if self.isVideo(fileName):
                            print("  Checking: " + fileName)
                            for term in self.config['excludedTerms']:
                                if (term.lower() in fileName.lower()):
                                    print("    Current file includes an exclusion term, skipping this file.")
                                    error = True
                                elif (term.lower() in path[0].lower()):
                                    print("    Current path includes an exclusion term, skipping this file.")
                                    error = True
                                    
                            fileSize = os.path.getsize(path[0]+os.sep+fileName)
                            if fileSize < self.config['minFileSize']:
                                print("    File to small, skipping this file.")
                                error = True
                            if not error:
                                found = False
                                for expression in self.config['episodeRegEx']:
                                    if re.search(expression, ' '+fileName.lower()+' '):
                                        curFile = os.path.join(path[0], fileName)
                                        if self.config['debug']:
                                            print(curFile)
                                            print(self.config['failedConverts'])
                                        if curFile not in self.config['failedConverts']:
                                            self.rawTvShows.append(curFile)
                                            print("    Added: " + fileName + " to TV Shows Queue.")
                                        else:
                                            print("    File was tried before and failed, skipping.")
                                        found = True
                                if not found:
                                    while True:
                                        if self.config['auto']:
                                            choice = '1'
                                        else:
                                            print(fileName + " could not be identified, please select one bellow:")
                                            print("1 - Movie")
                                            print("2 - TV Show")
                                            print("3 - Skip")
                                            print("4 - Delete")
                                            choice = raw_input("Choice: ")
                                        if choice.isdigit():
                                            choice = int(choice)
                                            if choice == 1:
                                                self.rawMovies.append(os.path.join(path[0], fileName))
                                                print("    Added: " + fileName + " to Movies Queue.")
                                                # return True
                                                break
                                            elif choice == 2:
                                                self.rawTvShows.append(os.path.join(path[0], fileName))
                                                print("    Added: " + fileName + " to TV Shows Queue.")
                                                break
                                            elif choice == 3:
                                                print("    Skipping...")
                                                break
                                            elif choice == 4:
                                                print("    Deleteing...")
                                                try:
                                                    os.remove(path[0] + os.sep + fileName)
                                                except:
                                                    print("      Could not delete " + fileName + ", please check permissions.")
                                                break
                                            else:
                                                print("    Invalid input. Please try again.")
                                        else:
                                            print("    Invalid input, number only. Please try again.")
                
    def __init__(self, config):
        self.config = config
        self.config['tvShowHandler'] = tvShow
        self.config['movieHandler'] = movie
        try:
            self.config['historyLog'] = open("history.log", 'a')
        except:
            print("Could not open history file. Please check folder permissions.")
            
        try:
            self.config['errorLog'] = open("error.log", 'a')
        except:
            print("Could not open error log file. Please check folder permissions.")

        for extension in self.config['acceptedVideoExtensions']:
            self.config['commonTerms'].append(extension[1:])
        
        self.config['movies'] = []
        self.config['tvShows'] = []
        
        self.rawMovies = []
        self.rawTvShows = []

        if os.path.isdir(self.config['watchedFolder']):
            self.config['tvdbHandler'] = Tvdb(apikey = self.config['tvdbAPIkey'])
            self.getFilesToCheck()
            self.parseFilesToCheck()
            self.parseFilesToConvert()

if __name__ == "__main__":
    
    ## Config
    config = {
        'moviesFolder': "/share/Multimedia/Movies/",
        'tvShowsFolder': "/share/Multimedia/TV Shows/",
        'animeShowFolder': "/share/Multimedia/Anime/",
        'watchedFolder': "/share/Download/",
        'tempFolder': "/share/Public/",
        'autoDelete': True,
        'acceptedVideoExtensions': [
                ".mp4",
                ".m4v",
                ".avi",
                ".mkv",
                ".mov" 
                ],
        'commonTerms': [
                "HDTV",
                "720p",
                "720",
                "1080p",
                "x264",
                "TS",
                "XviD",
                "DVDRip",
                "BrRip",
                "BluRay",
                "H264",
                "AAC",
                "HQ",
                "subs",
                "REPACK",
                "HDRip",
                "1280x720",
                "dvd",
                "episode",
                "ep",
                "dvdscr"
            ],
        'excludedTerms': [
                "@Recycle",
                "sample"
            ],
        'subtitleExtensions': [
                ".srt",
                ".ass"
            ],
        ## Regex expressions will be tested against a lowercase file name (The Beginning s01E23.mp4 -> the beginning s01e23.mp4)
        'episodeRegEx': [ "([\ \.\_\-]s(\d{1,3})e(\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]s(\d{1,3})[\ \.\_\-]e(\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]s(\d{1,3})e(\d{1,3})v\d[\ \.\_\-])",
                                "([\ \.\_\-](\d{3})[\ \.\_\-])",
                                "([\ \.\_\-](\d{3})v\d[\ \.\_\-])",
                                "([\ \.\_\-](\d{1,3})x(\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]s(\d{1,3})[\.\ \_]-[\.\ \_](\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]-[\.\ \_](\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]-[\.\ \_](\d{1,3})v\d[\ \.\_\-])",
                                "([\ \.\_\-]ep[\.\ \_](\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]ep[\.\ \_](\d{1,3})v\d[\ \.\_\-])",
                                "([\ \.\_\-]e(\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]ova[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]ova[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])",
                                "([\ \.\_\-]season[\ \.\_\-](\d{1,3})[\ \.\_\-]{1,3}episode[\ \.\_\-](\d{1,3}))",
                                "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])",
                                "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                                "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])"
                                
                            ],
        'tvdbAPIkey': "4E7A4FBBC8CF4D74",
        'cachedTvShows': [ 'Castle (2009)', 'Reign (2013)', 'The Librarians (2014)'],
        'acceptableSubtitleTypes': [
                "subrip",
                "srt",
                "ass",
                "mov_text"
            ],
        'acceptableVideoTypes': [
                "h264",
                "mpeg4"
            ],
        'minFileSize': 75000000,
        'checkForSubs': True,
        'auto': False,
        'service': False,
        'debug': False,
        'mode': 3, # 3 = All, 2 = Audio/Sub, 1 = Sub, 0 = No conversions
        'failedConverts': [],
        'cpuLimit': True,
    }
    sleepBetweenChecks = 30*60 ## 60 seconds * 30 minutes
    print("Media Manager v1.0")
    if len(sys.argv) > 1:
        if sys.argv[1] == '-a':
            config['auto'] = True
        elif sys.argv[1] == '-s':
            config['service'] = True
            config['auto'] = True
        elif sys.argv[1] == '-d':
            config['debug'] = True
        elif sys.argv[1] == '-ad':
            config['debug'] = True
            config['auto'] = True
        elif sys.argv[1] == '-sd':
            config['debug'] = True
            config['service'] = True
            config['auto'] = True
        elif sys.argv[1] == '-q':
            config['auto'] = True
            config['mode'] = 2
        else:
            print("Accepted arguments:\n-a -> Auto Mode (only processes what is known)\n-s -> Serivce mode, intended to be run in the background and run auto mode on occasion.")
            exit(0)
    
    while True:
        root = MediaManager(config)
        if config['service']:
            if config['debug']:
                print(root.failed())
            config['failedConverts'] = root.failed()
            print(datetime.datetime.now())
            print("Sleeping...")
            sleep(sleepBetweenChecks)
        else:
            break

