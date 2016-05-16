from shared import *
from videoClass import *

class movie(videoClass):
    def __init__(self, config, videoPath, videoFile):
        print("\n\nProcessing movie: " + videoFile)
        self.start(config, videoPath, videoFile)

        self.nameFilter()
        
        if not self.error:
            ## Use filtered name for online search and confirmation
            self.getOnlineInfo()
        else:
            if self.config['debug']:
                print("Error in name filter, not checking online.")

        if not self.error:
            ## Use confirmed movie info for destination and title
            if not self.manualOverRide:
                self.movieTitle = checkPath(self.movieInfo.name)
                if len(self.movieInfo.year) > 0:
                    self.movieTitle += ' (' + str(self.movieInfo.year) + ')'
            else:
                self.movieTitle = self.videoTitle
            self.movieTitle += ".mp4"
            self.movieTitle = unicodeToString(checkFileName(self.movieTitle))
            
            self.destination = os.path.join(checkPath(self.config['moviesFolder']), self.movieTitle[:self.movieTitle.rfind('.')])
            self.outputFile = os.path.join(self.destination, self.movieTitle)
        else:
            print("Error in online info, not moving the file.")
            
    def generateSummary(self):
        self.summary = ""
        
        if self.config['debug']:
            print(self.movieInfo)

        self.summary += self.movieInfo.name
        if len(self.movieInfo.year) > 0:
            self.summary += " - " + self.movieInfo.year
        if len(self.movieInfo.plot) > 0:
            self.summary += " - " + self.movieInfo.plot
        else:
            self.summary += " - No Plot listed."
            
    def clearShowInfo(self):
        ## Empty the parameters for new searching
        self.curMovie = None
        self.movieInfo = None
        self.summary = None
        self.destination = None

    def getConfirmation(self, curMovie, assume = False):
        ## Obtain movie summary and prompt user for confirmation to use the selected info
        self.curMovie = curMovie
        print("Retriving information from IMDb...")
        self.movieInfo = self.imdbMovieInfo(self.curMovie.ID)
        if self.movieInfo:
            self.generateSummary()
            print(self.summary)
            
            if assume and self.config['auto']:
                return True
            else:
                while True:
                    print("1 - Use this information.")
                    print("2 - Back")
                    done = raw_input("Choice: ")
                    if done.isdigit():
                        done = int(done)
                        if done == 1:
                            return True
                        elif done == 2:
                            self.clearShowInfo()
                            return False
                        else:
                            print("Invalid choice. Please Try again.")
                    else:
                        print("Invalid input. Please try again.")
        else:
            self.error = True
        
    def nameFilter(self):
        self.videoTitle = self.videoFile
        if self.config['debug']:
            print(self.videoTitle)
        ## Remove uploader name from beginning
        if self.videoTitle[0] == '(':
            self.videoTitle = self.videoTitle[self.videoTitle.find(')')+1:]
            if self.config['debug']:
                print(self.videoTitle)
        if self.videoTitle[0] == '[':
            self.videoTitle  = self.videoTitle[self.videoTitle.find(']')+1:]
            if self.config['debug']:
                print(self.videoTitle)

        ## Remove extra parentesies from around years or anything
        self.videoTitle = self.videoTitle.replace('(', "").replace(')', "")
        if self.config['debug']:
            print(self.videoTitle)

        # Filter out alternative space marks
        altSpace = [ '.', '_' ]
        for alt in altSpace:
            self.videoTitle = self.videoTitle.replace(alt, ' ')
        if self.config['debug']:
            print(self.videoTitle)
        
        # Use common descprtion terms to find end of movie title
        self.videoTitle = self.videoTitle.lower().split()
        if self.config['debug']:
            print(self.videoTitle)
            
        stop = len(self.videoTitle)
        for term in self.config['commonTerms']:
            if term.lower() in self.videoTitle:
                place = self.videoTitle.index(term.lower())
                if place < stop:
                    stop = place
                    
        self.videoTitle = ' '.join(self.videoTitle[:stop])
        if self.config['debug']:
            print(self.videoTitle)

        ## Add/restore parentesies around the year if it's left after filtering.
        year = re.search("\ \d\d\d\d\ ", self.videoTitle)
        try:
            self.videoTitle = self.videoTitle.replace(year.group(0), " (" + year.group(0)[1:-1] + ") ")
        except:
            pass
        
    def imdbMovieInfo(self, movieID):
        URL = "http://www.imdb.com/title/tt" + movieID + "/"
        if self.config['debug']:
            print(URL)
        try:
            data = urllib.urlopen(URL).read()
        except:
            print('Error retriving online information about this show. Please check internet connection to the TvDB.')
            return False
    
        data = data.replace("\n", "").replace("\r", "")
        
        #try:
        # <h1 itemprop="name" class="">UFC Fight Night: Silva vs. Bisping&nbsp;            </h1>
        search = re.search("<h1 itemprop=\"name\"(?:.*?)>([\s\w\W]*?)</h1>", data)
        if self.config['debug']:
            print(search.groups())
        if search:
            name = search.group(1)
            name = name.replace("&nbsp;", "").replace("&raquo;", "")
            name = name.strip()
            if '<' in name:
                name = name[:name.find('<')]
            if 'titleYear' in search.group(1):
                year = re.search(">(\d\d\d\d)<", search.group(1)).group(1)
            else:
                year = ''
        else:
            print("Error parsing IMDB information. Please check that IMDB is working.")
            return False
    
        descriptionIndicator = "<div class=\"summary_text\" itemprop=\"description\">"
        sectionStart = data.find(descriptionIndicator)
        sectionEnd = data.find("</div>", sectionStart)
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
    
    def imdbSearch(self, title):
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
    
        exclude = [ '(in development)' ]
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
                        videoTitle = results[index][1] + '(' + year.group(1) + ')'
                        match = SM(None, title.lower(), videoTitle.lower()).ratio()
                        searchResults.append(IMDB_Search(results[index][0], results[index][1], year.group(1), results[index][2].replace('(' + year.group(1) + ')', ''), match))
                    else:
                        videoTitle = results[index][1]
                        match = SM(None, title.lower(), videoTitle.lower()).ratio()
                        searchResults.append(IMDB_Search(results[index][0], results[index][1], '', results[index][2], match))
                if len(searchResults) == 10:
                    break
                elif index == len(results)-1:
                    break
                index += 1
                
            movieMatch = []
            otherMatch = []
            
            for index in xrange(len(searchResults)):
                if 'tv' not in searchResults[index].info:
                    movieMatch.append(searchResults[index])
                else:
                    otherMatch.append(searchResults[index])
                    
            movieMatch = sorted(movieMatch, key=lambda entry: entry.match, reverse=True)
            otherMatch = sorted(otherMatch, key=lambda entry: entry.match, reverse=True)
            
            searchResults = []
            for entry in movieMatch:
                searchResults.append(entry)
            for entry in otherMatch:
                searchResults.append(entry)
            
            if len(searchResults) > 0:
                if self.config['debug']:
                    print searchResults
                return searchResults
            else:
                return False
        else:
            return False
                
    def getOnlineInfo(self, ask=False):
        
        ## Prompt user for new title if needed
        if ask:
            while True:
                userInput = raw_input("Enter in title to search: ")
                if len(userInput) > 0:
                    self.videoTitle = userInput
                    break
                else:
                    print("Invalid input. Please try again.")
                    
        ## Use IMDB and perform a search for the deduced title or user input
        print("Looking up: " + self.videoTitle)
        found = False
        results = self.imdbSearch(self.videoTitle)
        if results:
            if len(results) > 0:
                firstTitle = unicodeToString(results[0].name)
                if len(results[0].year) > 0:
                    firstTitle += " (" + str(results[0].year) + ")"
                ## Compare the first search result to the title and see if we have at least a 90% match
                match = SM(None, firstTitle.lower(), self.videoTitle.lower()).ratio()
                if match > 0.90:
                    print("Found a " + "{0:.0f}%".format(match*100) + " match.")
                    found = self.getConfirmation(results[0], True)
                if not found and not self.config['auto']:
                    ## Since first did not match high enough, in manual mode we list search results and prompt for the user to select one or type in new search
                    while True:
                        print("Search Results for " + self.videoTitle + ":")
                        slot = 0
                        for result in results:
                            slot += 1
                            display = str(slot).zfill(2) + " - "
                            if result.name:
                                display += result.name
                            else:
                                print("Error, something went wrong in retrieving information from IMDB as we are missing title information.")
                                break
                            if len(result.year):
                                display += " (" + str(result.year) + ")"
                            print(display)
                        slot += 1
                        print(str(slot).zfill(2) + " - New search")
                        slot += 1
                        print(str(slot).zfill(2) + " - Manual Name")
                        slot += 1
                        print(str(slot).zfill(2) + " - Actually a TV Show")
                        slot += 1
                        print(str(slot).zfill(2) + " - Exit")
                        choice = raw_input("Enter in number associated with movie for more info: ")
                        if choice.isdigit():
                            choice = int(choice)
                            if choice > 0 and choice < slot-3:
                                choice -= 1
                                found = self.getConfirmation(results[choice])
                                if found:
                                    return True
                            elif choice == slot-3:
                                self.getOnlineInfo(True)
                                break
                            elif choice == slot-2:
                                self.manualOverRide = True
                                name = raw_input("Enter in new file name without file extension or blank to exit: ")
                                if len(name) > 0:
                                    self.videoTitle = name
                                break
                            elif choice == slot-1:
                                self.error = True
                                self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.videoPath, self.videoFile))
                            elif choice == slot:
                                self.error = True
                                break
                            else:
                                print("Invalid choice. Please try again.")
                        else:
                            print("Invalid input. Please try again.")
                elif not found and self.config['auto']:
                    self.error = True
            else:
                ## Step through the file name words and search after each step till we get some results
                print("Trying alternative titles...")
                foundName = False
                tempvideoTitle = self.videoTitle.lower().split()
                for index in range(len(tempvideoTitle), 0, -1):
                    results = self.imdbSearch(' '.join(tempvideoTitle[:index]))
                    if len(results) > 0:
                        self.videoTitle = ' '.join(tempvideoTitle[:index])
                        foundName = True
                        break
                if foundName:
                    self.getOnlineInfo()
                else:
                    print("No results for " + self.movie)
                    if self.config['auto']:
                        self.error = True
                        self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.videoPath, self.videoFile))
                    else:
                        self.getOnlineInfo(True)
        else:
            print("Search returned no results, please try again.")
            if self.config['auto']:
                self.error = True
                self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.videoPath, self.videoFile))
            else:
                self.getOnlineInfo(True)