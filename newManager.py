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
import pprint

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
	def convertVideo(self):
		tempFile = os.path.join(self.config['tempFolder'], str(randint(0,5000)) + ".mp4")
		if not os.path.exists(self.config['tempFolder']):
			try:
				os.makedirs(self.config['tempFolder'])
			except:
				self.error = True
				print "Error in creatings temp folder. Please check permissions and try again."
				return False
		print "Converting", self.originalVideo, "in temp folder...\n"
		if self.forceConvert:
			print "Video contains unsupported codecs and requires a force conversion:", self.originalVideo
		self.command += "\"{}\"".format(tempFile)
		if self.config['debug']:
			raw_input(self.command)
			print self.command
		self.commandSplit = shlex.split(self.command)
		print self.commandSplit
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

			## Get length of video
			if "Duration:" in line:
				duration = re.search("\d\d:\d\d:\d\d\.\d\d", line)
				if duration:
					print 'Duration:', duration.group(0)

			print line
			if datetime.datetime.now() > timeout:
				self.error = True
				print "Error: Conversion has been running for 6 hours, bailing out..."
				ffmpeg.kill()
				sleep(10)
				try:
					os.remove(tempFile)
				except:
					pass
				return False
		exitCode = ffmpeg.returncode
		if exitCode != 0:
			print '\nError converting, ffmpeg did mot close correctly. Please try again.'
			print self.command
			print self.originalVideo, "-> ffmpeg error code:", exitCode
			try:
				os.remove(tempFile)
			except:
				pass
			return False
		else:
			print "\nDone."

		if self.config['debug']:
			print "Moving temp file to final destination:"
			print tempFile
			print self.outputFile
		try:
			shutil.move(tempFile, self.outputFile)
			print self.originalVideo, "->", self.outputFile
			return True
		except Exception as error:
			self.error = True
			print "Failed to move temp file:", self.originalVideo, "->", self.outputFile, "with error:", error

		return False

	def convertFile(self):
		if not self.error:
			print "\n\nConvert/Move: "
			print self.originalVideo
			print self.outputFile
			print "Video Conversion:", self.requiredConversion['video']
			print "Audio Conversion:", self.requiredConversion['audio']
			print "Subtitle Conversion:", self.requiredConversion['subtitle']
		else:
			print "Errors when processing info for file, skipping:", self.videoFile
			return False

		## Check if the videoFile already exsists
		if os.path.exists(self.outputFile):
			print "Video with the same destination already exists, skipping."
			self.error = True
			return False

		## Prepare for the folder path for the move
		if not os.path.exists(self.destination):
			try:
				os.makedirs(self.destination)
			except:
				print "Error creating destination for video. Please ensure you have permissions to:", self.destination
				self.error = True
				return False

		## Move subtitles and place it in the destination folder
		if self.subFiles and not self.error:
			print "Moving subtitle file..."
			subOutputFile = "{}.{}".format(self.outputFile[:self.outputFile.rfind('.')], self.subFiles[self.subFiles.rfind('.'):])
			if self.config['debug']:
				print "Moving:\n", self.subFiles, "->", subOutputFile
			try:
				shutil.move(self.subFiles, subOutputFile)
				print "Moved:\n", self.subFiles, "->", subOutputFile
			except Exception as error:
				print "Failed to move subtitle file with error:", error
				return False

		if not self.convertVideo():
			return False

		try:
			os.remove(self.originalVideo)
			print "Deleted original file."
		except Exception as error:
			print "Failed to delete source video with error:", error

	def mapFileStreams(self):
		results = []

		streams = []
		## ffprobe -analyzeduration 5000 %file$
		print "Gathering internal video info:", self.originalVideo
		self.command = "/usr/bin/env ffprobe -analyzeduration 5000 \"{}\"".format(self.originalVideo)
		self.command = shlex.split(self.command)
		ffprobe = subprocess.check_output(self.command, stderr=subprocess.STDOUT).split("\n")
		for line in ffprobe:
			if "Stream" in line:
				if self.config['debug']:
					print "Stream info:", line
								# Stream #0:2(eng): Subtitle: subrip (default)
				info = re.search("Stream\ \#(\d{1,2}\:\d{1,2})(.*?)\:\ (.+?)\:\ (.*)", line)
				if self.config['debug']:
					print info.groups()
				unsupported = False
				streams.append(streamInfo(info.group(1), info.group(2).replace('(', '').replace(')', ''), info.group(3), info.group(4), unsupported))
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
		if self.config['debug']:
			print "Streams:", self.streams

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
		self.requiredConversion = dict( video=False, audio=False, subtitle=False )
		if self.config['cpuLimit']:
			self.command = "/usr/bin/env nice -n 8 "
		else:
			self.command = ""

		self.command += "/usr/bin/env ffmpeg -i \"{}\"".format(self.originalVideo)

		if self.streams['video']:
			if self.config['debug']:
				print "Adding video stream(s):", self.streams['video']

			for stream in self.streams['video']:
				print "Mapping stream id:", stream.id
				self.command += "-map {} ".format(stream.id)

				if not self.forceConvert:
					resolution = re.search("\ (\d+?)x(\d+?)[\ \,]", stream.info)
					if resolution:
						width = int(resolution.group(1))
						height = int(resolution.group(2))
						print "Stream resolution:", str(width) + 'x' + str(height)
						if width <= 1300 and height <= 750 and "h264" in stream.info:
							self.command += "-vcodec copy "
						else:
							# self.command += "-profile:v main -level 3.1 -maxrate 2m "
							self.command += "-profile:v main -level 3.1 -maxrate 3m -vf 'scale=-2:720:flags=lanczos' "
							self.requiredConversion['video'] = True

		if self.streams['audio']:
			if self.config['debug']:
				print "Adding audio stream(s)", self.streams['audio']

			for stream in self.streams['audio']:
				print "Mapping stream id:", stream.id
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
			if self.config['debug']:
				print "Adding subtitle stream(s):", self.streams['subtitle']

			for stream in self.streams['subtitle']:
				print "Mapping stream id:", stream.id
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
		if self.config['debug']:
			print "Check for subtitles for:", self.videoFile
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

		if self.subFiles:
			print "Got external file subtitle(s):", self.subFiles

	def start(self, config, videoPath, videoFile):
		self.config = config
		self.videoPath = videoPath
		if self.videoPath[-1] != os.sep:
			self.videoPath = self.videoPath + os.sep
		self.videoFile = videoFile
		print self.videoPath
		print self.videoFile
		self.originalVideo = os.path.join(self.videoPath, self.videoFile)
		self.forceConvert = False

		## ffprobe video for info
		self.mapFileStreams()
		if self.config['mode']:
			if self.conversionLevel > self.config['mode']:
				print "Conversion level is higher then mode, video will not be converted."
				return False
		self.checkForSubFiles()
		return True

