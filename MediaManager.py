#!/usr/bin/env python
"""Central script for MediaManager"""

import collections
import datetime
import fractions
import os
import plistlib
import re
import shlex
import shutil
import string
import subprocess
import sys
import unicodedata
import urllib

from difflib import SequenceMatcher as SM
from random import randint
from time import sleep

from tvdb import TVDB
from url_functions import getOnlineContent

folderInfo = collections.namedtuple("folderInfo", "folderPath tvShows movies", verbose=False)

subtitle = collections.namedtuple("subtitle", "slot, lang, style, default", verbose=False)

IMDB_Search = collections.namedtuple("IMDB_Search", "ID, name, year, info, match", verbose=False)
IMDB_Movie = collections.namedtuple("IMDB_Movie", "ID, name, year, plot", verbose=False)

streamInfo = collections.namedtuple("streamInfo", "id, lang, type, info, unsupported", verbose=False)

def logger(message):
	if type(message) != str:
		message = str(message)
	logFile = open("history.log", 'a')
	logFile.write(str(datetime.datetime.now()) + " - " + message + '\n')
	logFile.close()

def error(message):
	if type(message) != str:
		message = str(message)
	logFile = open("error.log", 'a')
	logFile.write(str(datetime.datetime.now()) + " - " + message + '\n')
	logFile.close()

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

def getOnlineData(URL, regEx = False):
	data = getOnlineContent(URL)
	if data:
		if regEx:
			result = re.search(regEx, data)
			if result:
				return result.groups()
			return False
		else:
			return data
	else:
		return False

def imdbMovieInfo(movieID):
	URL = "http://www.imdb.com/title/tt" + movieID + "/"
	try:
		data = urllib.urlopen(URL).read()
	except:
		print 'Error retriving online information about this show. Please check internet connection to the TvDB.'
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
		print 'Error retriving online information about this show. Please check internet connection to IMDB.'
		return False

	if "No results found for "+title in data:
		print 'No results from search. Please try again.'
		return False
	results = ''
	if data:
		searchRegEx = '<td class="result_text">\ <a href=\"/title/tt(\d+?)/.+?\"\ >(.+?)</a>\ (.*?)<'
		results = re.findall(searchRegEx, data)
		if results:
			print "Search results retrived..."
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

