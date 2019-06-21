import HTMLParser
import os
import ssl
import urllib2


def getOnlineContent(URL):
    connSettings = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    location = os.path.join(os.path.dirname(__file__), "cert.pem")
    connSettings.load_verify_locations(cafile=location)
    connSettings.load_default_certs()
    if connSettings.cert_store_stats()['x509_ca'] == 0:
        raise RuntimeError("Failed to load any SSL certs!")

    header = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_4) AppleWebKit/603.1.14 (KHTML, like Gecko) Version/10.1 Safari/603.1.14"}

    req = urllib2.Request(URL, headers=header)

    try:
        handler = urllib2.urlopen(req, timeout=10)
    except Exception as error:
        try:
            handler = urllib2.urlopen(req, timeout=10, context=connSettings)
        except Exception as error:
            raise RuntimeError("Failed to connect to {} with error: {}".format(URL, error))

    result = handler.read()
    result = result.decode('ascii', 'replace')
    hparser = HTMLParser.HTMLParser()
    result = hparser.unescape(result)
    result = unicode(result).encode("ascii", "replace")
    return result