class tvEpisode(videoClass):
	def __init__(self, config, videoPath, videoFile, selectedTvShow, anime):
		self.config = config
		print "\n\nProcessing:", videoFile

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
				print "Checking:", self.config['episodeRegEx'][expression]
			result = re.search(self.config['episodeRegEx'][expression], " {} ".format(self.videoFile.lower()))
			if result:
				if self.config['debug']:
					print result.groups()
				for item in result.groups()[1:]:
					if item.isdigit():
						self.showNumbers.append(int(item))
					else:
						raise Exception("Regex groupings '()' should only be digits.")
				break
		if len(self.showNumbers) == 0:
			result = re.search("((\d\d)(\d\d))" , self.videoFile.lower() )
			if result:
				for item in result.groups()[1:]:
					if item.isdigit():
						self.showNumbers.append(int(item))
					else:
						raise Exception("Error: regex groupings '()' should only be digits.")

		if self.config['debug']:
			print "Got regex episode info:", self.showNumbers

		self.seasonEpisodeFilter()
		if self.config['debug']:
			print "Finished episode filter."
			print "Result:" + str(self.SeEp)

		self.outputFileName = "{} - S{:02}E{:02} - {}.mp4".format(self.showInfo['SeriesName'], self.SeEp[0], self.SeEp[1], self.tvShowEpisodeInfo['EpisodeName'])

		self.outputFileName = checkFileName(self.outputFileName)
		if self.anime:
			self.outputFile = self.config['animeShowFolder']
		else:
			self.outputFile = self.config['tvShowsFolder']
		self.outputFile += os.path.join(checkFileName(self.showInfo['SeriesName']), "Season {:02}".format(self.SeEp[0]))
		self.destination = self.outputFile
		self.outputFile = checkPath(os.path.join(self.outputFile, self.outputFileName))

		self.videoTitle = self.outputFileName

	def check(self):
		try:
			self.tvShowEpisodeInfo = self.showInfo[self.SeEp[0]][self.SeEp[1]]
		except Exception as error:
			print "Failed to find season/episode info with error:", error
			return False

		if not self.tvShowEpisodeInfo:
			if self.config['debug']:
				print "Error retringing show info."
			return False
		return True

	def findByEpisodeNumber(self, needle):
		if self.ova:
			if needle <= self.showInfo[0].keys()[-1]:
				return [0, needle]
			else:
				return False
		else:
			for season in self.showInfo.keys():
				for episode in self.showInfo[season].keys():
					if self.showInfo[season][episode]['absolute_number'] != None:
						if len(self.showInfo[season][episode]['absolute_number']) > 0:
							if int(self.showInfo[season][episode]['absolute_number']) == int(needle):
								return [season, episode]
			return False

	def seasonEpisodeFilter(self):
		print "\nProcessing season/episode info:", self.videoFile
		self.seasonInfo = []
		bottomSeason = self.showInfo.keys()[0]
		topSeason = self.showInfo.keys()[-1]
		if bottomSeason != 0:
			for filler in range(0, bottomSeason):
				self.seasonInfo.append(0)
		for entry in range(bottomSeason, topSeason+1):
			self.seasonInfo.append(self.showInfo[entry].keys()[-1])

		self.SeEp = [ '', '' ]
		print "Inited to:", self.SeEp
		print "Checking:", self.showNumbers
		slot = -1
		seasonWasInPath = False

		if len(self.showNumbers) > 0 and self.ova:
			self.SeEp[0] = 0
			self.SeEp[1] = self.showNumbers[0]
		elif len(self.showNumbers) > 0:
			print "Length of showNumbers:", len(self.showNumbers)
			if len(self.showNumbers) == 2:
				self.SeEp[0] = self.showNumbers[0]
				self.SeEp[1] = self.showNumbers[1]
				return True
			elif len(self.showNumbers) == 1:
				found = False
				topEpisode = 0
				for season in self.seasonInfo:
					topEpisode += int(season)

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
						print "Found season in path:", self.SeEp[0]
						print 'Checking with found season from path...'
						print 'Using episode:', str(self.showNumbers[0])
						self.SeEp[1] = self.showNumbers[0]
						if self.check():
							return True

				if len(str(self.showNumbers[0])) == 3:
					self.SeEp[0] = int(str(self.showNumbers[0])[0])
					self.SeEp[1] = int(str(self.showNumbers[0])[1:])
				else:
					self.SeEp[0] = 1
					self.SeEp[1] = self.showNumbers[0]
				if self.check():
					return True

				## assume the number is a full sequencial count not season and Episode
				result = self.findByEpisodeNumber(self.showNumbers[0])
				if self.config['debug']:
					print "FindByEpisodeNumber Result:", str(result)
				if result:
					self.SeEp = result
					return True
		raise Exception("Failed to find Season/Episode information.")