class videoClass:
	def history(self, message):
		if self.config['service'] == False:
			print message
		elif self.config['debug'] == True:
			print message
		logger(message)

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
				self.history("Error in creatings temp folder. Please check permissions and try again.")
		if not self.error:
			self.history("Converting " + self.originalVideo + " in temp folder...\n")
			if self.forceConvert:
				self.history(self.originalVideo + " contains unsupported codecs and requires a force conversion.")
			self.command += "\"" + tempFile + "\""
			if self.config['debug']:
				# raw_input(self.command)
				self.history(self.command)
			self.commandSplit = shlex.split(self.command)
			print self.commandSplit
			ffmpeg = subprocess.Popen(self.commandSplit, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			converting = False
			duration = "Unknown"
			location = -1
			start = datetime.datetime.now()
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
						self.history('Duration: ' + duration.group(0))

				## Check if ffmpeg is converting
				if line.startswith("frame="):
					if self.config['debug']:
						print line
					elif self.config['service'] == False:
						status = " Current: " + re.search("\d\d:\d\d:\d\d\.\d*?", line).group(0)
						# print status, end=''
						# print '\b' * len(status, end='')
				elif self.config['debug']:
					self.history(line)
				if (datetime.datetime.now() - start).total_seconds() > 21600:
					self.error = True
					self.history("Error: Conversion has been running for 6 hours, bailing out...")
					ffmpeg.kill()
					sleep(10)
					try:
						os.remove(tempFile)
					except:
						pass
					return False
			exitCode = ffmpeg.returncode
			if self.config['debug']:
				self.history(exitCode)
			if exitCode != 0:
				self.history('Error converting, ffmpeg did mot close correctly. Please try again.')
				error(self.originalVideo + " -> ffmpeg error code: " + str(exitCode))
				error(self.command)
				try:
					os.remove(tempFile)
				except:
					pass
				return False
			else:
				self.history("\nDone.")

			if not self.error:
				if self.config['debug']:
					self.history("Moving temp file to final destination:")
					self.history(tempFile)
					self.history(self.outputFile)
				try:
					shutil.move(tempFile, self.outputFile)
					self.history(self.originalVideo + " -> " + self.outputFile)
					return True
				except Exception as blarg:
					self.error = True
					error("Failed to move temp file: " + self.originalVideo + " -> " + self.outputFile + '\n')
					error(str(blarg))
					self.history("Failed to move temp file to final destination. Check folder/file permissions.")
			else:
				return False
		else:
			return False

	def convertFile(self):
		if not self.error:
			self.history("\n\nConvert/Move: ")
			self.history(self.originalVideo)
			self.history(self.outputFile)
			self.history("Video Conversion: " + str(self.requiredConversion['video']))
			self.history("Audio Conversion: " + str(self.requiredConversion['audio']))
			self.history("Subtitle Conversion: " + str(self.requiredConversion['subtitle']))
		else:
			self.history("Errors when processing info for file, skipping: " + self.videoFile)

		if not self.error:
			## Check if the videoFile already exsists
			if os.path.exists(self.outputFile):
				while True:
					if self.config['auto']:
						self.history(self.outputFile + " already exsists, skipping conversion and deleting video to convert.")
						self.error = True
						choice = 'n'
					else:
						self.history(self.videoTitle + " already exsists.")
						# choice = raw_input("Would you like to overwrite it? (Y/N): ")
						choice = 'n'
					if choice.lower() == 'y':
						try:
							os.remove(self.outputFile)
							break
						except:
							self.history("Error in deleteing " + self.videoTitle + " you may not have permission to this path/file or the file is in use. Cannot continue.")
							self.error = True
							break
					elif choice.lower() == 'n':
						self.error = True
						try:
							os.remove(self.originalVideo)
						except:
							self.history("Error in deleteing " + self.videoTitle + " you may not have permission to this path/file or the file is in use. Cannot continue.")
						return True
					else:
						self.history("Invalid input. Please try again.")

		if not self.error:
			## Prepare for the folder path for the move
			if not os.path.exists(self.destination):
				try:
					os.makedirs(self.destination)
				except:
					self.history("Error creating destination for video. Please ensure you have permissions to: " + self.destination)
					self.error = True

		if not self.error:
			## Move subtitles and place it in the destination folder
			if self.subFile and not self.error:
				self.history("Moving subtitle file...")
				subOutputFile = self.outputFile[:self.outputFile.rfind('.')]+self.subFile[self.subFile.rfind('.'):]
				if self.config['debug']:
					self.history(self.subFile)
					self.history(subOutputFile)
				try:
					shutil.move(self.subFile, subOutputFile)
					self.history("Moved.")
				except:
					self.history("Error moving subtitle file. Please check file/folder permissions.")
			if not self.error:
				self.history("Converting video file...")
				passed = self.convertVideo()
				if not passed and not self.error:
					#self.history("Error performing quick convert, usually has to do with an improperly packed video, requires a full conversion to resolve. Attempting that now...")
					#self.forceConvert = True
					#self.buildCommand()
					#passed = self.convertVideo()
					#if not passed:
					self.error = True
		if not self.error:
			## Prompt if user wishes to remove original file as the converted file has been moved.
			while True:
				if self.config['autoDelete']:
					choice = 'y'
				else:
					choice = raw_input("Delete orignal file: " + self.originalVideo + " (Y/N): ")

				if choice.lower() == 'y':
					try:
						os.remove(self.originalVideo)
						self.history("Deleted original file.")
					except:
						self.history("Failed to remove orignal file, please check permissions.")
					break
				elif choice == 'n':
					break
				else:
					self.history("Invalid input. Please try again.")

	def streamMenu(self, streams, title):
		if len(streams) > 0:
			if len(streams) == 0:
				while True:
					self.history("Video contains no " + title + " streams!")
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
							self.history("Invalid selection, please try again.")
			elif len(streams) > 1 and not self.config['auto']:
				self.history("Found multiple options for " + title + ", please select one: ")
				while True:
					for index in xrange(len(streams)):
						self.history(str(index+1).zfill(2) + " - " + streams[index].lang + " - " + streams[index].info + " supported = " + str((not streams[index].unsupported)))
					self.history( str(len(streams)+1).zfill(2) + " - None of the above.")
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
								self.history("Invalid selection, please try again.")
						else:
							self.history("Invalid input, please try again.")
					else:
						self.history("Invalid input, please try again.")
			elif len(streams) == 1 and not streams[0].unsupported:
				self.history("Found a single " + title + " stream: " + streams[0].lang + " - " + streams[0].info)
				return streams[0]
			else:
				self.history("Error in processing " + title + " streams.")
				self.error = True
				return False
		else:
			self.history("Found no " + title + " steams.")
			return False

	def mapFileStreams(self):
		results = []

		streams = []
		## ffprobe -analyzeduration 5000 %file$
		self.history("Gathering internal video info: " + self.originalVideo)
		self.command = "/share/CACHEDEV1_DATA/.qpkg/Entware-ng/bin/ffprobe -analyzeduration 5000 \"" + self.originalVideo + '"'
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
					self.history(line)
								# Stream #0:2(eng): Subtitle: subrip (default)
				info = re.search("Stream\ \#(\d{1,2}\:\d{1,2})(.*?)\:\ (.+?)\:\ (.*)", line)
				if info:
					if self.config['debug']:
						self.history(info.groups())
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

		# for key in sortedStreams.keys():
		#     temp = self.streamMenu(sortedStreams[key], key)
		#     if not self.error:
		#         results.append(temp)
		#     else:
		#         break

		# if not self.error:
		#     for index in range(len(results)-1, -1, -1):
		#         if results[index]:
		#             if results[index].unsupported == True:
		#                 self.history(results[index].type + " - " + results[index].lang + " - " + results[index].id + " - " + results[index].info + " - uses an unsupported codec and cannot be converted. Please select a different stream if possible, or manually convert.")
		#                 self.error = True

		if not self.error:
			# self.streams = dict(video=results[0], audio=results[1], subtitle=results[2])
			self.streams = sortedStreams
			if self.config['debug']:
				self.history(self.streams)

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
		# self.forceConvert = True
		self.requiredConversion = dict( video=False, audio=False, subtitle=False )
		if self.config['cpuLimit']:
			self.command = "nice -n 8 "
		else:
			self.command = ""

		self.command += "/share/CACHEDEV1_DATA/.qpkg/Entware-ng/bin/ffmpeg "
		# if self.config['debug']:
		#     self.command += "-report "
		self.command += "-i \"" + self.originalVideo + "\" "

		if len(self.streams['video']) > 0:
			if self.config['debug']:
				self.history("Adding video...")
				self.history(self.streams['video'])

			for stream in self.streams['video']:
				self.command += "-map {} ".format(stream.id)

				if not self.forceConvert:
					resolution = re.search("\ (\d+?)x(\d+?)[\ \,]", stream.info)
					if resolution:
						width = int(resolution.group(1))
						height = int(resolution.group(2))
						self.history(str(width) + 'x' + str(height))
						gcd = fractions.gcd(width, height)
						if gcd:
							self.history( str(width/gcd) + ':' + str(height/gcd) )
						self.history("1208x720")

						if width <= 1300 and height <= 750 and "h264" in stream.info:
							self.command += "-vcodec copy "
						else:
							# self.command += "-profile:v main -level 3.1 -maxrate 2m "
							self.command += "-profile:v main -level 3.1 -maxrate 3m -vf 'scale=-2:720:flags=lanczos' "
							self.requiredConversion['video'] = True

		if len(self.streams['audio']) > 0:
			if self.config['debug']:
				self.history("Adding audio...")
				self.history(self.streams['audio'])
			for stream in self.streams['audio']:
				self.command += "-map " + stream.id + ' '
				if not self.forceConvert:
					if "aac" in stream.info:
						self.command += "-acodec copy "
					else:
						self.command += "-strict -2 -acodec aac -maxrate 256k "
						self.requiredConversion['audio'] = True

		if self.forceConvert:
			self.command += "-profile main -level 3.1 -maxrate 3m scale=-1:720 "

		if len(self.streams['subtitle']) > 0:
			if self.config['debug']:
				self.history("Adding subtitle...")
				self.history(self.streams['subtitle'])
			for stream in self.streams['subtitle']:
				self.command += "-map " + stream.id + ' '
				if "mov_text" in stream.info:
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
			self.history(self.videoPath)
			self.history(self.config['watchedFolder'])
			self.history(self.videoPath != self.config['watchedFolder'])
			self.history(beginning)
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
				self.history(subFile)
			if len(subFile) > 0:
				if len(subFile) > 1 and not self.config['auto']:
					while True:
						self.history("Multiple subtitle files found, please select which one you would like to use or to skip.")
						for entry in range(0, len(subFile)):
							self.history(str(entry+1).zfill(2) + ' - ' + subFile[entry])
						self.history(str(len(subFile)+1).zfill(2) + ' - Do not use any.')
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
								self.history("Invalid choice. Please try again.")
						else:
							self.history("Invalid input. Please try again.")
				elif len(subFile) == 1 and not self.config['auto']:
					subFile = subFile[0]
					while True:
						self.history("Found a subtitle file: " + subFile)
						choice = raw_input("Would you like to use this subtitle file? (Y/N): ")
						if len(choice) == 1:
							if choice.lower() == 'y':
								self.subFile = subFile
								break
							elif choice.lower() == 'n':
								self.subFile = False
								break
							else:
								self.history("Invalid choice. Please try again.")
						else:
							self.history("Invalid input. Please try again.")
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
			self.history("Subtitle search result:")
			self.history("Subtitle File: " + str(self.subFile))

		if self.subFile:
			self.history("Got a external file subtitle: " + self.subFile)

	def start(self, config, videoPath, videoFile):
		self.history(videoFile)

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
					self.history("Conversion level is higher then mode, video will not be converted.")
				self.error = True
		self.checkForSubFiles()

class tvEpisode(videoClass):
	def __init__(self, config, videoPath, videoFile, selectedTvShow, anime):
		self.config = config
		self.history("\n\nProcessing: " + videoFile)

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
				self.history("Checking: " + self.config['episodeRegEx'][expression])
			result = re.search(self.config['episodeRegEx'][expression], ' ' + self.videoFile.lower() + ' ')
			if result:
				if self.config['debug']:
					self.history(result.groups())
				for item in result.groups()[1:]:
					if item.isdigit():
						self.showNumbers.append(int(item))
					else:
						self.history("Error: regex groupings '()' should only be digits.")
						self.error = True
				break
		if len(self.showNumbers) == 0:
			result = re.search("((\d\d)(\d\d))" , self.videoFile.lower() )
			if result:
				for item in result.groups()[1:]:
					if item.isdigit():
						self.showNumbers.append(int(item))
					else:
						self.history("Error: regex groupings '()' should only be digits.")
						self.error = True
		if self.config['debug']:
			self.history("Got regex episode info.")
			self.history(self.showNumbers)
			self.history(self.error)

		if not self.error:
			self.seasonEpisodeFilter()
			if self.config['debug']:
				self.history("Finished episode filter.")
				self.history("Result:" + str(self.SeEp))

		if not self.error:
			self.getConfirmation(True) ##auto mode??
			if self.config['debug']:
				self.history("Got confirmation.")

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

	def history(self, message):
		if self.config['service'] == False:
			print message
		elif self.config['debug'] == True:
			print message
		logger(message)

	def printOut(self):
		if not self.error:
			return self.videoFile + " -> " + self.showInfo['SeriesName'] + " S" + str(self.SeEp[0]).zfill(2) + "E" + str(self.SeEp[1]).zfill(2)
		else:
			return self.videoFile + " -> Error"

	def summary(self):
		if self.manualOverRide:
			self.error = False
			self.history(self.showInfo['SeriesName'] + " Season " + str(self.SeEp[0]) + " Episode " + str(self.SeEp[1]))
			return "No description avaliable due to manual override."

		try:
			self.tvShowEpisodeInfo = self.showInfo[self.SeEp[0]][self.SeEp[1]]
		except:
			return False

		if not self.tvShowEpisodeInfo:
			if self.config['debug']:
				self.history("Error retringing show info.")
			return False
		description = ""

		if self.config['debug']:
			self.history(self.showInfo.keys())

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
				self.history("This show has " + str(len(self.seasonInfo)) + " seasons: 0 - " + str(len(self.seasonInfo)-1))
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
						while True:
							if newSeason:
								confirm = 'y'
							else:
								confirm = raw_input(str(choice) + " is greater then the series has, do you wish to allow this anyway? (Y/N): ")
							if confirm.lower() == 'y':
								self.manualOverRide = True
								self.SeEp[0] = choice
								exit = True
								break
							elif confirm.lower() == 'n':
								break
							else:
								self.history("Invalid input. Please try again.")
					else:
						self.history("Invalid season number, there are only " + str(len(self.seasonInfo)) + " seasons listed.")
				else:
					self.history("Invalid input. Please try again.")
			else:
				if self.SeEp[0] >= len(self.seasonInfo):
					while True:
						confirm = raw_input(str(self.SeEp[0]) + " was auto detected and is greater then the series has, do you wish to allow this anyway? (Y/N): ")
						if confirm.lower() == 'y':
							self.manualOverRide = True
							exit = True
							break
						elif confirm.lower() == 'n':
							break
						else:
							self.history("Invalid input. Please try again.")
				else:
					exit = True

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
					self.history("Season " + str(self.SeEp[0]) + " contains " + str(self.seasonInfo[self.SeEp[0]]) + " episodes.")
					choice = raw_input("Enter in new episode number: (Previous = " + str(self.SeEp[1]) + "): ")
				else:
					choice = str(newEpisode)
				if len(choice) > 0:
					if choice.isdigit():
						choice = int(choice)
						if choice >= 0 and choice <= self.seasonInfo[self.SeEp[0]]:
							self.SeEp[1] = choice
							exit = True
						elif choice > self.seasonInfo[self.SeEp[0]]:
							while True:
								if newEpisode:
									confirm = 'y'
								else:
									confirm = raw_input(str(choice) + " is greater then the season has, do you wish to allow this anyway? (Y/N): ")
								if confirm.lower() == 'y':
									self.manualOverRide = True
									self.SeEp[1] = choice
									exit = True
									break
								elif confirm.lower() == 'n':
									break
								else:
									self.history("Invalid input. Please try again.")
						else:
							self.history("Invalid episode number, there are only " + str(self.seasonInfo[self.SeEp[0]]) + " episodes listed.")
					else:
						self.history("Invalid input. Please try again.")
				else:
					if self.SeEp[1] > self.seasonInfo[self.SeEp[0]]:
						while True:
							confirm = raw_input(str(self.SeEp[1]) + " was auto detected and is greater then the season has, do you wish to allow this anyway? (Y/N): ")
							if confirm.lower() == 'y':
								self.manualOverRide = True
								exit = True
								break
							elif confirm.lower() == 'n':
								break
							else:
								self.history("Invalid input. Please try again.")
					else:
						exit = True
			else:
				while True:
					choice = raw_input("Enter in new episode number: (Previous = " + str(self.SeEp[1]) + "): ")
					if len(choice) > 0:
						if choice.isdigit():
							self.SeEp[1] = int(choice)
							exit = True
							break
						else:
							self.history("Invalid input. Please try again.")
					else:
						self.history("Invalid input. Please try again.")

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
					self.history(summary)
				if assume:
					return False
				if not self.config['auto']:
					self.history("1 - Use this information.")
					self.history("2 - Change season and episode information")
					done = raw_input("Choice: ")
					if done.isdigit():
						done = int(done)
						if done == 1:
							return False
						elif done == 2:
							self.askForSeEp()
						else:
							self.history("Invalid choice. Please Try again.")
					else:
						self.history("Invalid input. Please try again.")
				else:
					return False
		return False

	def findByEpisodeNumber(self, needle):
		if self.ova:
			if needle <= self.showInfo[0].keys()[-1]:
				return [0, needle]
			else:
				return -1
		else:
			for season in self.showInfo.keys():
				for episode in self.showInfo[season].keys():
					if self.showInfo[season][episode]['absolute_number'] != None:
						if len(self.showInfo[season][episode]['absolute_number']) > 0:
							if int(self.showInfo[season][episode]['absolute_number']) == int(needle):
								return [season, episode]
			return -1

	def seasonEpisodeFilter(self):
		done = False
		self.history("\nProcessing season/episode info: " + self.videoFile)
		if self.error:
			self.history("Erroring out...")
			return False
		self.seasonInfo = []
		# if type(self.showInfo) is not dict:
		#     self.history("Erroring out, showInfo is not a dict:" + str(self.showInfo))
		#     return False
		bottomSeason = self.showInfo.keys()[0]
		topSeason = self.showInfo.keys()[-1]
		if bottomSeason != 0:
			for filler in range(0, bottomSeason):
				self.seasonInfo.append(0)
		for entry in range(bottomSeason, topSeason+1):
			self.seasonInfo.append(self.showInfo[entry].keys()[-1])

		self.SeEp = [ '', '' ]
		self.history("Inited to:" + str(self.SeEp))
		self.history("Checking:" + str(self.showNumbers))
		slot = -1
		seasonWasInPath = False

		if len(self.showNumbers) > 0 and self.ova:
			self.SeEp[0] = 0
			self.SeEp[1] = self.showNumbers[0]
			self.history("It's an ova?")
		elif len(self.showNumbers) > 0:
			self.history("Length of showNumbers:" + str(len(self.showNumbers)))
			if len(self.showNumbers) == 2:
				self.SeEp[0] = self.showNumbers[0]
				self.SeEp[1] = self.showNumbers[1]
				self.history("Not here?")
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
							self.history("Found season in path: " + str(self.SeEp[0]))

					if seasonWasInPath:
						if self.config['debug']:
							self.history('Checking with found season from path...')
							self.history('Using episode: ' + str(self.showNumbers[0]))
						self.SeEp[1] = self.showNumbers[0]
						found = self.summary()
						if found != False:
							done = True
					else:
						found = False
				if not done:
					processAsFullCount = False
					if seasonWasInPath and self.SeEp[0] <= topSeason:
						self.history(str(self.SeEp[0]) + "<=" + str(topSeason))
						seasonTopEpisode = self.showInfo[self.SeEp[0]].keys()[-1]
						if int(self.showNumbers[0]) > seasonTopEpisode:
							processAsFullCount = True
					if not processAsFullCount:
						if len(str(self.showNumbers[0])) == 3:
							self.SeEp[0] = int(str(self.showNumbers[0])[0])
							self.SeEp[1] = int(str(self.showNumbers[0])[1:])
							self.history("Here?")
						else:
							self.SeEp[0] = 1
							self.SeEp[1] = self.showNumbers[0]
							self.history("Here instead?")
						found = self.summary()
						if found != False:
							found = True

					else:
						## assume the number is a full sequencial count not season and Episode
						error = False
						result = self.findByEpisodeNumber(self.showNumbers[0])
						if self.config['debug']:
							self.history("FindByEpisodeNumber Result: " + str(result))
						if result != -1:
							self.SeEp = result
						elif not self.config['auto']:
							self.askForSeEp()
			else:
				self.askForSeEp()
		else:
			self.askForSeEp()

class tvShow:
	def history(self, message):
		if self.config['service'] == False:
			print message
		elif self.config['debug'] == True:
			print message
		logger(message)

	def getShowConfirmation(self, assume = False):
		if assume and self.config['auto']:
			summary = self.summary()
			self.history("Found a match.")
			if not self.config['auto']:
				self.history(summary)
			self.selectedTvShow = self.showEpisodeInfo
			return True
		else:
			while True:
				summary = self.summary()
				self.history('\n' + self.episode)
				self.history("Looking up " + self.showInfo['SeriesName'] + " information... ")
				self.history("Displaying Pilot episode for confirmation: ")
				self.history(summary)
				self.history("1 - Use this TV Show.")
				self.history("2 - Back")
				done = raw_input("Choice: ")
				if done.isdigit():
					done = int(done)
					if done == 1:
						self.selectedTvShow = self.config['tvdbHandler'].getShowInfo(self.showInfo['seriesid'])
						return True
					elif done == 2:
						return False
					else:
						self.history("Invalid choice. Please Try again.")
				else:
					self.history("Invalid input. Please try again.")
		return False

	def summary(self):
		if self.manualOverride:
			self.error = False
			self.history(self.showInfo['SeriesName'] + " Season " + str(self.SeEp[0]) + " Episode " + str(self.SeEp[1]))
			return "No description avaliable due to manual override."
		if self.config['debug']:
			self.history(self.showInfo['SeriesName'])
			self.history(self.SeEp)

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
				self.history("Error retringing show info.")
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
								self.history("Error, this file may be a TV Show but is not allowed on TVDB.")
								self.history("May need to try this as a movie to use IMDb information.")
								self.history("Would you like to try IMDb or skip?")
								self.history("1 - Try IMDb")
								self.history("2 - Skip")
								choice = raw_input("Choice: ")
								if len(choice) > 0:
									if choice.isdigit():
										choice = int(choice)
										if choice == 1:
											## add in handler for error movies
											self.config['movies'].append(self.config['movieHandler'](self.config, self.folderPath, self.episode))
											self.error = True
											if self.config['debug']:
												self.history("Error, show is actually a movie and will not be processed as a show.")
											break
										elif choice == 2:
											self.error = True
											if self.config['debug']:
												self.history("Error, skipping this file.")
											break
										else:
											self.history("Invalid choice. Please try again.")
									else:
										self.history("Invalid input. Please try again.")
								else:
									self.history("Invalid input. Please try again.")
						else:
							self.error = True
							if self.config['debug']:
								self.history("Error, auto mode does not handle mis-identified files. Skipping.")
					else:
						## Filter first result and compare looking for a >90% match
						punctuation = string.punctuation.replace('(','').replace(')','')
						for char in range(0,len(punctuation)):
							if punctuation[char] in firstTitle:
								firstTitle = firstTitle.replace(punctuation[char], "")
						checkOthers = True
						if self.config['debug']:
							self.history(self.tvShowTitle.lower())
							self.history(firstTitle.lower())
						match = SM(None, self.tvShowTitle.lower(), firstTitle.lower()).ratio()
						self.history("First result has a " + "{0:.0f}%".format(match*100) + " match.")
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
							self.history("\n\nMake a selection for: " + self.episode)
							self.history("From: " + self.folderPath)
							while True:
								slot = 0
								for result in results:
									keys = result.keys()
									slot += 1
									display = str(slot).zfill(2) + " - "
									if "SeriesName" in keys:
										display += result["SeriesName"]
									else:
										self.history("Error, something went wrong in retrieving information from TVdb as we are missing title information.")
										self.error = True
									if "firstaired" in keys:
										display += " (" + str(result["firstaired"]) + ")"
									self.history(display)
								if not self.error:
									highChoice = slot
									slot += 1
									self.history(str(slot).zfill(2) + " - New Search")
									slot += 1
									self.history(str(slot).zfill(2) + " - Actually a Movie")
									slot += 1
									self.history(str(slot).zfill(2) + " - Exit")
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
													self.history("Invalid input. Please try again.")
											break
										elif choice == slot-1:
											self.error = True
											self.config['movies'].append(self.config['movieHandler'](self.config, self.folderPath, self.episode))
										elif choice == slot:
											self.error = True
											break
										else:
											self.history("Invalid choice. Please try again.")
									else:
										self.history("Invalid input. Please try again.")
								else:
									break
						elif checkOthers and self.config['auto']:
							self.error = True
							if self.config['debug']:
								self.history("Error, auto mode and a >90% match was not made.")
			else:
				## Step through remaining words and search online until we get some results.
				foundName = False
				tempTvShowTitle = self.tvShowTitle.lower().split()
				for index in range(len(tempTvShowTitle), 0, -1):
					try:
						results = self.config['tvdbHandler'].search(' '.join(tempTvShowTitle[:index]))
					except:
						self.history("Error communicating with the tvdb. Please check your connection or try again later.")
						self.error = True
					if results:
						if len(results) > 0 :
							self.tvShowTitle = ' '.join(tempTvShowTitle[:index])
							foundName = True
							break
				if not foundName:
					self.history("\n\nEpisode: " + self.episode)
					self.history("From: " + self.folderPath)
					self.history("No results for " + self.tvShowTitle)
					if self.config['auto']:
						self.error = True
						self.history("Unable to find a close match to title.")
					else:
						while True:
							userInput = raw_input("Enter in title to search: ")
							if len(userInput) > 0:
								self.tvShowTitle = userInput
								self.lookup()
								break
							else:
								self.history("Invalid input. Please try again.")
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

		if len(self.tvShowTitle) > 0:
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
				self.history("Error in removing original path from file path for processing. Error in path/linking.")
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

		if len(self.tvShowTitle) > 0:
			if self.tvShowTitle[0] == ' ':
				self.tvShowTitle = self.tvShowTitle[1:]
			if self.tvShowTitle[-1] == ' ':
				self.tvShowTitle = self.tvShowTitle[:-1]

	def isAnime(self):
		print self.showInfo.keys()
		genres = self.showInfo.get('Genre', "").split('|')
		if 'Animation' in genres:
			self.anime = True
			self.history("Show is calisified as an Anime show.")
		else:
			self.anime = False

	def buildQueue(self):
		self.queues = [ [], [], [], [] ]
		if not self.error:
			for episode in self.episodes:
				self.queues[episode.convserionLevel()].append(episode)

		if self.config['debug']:
			self.history(self.queues[0])
			self.history(self.queues[1])
			self.history(self.queues[2])
			self.history(self.queues[3])

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

		if self.config['debug']:
			self.history(self.episodes)
			self.history(self.episode)
			self.history(folder)
		self.folderPath = os.path.join(self.config['watchedFolder'], folder)
		if self.config['debug']:
			self.history(self.folderPath)
		self.manualOverride = False
		self.SeEp = [ 1, 1 ]
		self.showInfo = False
		self.anime = False

		self.history("\n\nProcessing: " + os.path.join(self.folderPath, episodes[0]))

		self.tvShowTitle = episodes[0].lower()
		self.nameFilter()
		self.tvShowTitle = self.tvShowTitle.title()
		if self.config['debug']:
			self.history("Finished name filter.")
			self.history(self.error)

		if not self.error:
			self.lookup()
			if not self.error:
				self.history('Retriving additional online information...')
				self.isAnime()
			if self.config['debug']:
				self.history("Finished lookup.")
				self.history(self.error)

		if not self.error:
			for index in xrange(len(self.episodes)):
				self.episodes[index] = tvEpisode(self.config, self.folderPath, self.episodes[index], self.selectedTvShow, self.anime)
		if not self.error:
			if self.config['auto']:
				for index in xrange(len(self.episodes)):
					self.history(str(index+1).zfill(2) + " - " + self.episodes[index].printOut())
			else:
				while True:
					self.history("Search results: ")
					for index in xrange(len(self.episodes)):
						self.history(str(index+1).zfill(2) + " - " + self.episodes[index].printOut())

					self.history(str(len(self.episodes)+1).zfill(2) + " - Change whole season")
					self.history(str(len(self.episodes)+2).zfill(2) + " - Continue")
					choice = raw_input("Selection: ")
					if len(choice) > 0:
						if choice.isdigit():
							choice = int(choice)-1
							if choice >= 0 and choice < len(self.episodes):
								self.episodes[choice].getConfirmation()
							elif choice == len(self.episodes):
								while True:
									bottomSeason = self.selectedTvShow.keys()[0]
									topSeason = self.selectedTvShow.keys()[-1]
									if bottomSeason == 0:
										count = topSeason + 1
									else:
										count = topSeason
									self.history("This show has " + str(count) + " seasons. " + str(bottomSeason) + " - " + str(topSeason))
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
															self.history("Invalid choice, please try again.")
													else:
														self.history("Invalid input, please try again.")
												break
											else:
												self.history("Invalid selection. Please try again.")
										else:
											self.history("Invalid input, please try again.")
									else:
										self.history("Invalid input, please try again.")
							elif choice == len(self.episodes)+1:
								break
							else:
								self.history("Invalid choice, please try again.")
						else:
							self.history("Invalid input, please try again.")
					else:
						self.history("Invalid input, please try again.")

class movie(videoClass):
	def __init__(self, config, videoPath, videoFile):
		self.config = config
		self.history("\n\nProcessing movie: " + videoFile)
		self.start(config, videoPath, videoFile)

		self.nameFilter()

		if not self.error:
			## Use filtered name for online search and confirmation
			self.getOnlineInfo()
		else:
			if self.config['debug']:
				self.history("Error in name filter, not checking online.")

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
			self.history("Error in online info, not moving the file.")

	def history(self, message):
		if self.config['service'] == False:
			print message
		elif self.config['debug'] == True:
			print message
		logger(message)

	def generateSummary(self):
		self.summary = ""

		if self.config['debug']:
			self.history(self.movieInfo)

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
		self.history("Retriving information from IMDb...")
		self.movieInfo = self.imdbMovieInfo(self.curMovie.ID)
		if self.movieInfo:
			self.generateSummary()
			self.history(self.summary)

			if assume and self.config['auto']:
				return True
			else:
				while True:
					self.history("1 - Use this information.")
					self.history("2 - Back")
					done = raw_input("Choice: ")
					if done.isdigit():
						done = int(done)
						if done == 1:
							return True
						elif done == 2:
							self.clearShowInfo()
							return False
						else:
							self.history("Invalid choice. Please Try again.")
					else:
						self.history("Invalid input. Please try again.")
		else:
			self.error = True

	def nameFilter(self):
		self.videoTitle = self.videoFile
		if self.config['debug']:
			self.history(self.videoTitle)
		## Remove uploader name from beginning
		if self.videoTitle[0] == '(':
			self.videoTitle = self.videoTitle[self.videoTitle.find(')')+1:]
			if self.config['debug']:
				self.history(self.videoTitle)
		if self.videoTitle[0] == '[':
			self.videoTitle  = self.videoTitle[self.videoTitle.find(']')+1:]
			if self.config['debug']:
				self.history(self.videoTitle)

		## Remove extra parentesies from around years or anything
		self.videoTitle = self.videoTitle.replace('(', "").replace(')', "")
		if self.config['debug']:
			self.history(self.videoTitle)

		# Filter out alternative space marks
		altSpace = [ '.', '_' ]
		for alt in altSpace:
			self.videoTitle = self.videoTitle.replace(alt, ' ')
		if self.config['debug']:
			self.history(self.videoTitle)

		# Use common descprtion terms to find end of movie title
		self.videoTitle = self.videoTitle.lower().split()
		if self.config['debug']:
			self.history(self.videoTitle)

		stop = len(self.videoTitle)
		for term in self.config['commonTerms']:
			if term.lower() in self.videoTitle:
				place = self.videoTitle.index(term.lower())
				if place < stop:
					stop = place

		self.videoTitle = ' '.join(self.videoTitle[:stop])
		if self.config['debug']:
			self.history(self.videoTitle)

		## Add/restore parentesies around the year if it's left after filtering.
		year = re.search("\ \d\d\d\d\ ", self.videoTitle)
		try:
			self.videoTitle = self.videoTitle.replace(year.group(0), " (" + year.group(0)[1:-1] + ") ")
		except:
			pass

	def imdbMovieInfo(self, movieID):
		URL = "http://www.imdb.com/title/tt" + movieID + "/"
		if self.config['debug']:
			self.history(URL)
		try:
			data = urllib.urlopen(URL).read()
		except:
			self.history('Error retriving online information about this show. Please check internet connection to the TvDB.')
			return False

		data = data.replace("\n", "").replace("\r", "")

		#try:
		# <h1 itemprop="name" class="">UFC Fight Night: Silva vs. Bisping&nbsp;            </h1>
		search = re.search("<h1 itemprop=\"name\"(?:.*?)>([\s\w\W]*?)</h1>", data)
		if self.config['debug']:
			self.history(search.groups())
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
			self.history("Error parsing IMDB information. Please check that IMDB is working.")
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
		#self.history(URL)
		try:
			data = urllib.urlopen(URL).read()
			data = data.replace("\n", "")
		except:
			self.history('Error retriving online information about this show. Please check internet connection to the TvDB.')
			return False

		if "No results found for "+title in data:
			self.history('No results from search. Please try again.')
			return False
		results = ''
		if data:
			searchRegEx = '<td class="result_text">\ <a href=\"/title/tt(\d+?)/.+?\"\ >(.+?)</a>\ (.*?)<'
			results = re.findall(searchRegEx, data)
			if results:
				self.history("Search results retrived...")
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
					self.history(searchResults)
				return searchResults
			else:
				return False
		else:
			return False

	def getOnlineInfo(self, ask=False):
		search = False

		## Prompt user for new title if needed
		if ask:
			while True:
				userInput = raw_input("Enter in title to search: ")
				if len(userInput) > 0:
					self.videoTitle = userInput
					break
				else:
					self.history("Invalid input. Please try again.")

		## Use IMDB and perform a search for the deduced title or user input
		self.history("Looking up: " + self.videoTitle)
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
					self.history("Found a " + "{0:.0f}%".format(match*100) + " match.")
					found = self.getConfirmation(results[0], True)
				if not found and not self.config['auto']:
					## Since first did not match high enough, in manual mode we list search results and prompt for the user to select one or type in new search
					while True:
						self.history("Search Results for " + self.videoTitle + ":")
						slot = 0
						for result in results:
							slot += 1
							display = str(slot).zfill(2) + " - "
							if result.name:
								display += result.name
							else:
								self.history("Error, something went wrong in retrieving information from IMDB as we are missing title information.")
								break
							if len(result.year):
								display += " (" + str(result.year) + ")"
							self.history(display)
						slot += 1
						self.history(str(slot).zfill(2) + " - New search")
						slot += 1
						self.history(str(slot).zfill(2) + " - Manual Name")
						slot += 1
						self.history(str(slot).zfill(2) + " - Actually a TV Show")
						slot += 1
						self.history(str(slot).zfill(2) + " - Exit")
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
								break
							elif choice == slot:
								self.error = True
								break
							else:
								self.history("Invalid choice. Please try again.")
						else:
							self.history("Invalid input. Please try again.")
				elif not found and self.config['auto']:
					self.error = True
			else:
				search = True
		else:
			search = True
		if search:
			## Step through the file name words and search after each step till we get some results
			self.history("Trying alternative titles...")
			foundName = False
			tempvideoTitle = self.videoTitle.lower().split()
			for index in range(len(tempvideoTitle), 0, -1):
				results = self.imdbSearch(' '.join(tempvideoTitle[:index]))
				if results:
					if len(results) > 0:
						self.videoTitle = ' '.join(tempvideoTitle[:index])
						foundName = True
						break
			if foundName:
				self.getOnlineInfo()
			else:
				self.history("No results for " + self.movie)
				if self.config['auto']:
					self.error = True
					self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.videoPath, self.videoFile))
				else:
					self.getOnlineInfo(True)

