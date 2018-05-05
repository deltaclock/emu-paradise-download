#!/usr/bin/env python
import requests
from tqdm import tqdm
tqdm.monitor_interval = 2
try:
    from bs4 import BeautifulSoup
except ImportError:
    print "[!] Could not import BeautifulSoup!"

domain = 'https://www.emuparadise.me'
direct = 'http://direct.emuparadise.me'
url = 'https://www.emuparadise.me/roms/search.php'

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


def makeSearchQuery(searchTerm, url=url, sect=0):
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
    print '[+] Welcome to EmuParadise Downloader!'
    print '[+] Here is the list of currently supported platforms'
    for index, name in enumerate(platformDict):
        print '[{}] {}'.format(index, name)
    console = int(raw_input('Enter a console number: '))
    consoleId = platformDict[platformDict.keys()[console]]
    print '[+] OK! Now type the game you wanna search for'
    game = raw_input('Enter the game name: ')
    return consoleId, game


if __name__ == '__main__':
    conId, gameQuery = menu()
    queryResult = makeSearchQuery(gameQuery, sect=conId)
    if not queryResult:
        print '[!] Server Error! Try again later!'
        exit(1)

    searchResult = parseSearchHtml(queryResult)
    if len(searchResult) == 0:
        print '[!] No Such game!'
        exit(1)

    gamesDict = parseLinks(searchResult)
    for idx, game in enumerate(gamesDict):
        print '[{}] {}'.format(idx, game)

    print '[+] Which of these games u want to download?'
    gameNum = int(raw_input('Enter the game number: '))
    gameName = gamesDict.keys()[gameNum]
    href = gamesDict[gameName]
    gameDownloadUrl = domain + href

    gamePageHtml = getGameDownloadPage(gameDownloadUrl)
    if not gamePageHtml:
        print '[!] Server Error! Try again later!'
        exit(1)
    gameDownloadLink, gameSize = parseGameLink(gamePageHtml)

    print '[*] Your game {} is {} big'.format(gameName, gameSize.split()[2])
    prompt = raw_input('Do you really want o download it? [y/n] ').lower()[0]
    gameDownloadLink = direct + gameDownloadLink
    if prompt != 'y':
        print '[!] ok bye :('
        print '[*] Heres the download link, you can use another program now'
        print gameDownloadLink
        exit(1)
    print '[+] OK! Please wait while your game is downloading!'
    saveGame(gameDownloadLink)