class tvShow:
	def getShowConfirmation(self, assume = False):
		if self.summary():
			self.selectedTvShow = self.showEpisodeInfo
			return True
		return False

	def summary(self):
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
			firstTitle = results[0]["SeriesName"]

			## Necessary??
			if firstTitle[0] == ' ':
				firstTitle = firstTitle[1:]
			if firstTitle[-1] == ' ':
				firstTitle = firstTitle[:-1]
			## END

			## TVdb disallows some tv broadcasted shows that no not count as tv series.
			if firstTitle == '** 403: Series Not Permitted **':
				self.config['movies'].append(self.config['movieHandler'](self.config, self.folderPath, self.episode))
				return False
			else:
				## Filter first result and compare looking for a >90% match
				punctuation = string.punctuation.replace('(','').replace(')','')
				for char in range(0,len(punctuation)):
					if punctuation[char] in firstTitle:
						firstTitle = firstTitle.replace(punctuation[char], "")
				checkOthers = True
				if self.config['debug']:
					print self.tvShowTitle.lower()
					print firstTitle.lower()
				match = SM(None, self.tvShowTitle.lower(), firstTitle.lower()).ratio()
				print "First result has a", "{0:.0f}%".format(match*100) + " match."
				if (match > .90) or (len(results) == 1):
					self.showInfo = results[0]
					found = self.getShowConfirmation(True)
					if found:
						if firstTitle not in self.config['cachedTvShows']:
							self.config['cachedTvShows'].append(firstTitle)
						checkOthers = False
					else:
						self.showInfo = False
				else:
					raise Exception("Failed to find a >90% match.")
		else:
			## Step through remaining words and search online until we get some results.
			foundName = False
			tempTvShowTitle = self.tvShowTitle.lower().split()
			for index in range(len(tempTvShowTitle), 0, -1):
				try:
					results = self.config['tvdbHandler'].search(' '.join(tempTvShowTitle[:index]))
				except:
					raise Exception("Error communicating with the tvdb. Please check your connection or try again later.")
				if results:
					if len(results) > 0 :
						self.tvShowTitle = ' '.join(tempTvShowTitle[:index])
						foundName = True
						break
			if not foundName:
				print "\n\nEpisode:", self.episode
				print "From:", self.folderPath
				print "No results for", self.tvShowTitle
				raise Exception("Unable to find a close match to title.")
			else:
				self.lookup()

	def nameFilter(self):

		## Add space buffers for regex searching
		self.tvShowTitle = " {} ".format(self.tvShowTitle)

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
				raise Exception("Error in removing original path from file path for processing. Error in path/linking.")
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
			print "Show is calisified as an Anime show."
		else:
			self.anime = False

	def buildQueue(self):
		self.queues = [ [], [], [], [] ]
		if not self.error:
			for episode in self.episodes:
				self.queues[episode.convserionLevel()].append(episode)

		if self.config['debug']:
			print self.queues[0]
			print self.queues[1]
			print self.queues[2]
			print self.queues[3]

		return self.queues

	def __init__(self, config, folder, episodes):
		self.selectedTvShow = False
		self.checkingPath = False
		self.config = config

		if not isinstance(episodes, list):
			self.episodes = [ episodes ]
			self.episode = episodes
		else:
			self.episodes = episodes
			self.episode = episodes[0]

		if self.config['debug']:
			print self.episodes
			print self.episode
			print folder

		self.folderPath = os.path.join(self.config['watchedFolder'], folder)
		if self.config['debug']:
			print self.folderPath

		self.SeEp = [ 1, 1 ]
		self.showInfo = False
		self.anime = False

		print "\n\nProcessing:", os.path.join(self.folderPath, episodes[0])

		self.tvShowTitle = episodes[0].lower()
		self.nameFilter()
		self.tvShowTitle = self.tvShowTitle.title()

		self.lookup()
		self.isAnime()

		for index in xrange(len(self.episodes)):
			self.episodes[index] = tvEpisode(self.config, self.folderPath, self.episodes[index], self.selectedTvShow, self.anime)