class MediaManager:
	def history(self, message):
		if self.config['service'] == False:
			print message
		elif self.config['debug'] == True:
			print message
		logger(message)

	def failed(self):
		return self.config['failedConverts']

	def collectionBuilder(self, data, basePath):
		for index in xrange(len(data)):
			data[index] = data[index].replace(basePath, os.sep)

		data.sort(reverse=True)

		if self.config['debug']:
			self.history(data)

		folderSets = []

		for line in data:
			videoFile = [ line[ line.rfind(os.sep)+1 : ]]
			directory = line[ 1 : line.rfind(os.sep) ]
			singleSet = [ directory, videoFile]
			folderSets.append(singleSet)

		if self.config['debug']:
			self.history(folderSets)

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
						self.history([tempSet[0], tempSet[1][0], folderSets[index][1][0], match])
					if folderSets[index][0] == tempSet[0] and match >= 0.80:
						tempSet[1].append(folderSets[index][1][0])
						folderSets.pop(index)
				collectedSets.append(tempSet)

		if self.config['debug']:
			self.history(collectedSets)

		index = 0
		while index < len(collectedSets):
			commonPrefix = os.path.commonprefix(collectedSets[index][1])
			if self.config['debug']:
				self.history(commonPrefix)
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
			self.history(masterQueue[0])
			self.history(masterQueue[1])
			self.history(masterQueue[2])
			self.history(masterQueue[3])

		for level in masterQueue:
			for video in level:
				video.convertFile()
				if self.config['debug']:
					self.history(video.hasError())
				if video.hasError():
					self.config['failedConverts'].append(video.origFile())

	def parseFilesToCheck(self):
		self.rawTvShows = self.collectionBuilder(self.rawTvShows, self.config['watchedFolder'])

		for index in xrange(len(self.rawTvShows)):
			if self.config['debug']:
				self.history(self.rawTvShows[index][0])
				self.history(self.rawTvShows[index][1])
			self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.rawTvShows[index][0], self.rawTvShows[index][1]))

		for index in xrange(len(self.rawMovies)):
			folder = self.rawMovies[index][:self.rawMovies[index].rfind(os.sep)]
			inFile = self.rawMovies[index][self.rawMovies[index].rfind(os.sep)+1:]
			self.config['movies'].append(self.config['movieHandler'](self.config, folder, inFile))

	def getFilesToCheck(self):
		self.filesToCheck = []
		self.history("Searching folder: " + self.config['watchedFolder'])
		walker = os.walk(self.config['watchedFolder'])
		for path in walker:
			if ".@__thumb" in path[0] or "@Recycle" in path[0]:
				continue
			else:
				self.history("Parsing: " + path[0])
				for fileName in path[2]:
					if self.isVideo(fileName):
						self.history("Checking: " + fileName)
						for term in self.config['excludedTerms']:
							if (term.lower() in fileName.lower()):
								self.history("Current file includes an exclusion term, skipping this file.")
								continue
							elif (term.lower() in path[0].lower()):
								self.history("Current path includes an exclusion term, skipping this file.")
								continue

						fileSize = os.path.getsize(os.path.join(path[0], fileName))
						if fileSize < self.config['minFileSize']:
							self.history("File to small, skipping this file.")
							continue

						found = False
						for expression in self.config['episodeRegEx']:
							if re.search(expression, " {} ".format(fileName.lower())):
								curFile = os.path.join(path[0], fileName)
								if self.config['debug']:
									self.history("Matching regex: {}".format(expression))
									self.history(curFile)
									self.history(self.config['failedConverts'])
								if curFile not in self.config['failedConverts']:
									self.rawTvShows.append(curFile)
									self.history("Added: " + fileName + " to TV Shows Queue.")
								else:
									self.history("File was tried before and failed, skipping.")
								found = True
								break
						if not found:
							while True:
								if self.config['auto']:
									choice = '1'
								else:
									self.history(fileName + " could not be identified, please select one bellow:")
									self.history("1 - Movie")
									self.history("2 - TV Show")
									self.history("3 - Skip")
									self.history("4 - Delete")
									self.history("5 - Exit")
									choice = raw_input("Choice: ")
								if choice.isdigit():
									choice = int(choice)
									if choice == 1:
										self.rawMovies.append(os.path.join(path[0], fileName))
										self.history("Added: " + fileName + " to Movies Queue.")
										break
									elif choice == 2:
										self.rawTvShows.append(os.path.join(path[0], fileName))
										self.history("Added: " + fileName + " to TV Shows Queue.")
										break
									elif choice == 3:
										self.history("Skipping...")
										break
									elif choice == 4:
										self.history("Deleteing...")
										try:
											os.remove(path[0] + os.sep + fileName)
										except:
											self.history("Could not delete " + fileName + ", please check permissions.")
										break
									elif choice == 5:
										exit()
									else:
										self.history("Invalid input. Please try again.")
								else:
									self.history("Invalid input, number only. Please try again.")

	def __init__(self, config):
		self.config = config
		self.config['tvShowHandler'] = tvShow
		self.config['movieHandler'] = movie

		for extension in self.config['acceptedVideoExtensions']:
			self.config['commonTerms'].append(extension[1:])

		self.config['movies'] = []
		self.config['tvShows'] = []

		self.rawMovies = []
		self.rawTvShows = []

		if os.path.isdir(self.config['watchedFolder']):
			self.config['tvdbHandler'] = TVDB(self.config['tvdbAPIkey'], self.config['debug'])
			self.getFilesToCheck()
			self.parseFilesToCheck()
			self.parseFilesToConvert()

if __name__ == "__main__":
    print "Media Manager v2"

    try:
        config = plistlib.readPlist(os.path.join(os.path.dirname(__file__), "config.plist"))
    except Exception:
        print "Error: Failed to read in config plist."
        exit(-1)

    ## Check if running in service mode
    if len(sys.argv) == 2:
        if sys.argv[1] == "-s":
            config["service"] = True
            config["auto"] = True

    ## Clean up log files
    try:
        os.remove('history.log')
    except:
        pass
    try:
        os.remove('error.log')
    except:
        pass

	shutil.rmtree("/tmp/series/", ignore_errors=True, onerror=None)

    previousStamp = False
    while True:
        curStamp = os.stat(config['watchedFolder']).st_mtime
        if curStamp != previousStamp:
            root = MediaManager(config)
            previousStamp = os.stat(config['watchedFolder']).st_mtime
            if config['service']:
                if config['debug']:
                    print root.failed()
                config['failedConverts'] = root.failed()
            else:
                break
        else:
            sleep(60*5)
