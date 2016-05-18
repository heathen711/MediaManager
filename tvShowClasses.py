from shared import *
from videoClass import *

class tvEpisode(videoClass):
    def __init__(self, config, videoPath, videoFile, selectedTvShow, anime):
        print "\n\nProcessing: " + videoFile
        
        self.start(config, videoPath, videoFile)
        self.showInfo = selectedTvShow
        self.SeEp = [ 1, 1 ]
        self.anime = anime
        
        if 'ova' in self.videoFile.lower():
            self.ova = True
        else:
            self.ova = False
    
        self.showNumbers = []
        for expression in range(0, len(self.config['episodeRegEx'])):
            if self.config['debug']:
                print("Checking: " + self.config['episodeRegEx'][expression])
            result = re.search(self.config['episodeRegEx'][expression], ' ' + self.videoFile.lower() + ' ')
            if result:
                if self.config['debug']:
                    print(result.groups())
                for item in result.groups()[1:]:
                    if item.isdigit():
                        self.showNumbers.append(int(item))
                    else:
                        print("Error: regex groupings '()' should only be digits.")
                        self.error = True
                break
        if len(self.showNumbers) == 0:
            result = re.search("((\d\d)(\d\d))" , self.videoFile.lower() )
            if result:
                for item in result.groups()[1:]:
                    if item.isdigit():
                        self.showNumbers.append(int(item))
                    else:
                        print("Error: regex groupings '()' should only be digits.")
                        self.error = True
        if self.config['debug']:
            print("Got regex episode info.")
            print(self.showNumbers)
            print(self.error)
            
        if not self.error:
            self.seasonEpisodeFilter()
            if self.config['debug']:
                print("Finished episode filter.")
        
        if not self.error:
            self.getConfirmation(True) ##auto mode??
            if self.config['debug']:
                print("Got confirmation.")
                
        if not self.error:
            if self.manualOverRide:
                self.outputFileName = self.showInfo['SeriesName'] + " - S" + str(self.SeEp[0]).zfill(2) + "E" + str(self.SeEp[1]).zfill(2) + '.mp4'
            else:
                self.outputFileName = self.showInfo['SeriesName'] + " - S" + str(self.SeEp[0]).zfill(2) + "E" + str(self.SeEp[1]).zfill(2) + ' - ' + self.tvShowEpisodeInfo['EpisodeName'] + '.mp4'
    
            self.outputFileName = checkFileName(self.outputFileName)
            if self.anime:
                self.outputFile = self.config['animeShowFolder']
            else:
                self.outputFile = self.config['tvShowsFolder']
            self.outputFile += checkFileName(self.showInfo['SeriesName']) + os.sep + "Season " + str(self.SeEp[0]).zfill(2) + os.sep 
            self.destination = self.outputFile
            self.outputFile += self.outputFileName
            self.outputFile = checkPath(self.outputFile)
            
            self.videoTitle = self.outputFileName
            
    def printOut(self):
        if not self.error:
            return self.videoFile + " -> " + self.showInfo['SeriesName'] + " S" + str(self.SeEp[0]).zfill(2) + "E" + str(self.SeEp[1]).zfill(2)
        else:
            return self.videoFile + " -> Error"
            
    def summary(self):
        if self.manualOverRide:
            self.error = False
            print(self.showInfo['SeriesName'] + " Season " + str(self.SeEp[0]) + " Episode " + str(self.SeEp[1]))
            return "No description avaliable due to manual override."
        
        try:
            self.tvShowEpisodeInfo = self.showInfo[self.SeEp[0]][self.SeEp[1]]
        except:
            return False
            
        if not self.tvShowEpisodeInfo:
            if self.config['debug']:
                print "Error retringing show info."
            return False
        description = ""

        if self.config['debug']:
            print(self.showInfo.keys())

        if "SeriesName" in self.showInfo.showKeys():
            description += unicodeToString(self.showInfo["SeriesName"])
        if "FirstAired" in self.showInfo.showKeys():
            description += " - " + str(self.showInfo["FirstAired"]).split('-')[0]
        description += " - Season " + str(self.SeEp[0]).zfill(2) + " Episode " + str(self.SeEp[1]).zfill(2)
        if "Network" in self.showInfo.keys():
            description += " - " + str(self.showInfo["Network"])
        if "Overview" in self.tvShowEpisodeInfo.keys():
            try:
                description += " - " + unicodeToString(self.tvShowEpisodeInfo["Overview"])
            except:
                description += " - No overview listed."

        return description
        
    def setSeason(self, newSeason = False):
        self.manualOverRide = False
        exit = False
        while True:
            if exit:
                break
            if newSeason and self.config['auto']:
                choice = str(newSeason)
            elif not newSeason and self.config['auto']:
                return False
            elif not newSeason:
                print("This show has " + str(len(self.seasonInfo)) + " seasons: 0 - " + str(len(self.seasonInfo)-1))
                choice = raw_input("Enter in new season number: (Previous = " + str(self.SeEp[0]) + "): ")
            else:
                choice = str(newSeason)
            if len(choice) > 0:
                if choice.isdigit():
                    choice = int(choice)
                    if choice >= 0 and choice < len(self.seasonInfo):
                        self.SeEp[0] = choice
                        break
                    elif choice >= len(self.seasonInfo):
                        done = False
                        while True:
                            if newSeason:
                                confirm = 'y'
                            else:
                                confirm = raw_input(str(choice) + " is greater then the series has, do you wish to allow this anyway? (Y/N): ")
                            if confirm.lower() == 'y':
                                self.manualOverRide = True
                                self.SeEp[0] = choice
                                done = True
                                break
                            elif confirm.lower() == 'n':
                                exit = True
                                break
                            else:
                                print("Invalid input. Please try again.")
                        if done:
                            break
                    else:
                        print("Invalid season number, there are only " + str(len(self.seasonInfo)) + " seasons listed.")
                else:
                    print("Invalid input. Please try again.")
            else:
                while True:
                    if self.SeEp[0] >= len(self.seasonInfo):
                        done = False
                        while True:
                            confirm = raw_input(str(self.SeEp[0]) + " is greater then the series has, do you wish to allow this anyway? (Y/N): ")
                            if confirm.lower() == 'y':
                                self.manualOverRide = True
                                done = True
                                break
                            elif confirm.lower() == 'n':
                                break
                            else:
                                print("Invalid input. Please try again.")
                        if done == True:
                            break
                    else:
                        break
                break
        
    def setEpisode(self, newEpisode = False):
        exit = False
        while True:
            if exit:
                break
            if not self.manualOverRide:
                if newEpisode and self.config['auto']:
                    choice = str(newEpisode)
                elif not newEpisode and self.config['auto']:
                    return False
                elif not newEpisode:
                    print("Season " + str(self.SeEp[0]) + " contains " + str(self.seasonInfo[self.SeEp[0]]) + " episodes.")
                    choice = raw_input("Enter in new episode number: (Previous = " + str(self.SeEp[1]) + "): ")
                else:
                    choice = str(newEpisode)
                if len(choice) > 0:
                    if choice.isdigit():
                        choice = int(choice)
                        if choice >= 0 and choice <= self.seasonInfo[self.SeEp[0]]:
                            self.SeEp[1] = choice
                            break
                        elif choice > self.seasonInfo[self.SeEp[0]]:
                            done = False
                            while True:
                                if newEpisode:
                                    confirm = 'y'
                                else:
                                    confirm = raw_input(str(choice) + " is greater then the season has, do you wish to allow this anyway? (Y/N): ")
                                if confirm.lower() == 'y':
                                    self.manualOverRide = True
                                    self.SeEp[1] = choice
                                    done = True
                                    break
                                elif confirm.lower() == 'n':
                                    exit = True
                                    break
                                else:
                                    print("Invalid input. Please try again.")
                            if done:
                                break
                        else:
                            print("Invalid season number, there are only " + str(self.seasonInfo[self.SeEp[0]][-1]) + " episodes listed.")
                    else:
                        print("Invalid input. Please try again.")
                else:
                    break
            else:
                choice = raw_input("Enter in new episode number: (Previous = " + str(self.SeEp[1]) + "): ")
                if len(choice) > 0:
                    if choice.isdigit():
                        self.SeEp[1] = int(choice)
                        break
                    else:
                        print("Invalid input. Please try again.")
                else:
                    break
                
    def askForSeEp(self):
        self.manualOverRide = False
        self.setSeason()
        self.setEpisode()

    def getConfirmation(self, assume = False):
        while True:
            summary = self.summary()
            if summary == False:
                if self.config['auto'] == False:
                    self.askForSeEp()
                else:
                    self.error = True
                    return False
            else:
                if not self.config['auto']:
                    print(summary)
                if assume:
                    return False
                if not self.config['auto']:
                    print("1 - Use this information.")
                    print("2 - Change season and episode information")
                    done = raw_input("Choice: ")
                    if done.isdigit():
                        done = int(done)
                        if done == 1:
                            return False
                        elif done == 2:
                            self.askForSeEp()
                        else:
                            print("Invalid choice. Please Try again.")
                    else:
                        print("Invalid input. Please try again.")
                else:
                    return False
        return False

    def seasonEpisodeFilter(self):
        done = False
        print("\nProcessing season/episode info: " + self.videoFile)
        if self.error:
            return False
        self.seasonInfo = []
        bottomSeason = self.showInfo.keys()[0]
        topSeason = self.showInfo.keys()[-1]
        if bottomSeason != 0:
            for filler in range(0, bottomSeason):
                self.seasonInfo.append(0)
        for entry in range(bottomSeason, topSeason+1):
            self.seasonInfo.append(self.showInfo[entry].keys()[-1])

        self.SeEp = [ '', '' ]
        slot = -1
        seasonWasInPath = False

        if len(self.showNumbers) > 0 and self.ova:
            self.SeEp[0] = 0
            self.SeEp[1] = self.showNumbers[0]
        elif len(self.showNumbers) > 0:
            if len(self.showNumbers) == 2:
                self.SeEp[0] = self.showNumbers[0]
                self.SeEp[1] = self.showNumbers[1]
            elif len(self.showNumbers) == 1:
                found = False
                topEpisode = 0
                for season in self.seasonInfo:
                    topEpisode += int(season)
                
                if self.showNumbers[0] > 0 and self.showNumbers[0] < 100:
                    ## check folder path for season number
                    ## Remove excess puncuation
                    punctuation = string.punctuation.replace('(','').replace(')','')
                    for char in range(0,len(punctuation)):
                        if punctuation[char] in self.videoPath:
                            self.videoPath = self.videoPath.replace(punctuation[char], "")
        
                    filePathFilters = [ "([\.\ \_\-]*?s(\d{1,3})[\.\ \_\-\/]*?)",
                                        "([\.\ \_\-]*?season[\.\ \_\-](\d{1,3})[\.\ \_\-\/]*?)" ]
                    for phrase in filePathFilters:
                        seasonInPath = re.search(phrase, self.videoPath.lower())
                        if seasonInPath:
                            result = seasonInPath.groups()
                            self.SeEp[0] = int(result[1])
                            seasonWasInPath = True
                            print("Found season in path: " + str(self.SeEp[0]))
                            
                    if seasonWasInPath:
                        if self.config['debug']:
                            print('Checking with found season from path...')
                            print('Using episode: ' + str(self.showNumbers[0]))
                        self.SeEp[1] = self.showNumbers[0]
                        found = self.summary()
                        if found != False:
                            done = True
                    else:
                        found = False
                if not done:
                    processAsFullCount = False
                    if seasonWasInPath and self.SeEp[0] <= topSeason:
                        seasonTopEpisode = self.showInfo[self.SeEp[0]].keys()[-1]
                        if int(self.showNumbers[0]) > seasonTopEpisode:
                            processAsFullCount = True
                    if (self.showNumbers[0] > topEpisode) and processAsFullCount != True:
                        if len(str(self.showNumbers[0])) == 3:
                            self.SeEp[0] = int(str(self.showNumbers[0])[0])
                            self.SeEp[1] = int(str(self.showNumbers[0])[1:])
                        else:
                            self.SeEp[0] = 1
                            self.SeEp[1] = self.showNumbers[0]
                        found = self.summary()
                        if found != False:
                            found = True
                            
                    else:
                        ## assume the number is a full sequencial count not season and Episode
                        error = False
                        tempNumber = int(self.showNumbers[0])
                        topSeason = len(self.seasonInfo)
                        curSeason = 1 ## skip ova / specials in season 0
                        while True:
                            try:
                                self.seasonInfo[curSeason]
                            except:
                                print("WARNING: Seqential number goes beyond season and episode count for: " + self.videoFile)
                                error = True
                                break
                            if not error:
                                if tempNumber <= self.seasonInfo[curSeason] and curSeason <= topSeason:
                                    self.SeEp[0] = curSeason
                                    self.SeEp[1] = tempNumber
                                    break
                                elif self.showNumbers > self.seasonInfo[curSeason] and curSeason <= topSeason:
                                    tempNumber -= self.seasonInfo[curSeason]-1
                                    curSeason += 1
                        if error and not self.config['auto']:
                            self.askForSeEp()
        else:
            self.askForSeEp()
                    