class movie(videoClass):
	def __init__(self, config, videoPath, videoFile):
		self.config = config
		print "\n\nProcessing movie:", videoFile
		self.start(config, videoPath, videoFile)

		self.nameFilter()

		if not self.error:
			## Use filtered name for online search and confirmation
			self.getOnlineInfo()
		else:
			if self.config['debug']:
				print "Error in name filter, not checking online."

		if not self.error:
			## Use confirmed movie info for destination and title
			self.movieTitle = checkPath(self.movieInfo.name)
			if len(self.movieInfo.year) > 0:
				self.movieTitle += ' (' + str(self.movieInfo.year) + ')'

			self.movieTitle += ".mp4"
			self.movieTitle = unicodeToString(checkFileName(self.movieTitle))

			self.destination = os.path.join(checkPath(self.config['moviesFolder']), self.movieTitle[:self.movieTitle.rfind('.')])
			self.outputFile = os.path.join(self.destination, self.movieTitle)
		else:
			print "Error in online info, not moving the file."

	def generateSummary(self):
		self.summary = ""

		if self.config['debug']:
			print self.movieInfo

		self.summary += self.movieInfo.name
		if len(self.movieInfo.year) > 0:
			self.summary += " -", self.movieInfo.year
		if len(self.movieInfo.plot) > 0:
			self.summary += " -", self.movieInfo.plot
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
		print "Retriving information from IMDb..."
		self.movieInfo = self.imdbMovieInfo(self.curMovie.ID)
		if not self.movieInfo:
			self.error = True

	def nameFilter(self):
		self.videoTitle = self.videoFile
		if self.config['debug']:
			print self.videoTitle
		## Remove uploader name from beginning
		if self.videoTitle[0] == '(':
			self.videoTitle = self.videoTitle[self.videoTitle.find(')')+1:]
			if self.config['debug']:
				print self.videoTitle
		if self.videoTitle[0] == '[':
			self.videoTitle  = self.videoTitle[self.videoTitle.find(']')+1:]
			if self.config['debug']:
				print self.videoTitle

		## Remove extra parentesies from around years or anything
		self.videoTitle = self.videoTitle.replace('(', "").replace(')', "")
		if self.config['debug']:
			print self.videoTitle

		# Filter out alternative space marks
		altSpace = [ '.', '_' ]
		for alt in altSpace:
			self.videoTitle = self.videoTitle.replace(alt, ' ')
		if self.config['debug']:
			print self.videoTitle

		# Use common descprtion terms to find end of movie title
		self.videoTitle = self.videoTitle.lower().split()
		if self.config['debug']:
			print self.videoTitle

		stop = len(self.videoTitle)
		for term in self.config['commonTerms']:
			if term.lower() in self.videoTitle:
				place = self.videoTitle.index(term.lower())
				if place < stop:
					stop = place

		self.videoTitle = ' '.join(self.videoTitle[:stop])
		if self.config['debug']:
			print self.videoTitle

		## Add/restore parentesies around the year if it's left after filtering.
		year = re.search("\ \d\d\d\d\ ", self.videoTitle)
		try:
			self.videoTitle = self.videoTitle.replace(year.group(0), " (" + year.group(0)[1:-1] + ") ")
		except:
			pass

	def imdbMovieInfo(self, movieID):
		URL = "http://www.imdb.com/title/tt" + movieID + "/"
		if self.config['debug']:
			print URL
		try:
			data = urllib.urlopen(URL).read()
		except:
			print 'Error retriving online information about this show. Please check internet connection to the TvDB.'
			return False

		data = data.replace("\n", "").replace("\r", "")

		#try:
		# <h1 itemprop="name" class="">UFC Fight Night: Silva vs. Bisping&nbsp;            </h1>
		search = re.search("<h1 itemprop=\"name\"(?:.*?)>([\s\w\W]*?)</h1>", data)
		if self.config['debug']:
			print search.groups()
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
			print "Error parsing IMDB information. Please check that IMDB is working."
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
		#print URL
		try:
			data = urllib.urlopen(URL).read()
			data = data.replace("\n", "")
		except:
			print 'Error retriving online information about this show. Please check internet connection to the TvDB.'
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
		search = False

		## Prompt user for new title if needed
		if ask:
			while True:
				userInput = raw_input("Enter in title to search: ")
				if len(userInput) > 0:
					self.videoTitle = userInput
					break
				else:
					print "Invalid input. Please try again."

		## Use IMDB and perform a search for the deduced title or user input
		print "Looking up:", self.videoTitle
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
					print "Found a", "{0:.0f}%".format(match*100) + " match."
					found = self.getConfirmation(results[0], True)
				if not found and not self.config['auto']:
					## Since first did not match high enough, in manual mode we list search results and prompt for the user to select one or type in new search
					while True:
						print "Search Results for", self.videoTitle + ":"
						slot = 0
						for result in results:
							slot += 1
							display = str(slot).zfill(2) + " - "
							if result.name:
								display += result.name
							else:
								print "Error, something went wrong in retrieving information from IMDB as we are missing title information."
								break
							if len(result.year):
								display += " (" + str(result.year) + ")"
							print display
						slot += 1
						print str(slot).zfill(2) + " - New search"
						slot += 1
						print str(slot).zfill(2) + " - Manual Name"
						slot += 1
						print str(slot).zfill(2) + " - Actually a TV Show"
						slot += 1
						print str(slot).zfill(2) + " - Exit"
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
								print "Invalid choice. Please try again."
						else:
							print "Invalid input. Please try again."
				elif not found and self.config['auto']:
					self.error = True
			else:
				search = True
		else:
			search = True
		if search:
			## Step through the file name words and search after each step till we get some results
			print "Trying alternative titles..."
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
				print "No results for", self.movie
				if self.config['auto']:
					self.error = True
					self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.videoPath, self.videoFile))
				else:
					self.getOnlineInfo(True)

