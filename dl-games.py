#!/usr/bin/env python
import requests
import colorama as col
from tqdm import tqdm, TqdmSynchronisationWarning
import warnings
try:
    from bs4 import BeautifulSoup
except ImportError:
    print "[!] Could not import BeautifulSoup!"

domain = 'https://www.emuparadise.me'
direct = 'http://direct.emuparadise.me'
searchUrl = 'https://www.emuparadise.me/roms/search.php'
yBr = col.Style.BRIGHT + col.Fore.YELLOW
gBr = col.Style.BRIGHT + col.Fore.GREEN
wBr = col.Style.BRIGHT + col.Fore.WHITE
rBr = col.Style.BRIGHT + col.Fore.RED
cRes = col.Style.RESET_ALL
platformDict = dict(PS2=41, PSP=44)

# bypass bot protections
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:59.0) \
     Gecko/20100101 Firefox/59.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

payload = {
    'query': '',
    'section': 'roms',
    'sysid': ''
}


def hideWarnings(func):
    def wrapper(directUrl):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", TqdmSynchronisationWarning)
            return func(directUrl)
    return wrapper


def makeSearchQuery(searchTerm, url=searchUrl, sect=0):
    payload['query'] = searchTerm
    payload['sysid'] = sect
    r = requests.get(url, headers=headers, params=payload)

    return r.text if r.status_code == 200 else False


def parseSearchHtml(htmlDoc):
    soup = BeautifulSoup(htmlDoc, 'html.parser')
    links = soup('div', attrs={"class": "roms"})
    return links


def parseLinks(linksSoup):
    linksDict = {}
    for link in linksSoup:
        gameTitle = link.a.contents
        gameUrl = link.a.get('href')
        linksDict[gameTitle[0]] = gameUrl
    return linksDict


def getGameDownloadPage(gameUrl):
    gameUrl += '-download'
    skipCaptcha = {'downloadcaptcha': '1'}
    r = requests.get(gameUrl, headers=headers, cookies=skipCaptcha)

    return r.text if r.status_code == 200 else False


def parseGameLink(gameDownloadDoc):
    soup = BeautifulSoup(gameDownloadDoc, 'html.parser')
    downloadLink = soup('a', attrs={"id": "download-link"})
    size = soup('font', attrs={"style": "font-size: 16px"})

    downloadLink = downloadLink[0].get('href')
    size = size[0].contents[0].strip(' - ')

    return downloadLink, size


@hideWarnings
def saveGame(directUrl):
    setHttp = {'epdprefs': 'ephttpdownload'}
    r = requests.get(directUrl, stream=True, headers=headers, cookies=setHttp)
    totalSize = int(r.headers.get('content-length', 0)) / (32 * 1024.0)
    fileName = r.url.split('/')[-1]
    with open(fileName, 'wb') as f:
        with tqdm(total=totalSize, unit='B', unit_scale=True,
                  unit_divisor=1024) as pbar:
            for chunk in r.iter_content(chunk_size=4096):
                f.write(chunk)
                pbar.update(len(chunk))


def menu():
    print yBr + '[+] Welcome to EmuParadise Downloader!'
    print '[+] Here is the list of currently supported platforms' + cRes
    print '-' * 53 + gBr
    for index, name in enumerate(platformDict):
        print '[{}] {}'.format(index, name)
    print cRes + '-' * 53
    console = int(raw_input(wBr + 'Enter a console number: '))
    consoleId = platformDict[platformDict.keys()[console]]
    print yBr + '[+] OK! Now type the game you wanna search for'
    game = raw_input((wBr + 'Enter the game name: '))
    return consoleId, game


def main():

    try:
        conId, gameQuery = menu()
    except IndexError:
        print rBr + '[!] No such console!' + cRes
        exit(1)

    queryResult = makeSearchQuery(gameQuery, sect=conId)
    if not queryResult:
        print rBr + '[!] Server Error! Try again later!' + cRes
        exit(1)

    searchResult = parseSearchHtml(queryResult)
    if len(searchResult) == 0:
        print rBr + '[!] No Such game!' + cRes
        exit(1)

    gamesDict = parseLinks(searchResult)
    print cRes + '-' * 53 + gBr
    for idx, game in enumerate(gamesDict):
        print '[{}] {}'.format(idx, game)

    print cRes + '-' * 53
    print yBr + '[+] Which of these games u want to download?'
    gameNum = int(raw_input(wBr + 'Enter the game number: '))
    gameName = gamesDict.keys()[gameNum]
    href = gamesDict[gameName]
    gameDownloadUrl = domain + href

    gamePageHtml = getGameDownloadPage(gameDownloadUrl)
    if not gamePageHtml:
        print rBr + '[!] Server Error! Try again later!' + cRes
        exit(1)
    gameDownloadLink, gameSize = parseGameLink(gamePageHtml)
    gameSize = gameSize.split()[2]
    print yBr + '[*] Your game {} is {} big'.format(gameName, gameSize)
    prompt = raw_input(wBr + 'Do you really want o download it? [y/n] ')
    gameDownloadLink = direct + gameDownloadLink
    if prompt.lower()[0] != 'y':
        print wBr + '[*] Heres the download link, you can use another program'
        print gameDownloadLink + cRes
        exit(1)
    print yBr + '[+] OK! Please wait while your game is downloading!' + cRes
    saveGame(gameDownloadLink)


if __name__ == '__main__':
    col.init()
    try:
        main()
    except KeyboardInterrupt:
        print rBr + '\n[!] Exiting...'
    col.deinit()