class tvShow:
    def getShowConfirmation(self, assume = False):
        if assume and self.config['auto']:
            summary = self.summary()
            print("Found a match.")
            if not self.config['auto']:
                print(summary)
            self.selectedTvShow = self.showEpisodeInfo
            return True
        else:
            while True:
                summary = self.summary()
                print('\n' + self.episode)
                print("Looking up " + self.showInfo['SeriesName'] + " information... ")
                print("Displaying Pilot episode for confirmation: ")
                print(summary)
                print("1 - Use this TV Show.")
                print("2 - Back")
                done = raw_input("Choice: ")
                if done.isdigit():
                    done = int(done)
                    if done == 1:
                        self.selectedTvShow = self.config['tvdbHandler'].getShowInfo(self.showInfo['seriesid'])
                        return True
                    elif done == 2:
                        return False
                    else:
                        print("Invalid choice. Please Try again.")
                else:
                    print("Invalid input. Please try again.")
        return False
        
    def summary(self):
        if self.manualOverride:
            self.error = False
            print(self.showInfo['SeriesName'] + " Season " + str(self.SeEp[0]) + " Episode " + str(self.SeEp[1]))
            return "No description avaliable due to manual override."
        if self.config['debug']:
            print self.showInfo['SeriesName']
            print self.SeEp
        
        if self.showInfo:
            self.showEpisodeInfo = self.config['tvdbHandler'].getShowInfo(self.showInfo['seriesid'])
            if self.showEpisodeInfo:
                self.tvShowEpisodeInfo = self.showEpisodeInfo[self.SeEp[0]][self.SeEp[1]]
            else:
                return False
        else:
            return False
            
        if not self.tvShowEpisodeInfo:
            if self.config['debug']:
                print "Error retringing show info."
            return False
        description = ""

        if "SeriesName" in self.showInfo.keys():
            description += self.showInfo["SeriesName"]
        if "FirstAired" in self.showInfo.keys():
            description += " - " + str(self.showInfo["FirstAired"]).split('-')[0]
        description += " - Season " + str(self.SeEp[0]).zfill(2) + " Episode " + str(self.SeEp[1]).zfill(2)
        if "Network" in self.showInfo.keys():
            description += " - " + str(self.showInfo["Network"])
        
        if "Overview" in self.tvShowEpisodeInfo.keys():
            try:
                description += " - " + self.tvShowEpisodeInfo["Overview"]
            except:
                description += " - No overview listed."
        return description
        
    def lookup(self):
        if not self.error:
            ## Check deduced title against previous cached show results.
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
                if len(results) > 0:
                    firstTitle = results[0]["SeriesName"]
                    
                    ## Necessary??
                    if firstTitle[0] == ' ':
                        firstTitle = firstTitle[1:]
                    if firstTitle[-1] == ' ':
                        firstTitle = firstTitle[:-1]
                    ## END
                        
                    ## TVdb disallows some tv broadcasted shows that no not count as tv series.
                    if firstTitle == '** 403: Series Not Permitted **':
                        if not self.config['auto']:
                            while True:
                                print("Error, this file may be a TV Show but is not allowed on TVDB.")
                                print("May need to try this as a movie to use IMDb information.")
                                print("Would you like to try IMDb or skip?")
                                print("1 - Try IMDb")
                                print("2 - Skip")
                                choice = raw_input("Choice: ")
                                if len(choice) > 0:
                                    if choice.isdigit():
                                        choice = int(choice)
                                        if choice == 1:
                                            ## add in handler for error movies
                                            self.config['movies'].append(self.config['movieHandler'](self.config, self.folderPath, self.episode))
                                            self.error = True
                                            if self.config['debug']:
                                                print("Error, show is actually a movie and will not be processed as a show.")
                                            break
                                        elif choice == 2:
                                            self.error = True
                                            if self.config['debug']:
                                                print("Error, skipping this file.")
                                            break
                                        else:
                                            print("Invalid choice. Please try again.")
                                    else:
                                        print("Invalid input. Please try again.")
                                else:
                                    print("Invalid input. Please try again.")
                        else:
                            self.error = True
                            if self.config['debug']:
                                print("Error, auto mode does not handle mis-identified files. Skipping.")
                    else:
                        ## Filter first result and compare looking for a >90% match
                        punctuation = string.punctuation.replace('(','').replace(')','')
                        for char in range(0,len(punctuation)):
                            if punctuation[char] in firstTitle:
                                firstTitle = firstTitle.replace(punctuation[char], "")
                        checkOthers = True
                        if self.config['debug']:
                            print(self.tvShowTitle.lower())
                            print(firstTitle.lower())
                        match = SM(None, self.tvShowTitle.lower(), firstTitle.lower()).ratio()
                        print("First result has a " + "{0:.0f}%".format(match*100) + " match.")
                        if (match > .90) or (len(results) == 1):
                            self.showInfo = results[0]
                            found = self.getShowConfirmation(True)
                            if found:
                                if firstTitle not in self.config['cachedTvShows']:
                                    self.config['cachedTvShows'].append(firstTitle)
                                checkOthers = False
                            else:
                                self.showInfo = False
                        if checkOthers and not self.config['auto']:
                            ## Prompt user for a selection in manual mode as first did not match >90%
                            print("\n\nMake a selection for: " + self.episode)
                            print("From: " + self.folderPath)
                            while True:
                                slot = 0
                                for result in results:
                                    keys = result.keys()
                                    slot += 1
                                    display = str(slot).zfill(2) + " - "
                                    if "SeriesName" in keys:
                                        display += result["SeriesName"]
                                    else:
                                        print("Error, something went wrong in retrieving information from TVdb as we are missing title information.")
                                        self.error = True
                                    if "firstaired" in keys:
                                        display += " (" + str(result["firstaired"]) + ")"
                                    print(display)
                                if not self.error:
                                    highChoice = slot
                                    slot += 1
                                    print(str(slot).zfill(2) + " - New Search")
                                    slot += 1
                                    print(str(slot).zfill(2) + " - Actually a Movie")
                                    slot += 1
                                    print(str(slot).zfill(2) + " - Exit")
                                    choice = raw_input("Enter in number associated with tvShow for more info: ")
                                    if choice.isdigit():
                                        choice = int(choice)
                                        if choice > 0 and choice <= highChoice:
                                            choice -= 1
                                            self.showInfo = results[choice]
                                            found = self.getShowConfirmation()
                                            if found:
                                                if results[choice]['SeriesName'] not in self.config['cachedTvShows']:
                                                    self.config['cachedTvShows'].append(results[choice]['SeriesName'])
                                                    break
                                        elif choice == slot-2:
                                            while True:
                                                userInput = raw_input("Enter in title to search: ")
                                                if len(userInput) > 0:
                                                    self.tvShowTitle = userInput
                                                    self.lookup()
                                                    break
                                                else:
                                                    print("Invalid input. Please try again.")
                                            break
                                        elif choice == slot-1:
                                            self.error = True
                                            self.config['movies'].append(self.config['movieHandler'](self.config, self.videoPath, self.videoFile))
                                        elif choice == slot:
                                            self.error = True
                                            break
                                        else:
                                            print("Invalid choice. Please try again.")
                                    else:
                                        print("Invalid input. Please try again.")
                                else:
                                    break
                        elif checkOthers and self.config['auto']:
                            self.error = True
                            if self.config['debug']:
                                print("Error, auto mode and a >90% match was not made.")
            else:
                ## Step through remaining words and search online until we get some results.
                foundName = False
                tempTvShowTitle = self.tvShowTitle.lower().split()
                for index in range(len(tempTvShowTitle), 0, -1):
                    try:
                        results = self.config['tvdbHandler'].search(' '.join(tempTvShowTitle[:index]))
                    except:
                        print("Error communicating with the tvdb. Please check your connection or try again later.")
                        self.error = True
                    if results:
                        if len(results) > 0 :
                            self.tvShowTitle = ' '.join(tempTvShowTitle[:index])
                            foundName = True
                            break
                if not foundName:
                    print("\n\nEpisode: " + self.episode)
                    print("From: " + self.folderPath)
                    print("No results for " + self.tvShowTitle)
                    if self.config['auto']:
                        self.error = True
                        print("Unable to find a close match to title.")
                    else:
                        while True:
                            userInput = raw_input("Enter in title to search: ")
                            if len(userInput) > 0:
                                self.tvShowTitle = userInput
                                self.lookup()
                                break
                            else:
                                print("Invalid input. Please try again.")
                else:
                    self.lookup()

    def nameFilter(self):
        
        ## Add space buffers for regex searching
        self.tvShowTitle = ' ' + self.tvShowTitle + ' '

        ## User regex to remove the season and episode info from the file title.
        for expression in range(0, len(self.config['episodeRegEx'])):
            result = re.search(self.config['episodeRegEx'][expression], self.tvShowTitle)
            if result:
                self.tvShowTitle = self.tvShowTitle.replace(result.group(0), ' SeEp ')
                break

        if "ova" in self.tvShowTitle.lower():
            self.tvShowTitle = self.tvShowTitle.lower().replace('ova', '').replace(' seep ', ' SeEp ')

        # Filter out alternative space marks
        altSpace = [ '.', '_']
        for alt in altSpace:
            self.tvShowTitle = self.tvShowTitle.replace(alt, ' ')

        self.tvShowTitle = ' '.join(self.tvShowTitle.split())
        
        ## Remove uploader name from beginning
        if self.tvShowTitle[0] == '(':
            self.tvShowTitle = self.tvShowTitle[self.tvShowTitle.find(')')+1:]
            
        if self.tvShowTitle[0] == '[':
            self.tvShowTitle  = self.tvShowTitle[self.tvShowTitle.find(']')+1:]
            
        self.tvShowTitle = self.tvShowTitle.replace('(', "").replace(')', "")

        # Use common descprtion terms to find end of tvShow title

        stop = len(self.tvShowTitle)
        for term in self.config['commonTerms']:
            if ' ' + term.lower() + ' ' in ' ' + self.tvShowTitle + ' ':
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
                self.error = True
                print("Error in removing original path from file path for processing. Error in path/linking.")
            tempFolderPath = tempFolderPath.replace(os.sep, ' ')
            self.tvShowTitle = tempFolderPath
            self.checkingPath = True
            self.nameFilter()
                
        ## Handle odd leet speak, by capturing full words and replaceing as needed
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
        
        ## Remove excess puncuation
        punctuation = string.punctuation.replace('(','').replace(')','')
        for char in range(0,len(punctuation)):
            if punctuation[char] in self.tvShowTitle:
                self.tvShowTitle = self.tvShowTitle.replace(punctuation[char], "")
        
        if self.tvShowTitle[0] == ' ':
            self.tvShowTitle = self.tvShowTitle[1:]
        if self.tvShowTitle[-1] == ' ':
            self.tvShowTitle = self.tvShowTitle[:-1]
        
        
    def isAnime(self):
        genre = getOnlineData("http://thetvdb.com/api/" + self.config['tvdbAPIkey'] + "/series/" + str(self.showInfo['id']) + "/all/", "(<Genre>(.*?)</Genre>)")
        if genre:
            genre = genre[1].split('|')
            if 'Animation' in genre:
                self.anime = True
                print("Show is calisified as an Anime show.")
            else:
                self.anime = False
        else:
            self.anime = False
            
    def buildQueue(self):
        self.queues = [ [], [], [], [] ]
        if not self.error:
            for episode in self.episodes:
                self.queues[episode.convserionLevel()].append(episode)
        
        if self.config['debug']:
            print(self.queues[0])
            print(self.queues[1])
            print(self.queues[2])
            print(self.queues[3])
        
        return self.queues
            
    def __init__(self, config, folder, episodes):
        self.selectedTvShow = False
        self.checkingPath = False
        self.config = config
        self.error = False
        if type(episodes) != list:
            self.episodes = [ episodes ]
            self.episode = episodes
        else:
            self.episodes = episodes
            self.episode = episodes[0]
        self.folderPath = os.path.join(self.config['watchedFolder'], folder)
        if self.config['debug']:
            print(self.folderPath)
        self.manualOverride = False
        self.SeEp = [ 1, 1 ]
        self.showInfo = False
        self.anime = False
    
        print("\n\nProcessing: " + self.folderPath + episodes[0])
        
        self.tvShowTitle = episodes[0].lower()
        self.nameFilter()
        self.tvShowTitle = self.tvShowTitle.title()
        if self.config['debug']:
            print("Finished name filter.")
            print(self.error)
        
        if not self.error:
            self.lookup()
            if not self.error:
                print('Retriving additional online information...')
                self.isAnime()
            if self.config['debug']:
                print("Finished lookup.")
                print(self.error)
                
        if not self.error:
            for index in xrange(len(self.episodes)):
                self.episodes[index] = tvEpisode(self.config, self.folderPath, self.episodes[index], self.selectedTvShow, self.anime)
        if not self.error:
            if self.config['auto']:
                for index in xrange(len(self.episodes)):
                    print(str(index+1).zfill(2) + " - " + self.episodes[index].printOut())
            else:
                while True:
                    print("Search results: ")
                    for index in xrange(len(self.episodes)):
                        print(str(index+1).zfill(2) + " - " + self.episodes[index].printOut())
                    
                    print(str(len(self.episodes)+1).zfill(2) + " - Change whole season")
                    print(str(len(self.episodes)+2).zfill(2) + " - Continue")
                    choice = raw_input("Selection: ")
                    if len(choice) > 0:
                        if choice.isdigit():
                            choice = int(choice)-1
                            if choice >= 0 and choice < len(self.episodes):
                                self.episodes[choice].getConfirmation()
                            elif choice == len(self.episodes):
                                while True:
                                    bottomSeason = self.config['tvdbHandler'][self.selectedTvShow['SeriesName']].keys()[0]
                                    topSeason = self.config['tvdbHandler'][self.selectedTvShow['SeriesName']].keys()[-1]
                                    if bottomSeason == 0:
                                        count = topSeason + 1
                                    else:
                                        count = topSeason
                                    print("This show has " + str(count) + " seasons. " + str(bottomSeason) + " - " + str(topSeason))
                                    newSeason = raw_input("Enter in new season number: ")
                                    if len(newSeason) > 0:
                                        if newSeason.isdigit():
                                            newSeason = int(newSeason)
                                            if newSeason >= bottomSeason and newSeason <= topSeason:
                                                for index in xrange(len(self.episodes)):
                                                    self.episodes[index].setSeason(newSeason)
                                                break
                                            elif newSeason > topSeason:
                                                while True:
                                                    overRide = raw_input(str(newSeason) + " is greater then the show has, are you sure you wish to use " + str(newSeason) + "? (Y/N): ")
                                                    if len(overRide) == 1:
                                                        overRide = overRide.lower()
                                                        if overRide == 'y':
                                                            for index in xrange(len(self.episodes)):
                                                                self.episodes[index].setSeason(newSeason)
                                                            break
                                                        elif overRide == 'n':
                                                            break
                                                        else:
                                                            print("Invalid choice, please try again.")
                                                    else:
                                                        print("Invalid input, please try again.")
                                                break
                                            else:
                                                print("Invalid selection. Please try again.")
                                        else:
                                            print("Invalid input, please try again.")
                                    else:
                                        print("Invalid input, please try again.")
                            elif choice == len(self.episodes)+1:
                                break
                            else:
                                print("Invalid choice, please try again.")
                        else:
                            print("Invalid input, please try again.")
                    else:
                        print("Invalid input, please try again.")