class MediaManager(object):
	def collectionBuilder(self, data, basePath):
		for index in xrange(len(data)):
			data[index] = data[index].replace(basePath, "")

		data.sort(reverse=True)

		if self.config['debug']:
			print "Building tv collection from:"
			pprint.pprint(data)

		folderSets = []

		for line in data:
			folderSets.append({"folder": os.path.dirname(line), "files": [os.path.basename(line)]})

		if self.config['debug']:
			print "Folder sets:"
			pprint.pprint(folderSets)

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
					if self.config['debug']:
						print tempSet["folder"], tempSet["files"][0], folderSets[index]["files"][0], "have a match ratio of:", match
					if folderSets[index]["folder"] == tempSet["folder"] and match >= 0.80:
						tempSet["files"] += folderSets[index]["files"]
						folderSets.pop(index)
				collectedSets.append(tempSet)

		if self.config['debug']:
			print "Collected sets:"
			pprint.pprint(collectedSets)

		for index in xrange(len(collectedSets)):
			commonPrefix = os.path.commonprefix(collectedSets[index]["folder"])
			if self.config['debug']:
				print "Common file name prefix:", commonPrefix
			if commonPrefix:
				tempSet = [ collectedSets[index]["folder"], [] ]
				testChar = collectedSets[index]["files"][0][0]
				for file_index in range(len(collectedSets[index]["files"])-1, 0, -1):
					if collectedSets[index]["files"][file_index][0] != testChar:
						tempSet[1].append(collectedSets[index]["files"][file_index])
						collectedSets[index]["files"].pop(file_index)
				collectedSets.append(tempSet)

		if self.config['debug']:
			print "Detangled collected sets:"
			pprint.pprint(collectedSets)

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
		print "Searching folder:", self.config['watchedFolder']
		walker = os.walk(self.config['watchedFolder'])
		for path in walker:
			if ".@__thumb" in path[0] or "@Recycle" in path[0]:
				continue
			else:
				print "Parsing:", path[0]
				for fileName in path[2]:
					if not self.isVideo(fileName):
						continue
					print "Checking:", fileName
					for term in self.config['excludedTerms']:
						if (term.lower() in fileName.lower()):
							print "Current file includes an exclusion term, skipping this file."
							continue
						elif (term.lower() in path[0].lower()):
							print "Current path includes an exclusion term, skipping this file."
							continue

					fileSize = os.path.getsize(os.path.join(path[0], fileName))
					if fileSize < self.config['minFileSize']:
						print "File to small, skipping this file."
						continue

					found = False
					for expression in self.config['episodeRegEx']:
						if re.search(expression, " {} ".format(fileName.lower())):
							print path[0]
							curFile = os.path.join(path[0], fileName)
							if curFile not in self.config['failedConverts']:
								self.rawTvShows.append(curFile)
								print "Added:", curFile, "to TV Shows Queue."
							else:
								print "File was tried before and failed, skipping."
							found = True
							break
					if not found:
						curFile = os.path.join(path[0], fileName)
						self.rawMovies.append(curFile)
						print "Added:", curFile, "to Movies Queue."

	def parseFilesToCheck(self):
		self.rawTvShows = self.collectionBuilder(self.rawTvShows, self.config['watchedFolder'])

		for index in xrange(len(self.rawTvShows)):
			if self.config['debug']:
				print "Folder:", self.rawTvShows[index]["folder"]
				print "Files:", self.rawTvShows[index]["files"]
			self.config['tvShows'].append(self.config['tvShowHandler'](self.config, self.rawTvShows[index]["folder"], self.rawTvShows[index]["files"]))

		for index in xrange(len(self.rawMovies)):
			self.config['movies'].append(self.config['movieHandler'](self.config, os.path.dirname(self.rawMovies[index]), os.path.basename(self.rawMovies[index])))

	def parseFilesToConvert(self):
		masterQueue = [ [], [], [], [] ]

		if self.config['movies']:
			for video in self.config['movies']:
				masterQueue[video.convserionLevel()].append(video)

		if self.config['tvShows']:
			for show in self.config['tvShows']:
				queue = show.buildQueue()
				for index in xrange(4):
					for slot in xrange(len(queue[index])):
						masterQueue[index].append(queue[index][slot])

		if self.config['debug']:
			print "Priority 1 items:", masterQueue[0]
			print "Priority 2 items:", masterQueue[1]
			print "Priority 3 items:", masterQueue[2]
			print "Priority 4 items:", masterQueue[3]

		for level in masterQueue:
			for video in level:
				video.convertFile()
				if video.hasError():
					self.config['failedConverts'].append(video.originalVideo)

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
	print "Media Manager v2"

	try:
		config = plistlib.readPlist(os.path.join(os.path.dirname(__file__), "config.plist"))
	except Exception:
		print "Error: Failed to read in config plist."
		exit(-1)

	## Clear TVDB cache folderInfo
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
