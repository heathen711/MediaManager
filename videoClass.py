from __future__ import print_function
from shared import *

class videoClass:
    def hasError(self):
        return self.error

    def origFile(self):
        return self.originalVideo

    def convertVideo(self):
        tempFile = os.path.join(self.config['tempFolder'], str(randint(0,5000)) + ".mp4")
        if not os.path.exists(self.config['tempFolder']):
            try:
                os.makedirs(self.config['tempFolder'])
            except:
                self.error = True
                print("Error in creatings temp folder. Please check permissions and try again.")
        if not self.error:
            print("Converting " + self.originalVideo + " in temp folder...\n")
            if self.forceConvert:
                print(self.originalVideo + " contains unsupported codecs and requires a force conversion.")
            self.command += "\"" + tempFile + "\""
            if self.config['debug']:
                raw_input(self.command)
            self.commandSplit = shlex.split(self.command)
            ffmpeg = subprocess.Popen(self.commandSplit, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
                    if self.config['debug']:
                        print(line, end='')
                        print('\b' * len(line), end='')
                    else:
                        status = " Current: " + re.search("\d\d:\d\d:\d\d\.\d*?", line).group(0)
                        print(status + '\b' * len(status), end='')
                elif self.config['debug']:
                    print(line)
            exitCode = ffmpeg.returncode
            if self.config['debug']:
                print(exitCode)
            if exitCode != 0:
                print('Error converting, ffmpeg did mot close correctly. Please try again.')
                self.config['errorLog'].write(self.originalVideo + " -> ffmpeg error code: " + str(exitCode) + "\n")
                self.config['errorLog'].write(self.command + "\n")
                try:
                    os.remove(tempFile)
                except:
                    pass
                return False
            else:
                print("\nDone.")

            if not self.error:
                if self.config['debug']:
                    print("Moving temp file to final destination:")
                    print(tempFile)
                    print(self.outputFile)
                try:
                    shutil.move(tempFile, self.outputFile)
                    self.config['historyLog'].write(self.originalVideo + " -> " + self.outputFile + '\n')
                    return True
                except:
                    self.error = True
                    print("Failed to move temp file to final destination. Check folder/file permissions.")
            else:
                return False
        else:
            return False

    def convertFile(self):
        if not self.error:
            print("\n\nConvert/Move: ")
            print(self.originalVideo)
            print(self.outputFile)
            print("Video Conversion: " + str(self.requiredConversion['video']))
            print("Audio Conversion: " + str(self.requiredConversion['audio']))
            print("Subtitle Conversion: " + str(self.requiredConversion['subtitle']))
        else:
            print("Errors when processing info for file, skipping: " + self.videoFile)

        if not self.error:
            ## Check if the videoFile already exsists
            if os.path.exists(self.outputFile):
                while True:
                    if self.config['auto']:
                        print(self.outputFile + " already exsists, skipping conversion.")
                        choice = 'n'
                    else:
                        choice = raw_input(self.videoTitle + " exsists, would you like to overwrite it? (Y/N): ")
                    if choice.lower() == 'y':
                        try:
                            os.remove(self.outputFile)
                            break
                        except:
                            print("Error in deleteing " + self.videoTitle + " you may not have permission to this path/file or the file is in use. Cannot continue.")
                            self.error = True
                            break
                    elif choice.lower() == 'n':
                        self.error = True
                        break
                    else:
                        print("Invalid input. Please try again.")

        if not self.error:
            ## Prepare for the folder path for the move
            if not os.path.exists(self.destination):
                try:
                    os.makedirs(self.destination)
                except:
                    print("Error creating destination for video. Please ensure you have permissions to: " + self.destination)
                    self.error = True

        if not self.error:
            ## Move subtitles and place it in the destination folder
            if self.subFile and not self.error:
                print("Moving subtitle file...")
                subOutputFile = self.outputFile[:self.outputFile.rfind('.')]+self.subFile[self.subFile.rfind('.'):]
                if self.config['debug']:
                    print(self.subFile)
                    print(subOutputFile)
                try:
                    shutil.move(self.subFile, subOutputFile)
                    print("Moved.")
                except:
                    print("Error moving subtitle file. Please check file/folder permissions.")
            if not self.error:
                print("Converting video file...")
                passed = self.convertVideo()
                if not passed and not self.error:
                    #print("Error performing quick convert, usually has to do with an improperly packed video, requires a full conversion to resolve. Attempting that now...")
                    #self.forceConvert = True
                    #self.buildCommand()
                    #passed = self.convertVideo()
                    #if not passed:
                    self.error = True
        if not self.error:
            ## Prompt if user wishes to remove original file as the converted file has been moved.
            while True:
                if self.config['debug']:
                    choice = 'n'
                elif not self.config['autoDelete']:
                    choice = raw_input("Delete orignal file: " + self.originalVideo + " (Y/N): ")
                elif self.config['autoDelete']:
                    choice = 'y'
                if choice.lower() == 'y':
                    try:
                        os.remove(self.originalVideo)
                        print("Deleted original file.")
                    except:
                        print("Failed to remove orignal file, please check permissions.")
                    break
                elif choice == 'n':
                    break
                else:
                    print("Invalid input. Please try again.")

    def streamMenu(self, streams, title):
        if len(streams) > 0:
            if len(streams) == 0:
                while True:
                    print("Video contains no " + title + " streams!")
                    if self.config['auto']:
                        choice = 'n'
                    else:
                        choice = raw_input("Continue (Y/N)? ")
                    if len(choice) == 1:
                        if choice.lower() == 'y':
                            return False
                            break
                        elif choice.lower() == 'n':
                            self.error = True
                            break
                    else:
                            print("Invalid selection, please try again.")
            elif len(streams) > 1 and not self.config['auto']:
                print("Found multiple options for " + title + ", please select one: ")
                while True:
                    for index in xrange(len(streams)):
                        print(str(index+1).zfill(2) + " - " + streams[index].lang + " - " + streams[index].info + " supported = " + str((not streams[index].unsupported)))
                    print( str(len(streams)+1).zfill(2) + " - None of the above.")
                    choice = raw_input("Choice: ")
                    if len(choice) > 0:
                        if choice.isdigit():
                            choice = int(choice)-1
                            if choice >= 0 and choice < len(streams):
                                return streams[choice]
                                break
                            elif choice == len(streams):
                                return False
                            else:
                                print("Invalid selection, please try again.")
                        else:
                            print("Invalid input, please try again.")
                    else:
                        print("Invalid input, please try again.")
            elif len(streams) == 1 and not streams[0].unsupported:
                print("Found a single " + title + " stream: " + streams[0].lang + " - " + streams[0].info)
                return streams[0]
            else:
                print("Error in processing " + title + " streams.")
                self.error = True
                return False
        else:
            print("Found no " + title + " steams.")
            return False

    def mapFileStreams(self):
        results = []

        streams = []
        ## ffprobe -analyzeduration 5000 %file$
        print("Gathering internal video info: " + self.originalVideo)
        self.command = "ffprobe -analyzeduration 5000 \"" + self.originalVideo + '"'
        self.command = shlex.split(self.command)
        ffprobe = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffprobe = ffprobe.communicate()[1].split('\n')
        for line in ffprobe:
            if "Unsupported codec with id " in line and not self.config['auto']:
                streamID = re.search("stream\ (\d+?)", line)
                if streamID:
                    streamID = streamID.group(1)
                    if streamID.isdigit():
                        streamID = int(streamID)
                        streams[streamID]._replace(unsupported=True)
            if "Stream" in line:
                if self.config['debug']:
                    print(line)
                                # Stream #0:2(eng): Subtitle: subrip (default)
                info = re.search("Stream\ \#(\d{1,2}\:\d{1,2})(.*?)\:\ (.+?)\:\ (.*)", line)
                if info:
                    if self.config['debug']:
                        print(info.groups())
                    unsupported = False
                    streams.append(streamInfo(info.group(1), info.group(2).replace('(', '').replace(')', ''), info.group(3), info.group(4), unsupported))

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

        for key in sortedStreams.keys():
            temp = self.streamMenu(sortedStreams[key], key)
            if not self.error:
                results.append(temp)
            else:
                break

        if not self.error:
            for index in range(len(results)-1, -1, -1):
                if results[index]:
                    if results[index].unsupported == True:
                        print(results[index].type + " - " + results[index].lang + " - " + results[index].id + " - " + results[index].info + " - uses an unsupported codec and cannot be converted. Please select a different stream if possible, or manually convert.")
                        self.error = True

        if not self.error:
            self.streams = dict(video=results[0], audio=results[1], subtitle=results[2])
            if self.config['debug']:
                print(streams)

            self.buildCommand()

            if self.forceConvert:
                self.level = 3
            elif self.requiredConversion['video']:
                self.level = 3
            elif self.requiredConversion['audio']:
                self.level = 2
            elif self.requiredConversion['subtitle']:
                self.level = 1
            else:
                self.level = 0
        else:
            self.level = -1

    def buildCommand(self):
        self.requiredConversion = dict( video=False, audio=False, subtitle=False )
        if self.config['cpuLimit']:
            self.command = "nice -n 8 "
        else:
            self.command = ""
        
        self.command += "ffmpeg -i \"" + self.originalVideo + "\" "

        if self.streams['video']:
            if self.config['debug']:
                print("Adding video...")
                print(self.streams['video'])

            self.command += "-map " + self.streams['video'].id + ' '

            if not self.forceConvert:
                resolution = re.search("\ (\d+?)x(\d+?)[\ \,]", self.streams['video'].info)
                if resolution:
                    width = int(resolution.group(1))
                    height = int(resolution.group(2))
                    if self.config['debug']:
                        print(str(width) + 'x' + str(height))
                        gcd = fractions.gcd(width, height)
                        if gcd:
                            print( str(width/gcd) + ':' + str(height/gcd) )
                        print("1208x720")

                    if width <= 1280 and height <= 720 and "h264" in self.streams['video'].info:
                        self.command += "-vcodec copy "
                    else:
                        self.command += "-profile:v main -level 3.1 "
                        self.requiredConversion['video'] = True

        if self.streams['audio']:
            if self.config['debug']:
                print("Adding audio...")
                print(self.streams['audio'])
            self.command += "-map " + self.streams['audio'].id + ' '
            if not self.forceConvert:
                if "aac" in self.streams['audio'].info:
                    self.command += "-acodec copy "
                else:
                    self.command += "-strict -2 -acodec aac "
                    self.requiredConversion['audio'] = True

        if self.forceConvert:
            self.command += "-profile main -level 3.1 "

        if self.streams['subtitle']:
            if self.config['debug']:
                print("Adding subtitle...")
                print(self.streams['subtitle'])
            self.command += "-map " + self.streams['subtitle'].id + ' '
            if "mov_text" in self.streams['subtitle'].info:
                self.command += "-scodec copy "
            else:
                self.command += "-scodec mov_text "
                self.requiredConversion['subtitle'] = True

        self.command += "-map_metadata -1 "

    def convserionLevel(self):
        if not self.error:
            return self.level
        else:
            return -1

    def checkForSubFiles(self):
        subFile = []
        beginning = self.videoFile
        beginning = beginning[:beginning.rfind('.')]
        if self.config['debug']:
            print(self.videoPath)
            print(self.config['watchedFolder'])
            print(self.videoPath != self.config['watchedFolder'])
            print(beginning)
        if self.videoPath != self.config['watchedFolder']:
            walker = os.walk(self.videoPath)
            for path in walker:
                for file in path[2]:
                    if file[file.rfind('.'):] in self.config['subtitleExtensions']:
                        if file != self.videoFile:
                            subFile.append(os.path.join(path[0], file))
        else:
            subFile = os.listdir(self.config['watchedFolder'])
            for item in range(len(subFile)-1, -1, -1):
                if not subFile[item].startswith(beginning) or subFile[item][subFile[item].rfind('.'):].lower() not in self.config['subtitleExtensions']:
                    subFile.pop(item)

        if len(subFile) > 0:
            subFile.sort()
            if self.config['debug']:
                print(subFile)
            if len(subFile) > 0:
                if len(subFile) > 1 and not self.config['auto']:
                    while True:
                        print("Multiple subtitle files found, please select which one you would like to use or to skip.")
                        for entry in range(0, len(subFile)):
                            print(str(entry+1).zfill(2) + ' - ' + subFile[entry])
                        print(str(len(subFile)+1).zfill(2) + ' - Do not use any.')
                        choice = raw_input("Choice: ")
                        if choice.isdigit():
                            choice = int(choice)-1
                            if choice in range(0, len(subFile)):
                                self.subFile = subFile[choice]
                                break
                            elif choice == len(subFile):
                                self.subFile = False
                                break
                            else:
                                print("Invalid choice. Please try again.")
                        else:
                            print("Invalid input. Please try again.")
                elif len(subFile) == 1 and not self.config['auto']:
                    subFile = subFile[0]
                    while True:
                        print("Found a subtitle file: " + subFile)
                        choice = raw_input("Would you like to use this subtitle file? (Y/N): ")
                        if len(choice) == 1:
                            if choice.lower() == 'y':
                                self.subFile = subFile
                                break
                            elif choice.lower() == 'n':
                                self.subFile = False
                                break
                            else:
                                print("Invalid choice. Please try again.")
                        else:
                            print("Invalid input. Please try again.")
                elif len(subFile) == 1 and self.config['auto']:
                    self.subFile = subFile[0]
                elif len(subFile) > 1 and self.config['auto']:
                    self.subFile = False
                    for sub in subFile:
                        if "eng" in sub.lower():
                            self.subFile = sub
                            break
                else:
                    self.subFile = False
            else:
                self.subFile = False
        else:
            self.subFile = False

        if self.config['debug']:
            print("Subtitle search result:")
            print("Subtitle File: " + str(self.subFile))

        if self.subFile:
            print("Got a external file subtitle: " + self.subFile)

    def start(self, config, videoPath, videoFile):
        print(videoFile)

        self.config = config
        self.videoPath = videoPath
        if self.videoPath[-1] != os.sep:
            self.videoPath = self.videoPath + os.sep
        self.videoFile = videoFile
        self.manualOverRide = False
        self.originalVideo = os.path.join(self.videoPath, self.videoFile)
        self.error = False
        self.forceConvert = False

        ## ffprobe video for info
        self.mapFileStreams()
        if self.config['mode']:
            if self.level > self.config['mode']:
                if self.config['debug']:
                    print("Conversion level is higher then mode, video will not be converted.")
                self.error = True
        self.checkForSubFiles()
