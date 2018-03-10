import os
import ssl
import urllib
import urllib2
import HTMLParser
import unicodedata

def getOnlineContent(URL):
    print "Trying to connect:", URL
    connSettings = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    location = os.path.join(os.path.dirname(__file__), "cert.pem")
    connSettings.load_verify_locations(cafile=location)
    connSettings.load_default_certs()
    if connSettings.cert_store_stats()['x509_ca'] == 0:
        return False

    header = { "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_4) AppleWebKit/603.1.14 (KHTML, like Gecko) Version/10.1 Safari/603.1.14"}

    req = urllib2.Request(URL, headers=header)

    try:
        handler = urllib2.urlopen(req, timeout=10)
    except Exception as errorString:
        print "Error: " + str(errorString)
        print "Trying HTTPS."
        try:
            handler = urllib2.urlopen(req, timeout=10, context=connSettings)
        except Exception as errorString:
            print "Error: " + str(errorString)
            return False
    try:
        result = handler.read()
    except Exception as errorString:
        print "Error: " + str(errorString)
        return False
    if len(result) > 0:
        result = result.decode('ascii', 'ignore')
        result = unicodedata.normalize('NFKD', result).encode('ascii', 'ignore')
        hparser = HTMLParser.HTMLParser()
        result = hparser.unescape(result)
        return result
    else:
        return False
