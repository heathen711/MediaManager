import html5lib
import requests
import re
from bs4 import BeautifulSoup


class IMDB(object):
    baseUrl = "http://www.imdb.com/"
    titleUrl = baseUrl+"title/"
    searchUrl = baseUrl+"find?s=all&q="
    creditsPath = 'fullcredits/'
    currentSearchTitle = None

    def getMovie(self, title):
        return self.getMovieByImdbId(self.getIdFromName(title))

    def getMovieByImdbId(self, title):
        soup = self.getSoup(title, None)
        movie = self.getFeatures(soup)
        movie['rating'] = self.getRatingByImdbId(title, soup)
        movie['summary'] = self.getSummaryByImdbId(title, soup)
        movie['director'] = self.getDirectorByImdbId(title, soup)
        movie['casting'] = self.getCastingByImdbId(title)

        return movie

    #############################
    '''get Ratings only STARTS'''
    #############################

    def getRating(self, title):
        return self.getRatingByImdbId(self.getIdFromName(title))

    def getRatingByImdbId(self, title, soup=None):
        soup = self.getSoup(title, soup)
        try:
            return re.sub('\s+', '', self.parseHTML(soup, 'div', 'class', 'ratingValue').get("strong", {}).get("span", {}).get("text", ""))
        except Exception as error:
            print("Failed to obtain rating with error: {}".format(error))
            return ""

    ###########################
    '''get Ratings only ENDS'''
    ###########################

    '''--------------------------------------------------------------------'''

    #############################
    '''get Summary only STARTS'''
    #############################

    def getSummary(self, title):
        return self.getSummaryByImdbId(self.getIdFromName(title))

    def getSummaryByImdbId(self, title, soup=None):
        soup = self.getSoup(title, soup)
        return (re.sub(r'[\t\r\n]', '', (self.parseHTML(soup, 'div', 'class', 'summary_text').get("text", "")))).strip()

    #############################
    '''get Summary only ENDS'''
    #############################

    '''--------------------------------------------------------------------'''

    #############################
    '''get Director only STARTS'''
    #############################

    def getDirector(self, title):
        return self.getDirectorByImdbId(self.getIdFromName(title))

    def getDirectorByImdbId(self, title, soup=None):
        soup = self.getSoup(title, soup)
        return re.sub('\s+', '', self.parseHTML(soup, 'span', 'itemprop', 'director').get("a", {}).get("span", {}).get("text", ""))

    #############################
    '''get Director only ENDS'''
    #############################

    '''--------------------------------------------------------------------'''

    #############################
    '''get Casting only STARTS'''
    #############################

    def getCasting(self, title, length=10, all=False):
        return self.getCastingByImdbId(self.getIdFromName(title), length=length, all=all)

    def getCastingByImdbId(self, title, length=10, all=False):
        soup = self.parseHTML(
            self.scrapSite(self.titleUrl+title+"/"+self.creditsPath),
            'table', 'class', 'cast_list'
        )
        castList = []
        if soup:
            counter = 0
            for tr in soup.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) > 2:
                    cast = {}
                    cast['actor'] = re.sub(r'[\t\r\n]', '', "".join(
                        tds[1].find_all(text=True))).strip()
                    cast['role'] = re.sub(r'[\t\r\n]', '', "".join(
                        tds[3].find_all(text=True))).strip()
                    castList.append(cast)
                    if not all:
                        counter += 1
                        if counter == 10:
                            break
        return castList

    #############################
    '''get Casting only ENDS'''
    #############################

    '''--------------------------------------------------------------------'''

    def getFeatures(self, soup):
        features = {}
        features['title'] = self.currentSearchTitle
        features['runTime'] = re.sub(
            '\s+', '', self.parseHTML(soup, 'time', 'itemprop', 'duration').get("text", ""))
        features['titleYear'] = self.parseHTML(
            soup, 'span', 'id', 'titleYear').get("a", {}).get("text", "")
        features['releaseDate'] = self.parseHTML(
            soup, 'meta', 'itemprop', 'datePublished').get("content", "")

        genreDirty = soup.find_all(attrs={"itemprop": "genre", "class": "itemprop"})
        genre = []
        for tag in genreDirty:
            genre.append(tag.text)

        features['genre'] = genre
        features['posterUrl'] = self.parseHTML(soup, 'div', 'class', 'poster').get(
            "a", {}).get("img", {}).get("src", "")

        return features

    def getSoup(self, title, soup):
        if soup is None:
            soup = self.scrapSite(self.titleUrl+title+"/")
        return soup

    def parseHTML(self, soup, ele, idType, idValue):
        result = soup.find(ele, {idType: idValue})
        if result:
            return result
        else:
            return {}

    def getIdFromName(self, title):
        try:
            soup = self.scrapSite(IMDB.searchUrl+title)
            movie = soup.find('td', {'class': 'result_text'}).a
            print("Movie: "+movie.text)
            self.currentSearchTitle = movie.text
            return movie['href'].split('/')[2]
        except Exception:
            print("Sorry an error accured cant get data extracted")

        return ""

    def scrapSite(self, url):
        try:
            resp = requests.get(url)
            return BeautifulSoup(resp.text, "html5lib")
        except Exception:
            print("Problem with the network connection, please check your wifi or lan connection")


if __name__ == "__main__":
    imdb = IMDB()
    result = imdb.getMovie("The Polar Express")
    print type(result)
    print result

    result = imdb.getMovie("")
