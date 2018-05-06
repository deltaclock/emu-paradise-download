#!/usr/bin/env python
import warnings
from sys import exit
try:
    import requests
    import colorama
    from tqdm import tqdm, TqdmSynchronisationWarning
    from bs4 import BeautifulSoup
except ImportError as e:
    print "[!] Could not import {}!".format(e.split()[-1])
    exit('[!] Make sure you have this package installed!')


class c:
    # class for all the colors we will use
    y = colorama.Style.BRIGHT + colorama.Fore.YELLOW
    g = colorama.Style.BRIGHT + colorama.Fore.GREEN
    w = colorama.Style.BRIGHT + colorama.Fore.WHITE
    r = colorama.Style.BRIGHT + colorama.Fore.RED
    res = colorama.Style.RESET_ALL


# all the available platforms, the number is the sysid
platformList = dict(PS2=41, PSP=44).items()

# bypass bot protections
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:59.0) \
     Gecko/20100101 Firefox/59.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


# wrapper to supress warnings
def hideWarnings(func):
    def wrapper(directUrl):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", TqdmSynchronisationWarning)
            return func(directUrl)
    return wrapper


# makes a search for the game using in the specified platform(sysid)
def makeSearchQuery(searchTerm, sect=0):
    url = 'https://www.emuparadise.me/roms/search.php'
    searchParams = dict(query=searchTerm, section='roms', sysid=sect)
    r = requests.get(url, headers=headers, params=searchParams)

    return r.text if r.status_code == 200 else False


# returns the section of the html containg the search results
def parseSearchHtml(htmlDoc):
    soup = BeautifulSoup(htmlDoc, 'html.parser')
    romsBody = soup('div', attrs={"class": "roms"})
    return romsBody


# returns a list of tuples found in the search body
def parseLinks(linksSoup):
    linksDict = []

    for link in linksSoup:
        gameTitle = link.a.contents[0]
        gameUrl = link.a.get('href')
        gameSize = link.get_text().split()[-1]

        linksDict.append((gameTitle, gameUrl, gameSize))

    return linksDict


# returns the game download page html
def getGameDownloadPage(gameUrl):
    gameUrl += '-download'
    skipCaptcha = {'downloadcaptcha': '1'}
    r = requests.get(gameUrl, headers=headers, cookies=skipCaptcha)

    return r.text if r.status_code == 200 else False


# returns the game href link and the game size
def parseGameLink(gameDownloadPage):
    soup = BeautifulSoup(gameDownloadPage, 'html.parser')
    downloadLink = soup('a', attrs={"id": "download-link"})
    size = soup('font', attrs={"style": "font-size: 16px"})

    downloadLink = 'http://direct.emuparadise.me' + downloadLink[0].get('href')
    size = size[0].contents[0].strip(' - ').split()[2]  # xxxMB

    return downloadLink, size


def isHappyHour(gameDownloadPage):
    soup = BeautifulSoup(gameDownloadPage, 'html.parser')
    happy = soup('span', attrs={"id": "happy-hour"})
    return True if len(happy) != 0 else False


# saves the game using http as a download method and tqdm for the download bar
@hideWarnings
def saveGame(directUrl):
    # start a http byte stream
    setHttp = {'epdprefs': 'ephttpdownload'}
    r = requests.get(directUrl, stream=True, headers=headers, cookies=setHttp)
    # get game size and game name + extension
    totalSize = int(r.headers.get('content-length', 0)) / (32 * 1024.0)
    fileName = r.url.split('/')[-1]
    # save the file 4096 bytes at a time while updating the progress bar
    with open(fileName, 'wb') as f:
        with tqdm(total=totalSize, unit='B', unit_scale=True,
                  unit_divisor=1024) as pbar:
            for chunk in r.iter_content(chunk_size=4096):
                f.write(chunk)
                pbar.update(len(chunk))


# return user platform and game choice
def menu():
    print c.y + '[+] Welcome to EmuParadise Downloader!'
    print '[+] Here is the list of currently supported platforms' + c.res
    print '-' * 53 + c.g

    # print a list of the available platforms
    for index, name in enumerate(platformList):
        print '[{}] {}'.format(index, name[0])
    print c.res + '-' * 53

    console = int(raw_input(c.w + 'Enter a console number: '))
    consoleId = platformList[console][1]

    print c.y + '[+] OK! Now type the game you wanna search for'
    game = raw_input((c.w + 'Enter the game name: '))
    return consoleId, game


def main():

    try:
        conId, gameQuery = menu()
        # to catch invalid console number
    except IndexError:
        exit(c.r + '[!] No such console!' + c.res)

    searchHtml = makeSearchQuery(gameQuery, sect=conId)
    if not searchHtml:
        exit(c.r + '[!] Server Error! Try again later!' + c.res)

    searchResult = parseSearchHtml(searchHtml)
    if len(searchResult) == 0:
        exit(c.r + '[!] No Such game!' + c.res)

    gamesList = parseLinks(searchResult)
    print c.res + '-' * 53 + c.g
    # print the games found with their size
    for idx, game in enumerate(gamesList):
        print '[{}] {} - Size: {}'.format(idx, game[0], game[2])

    print c.res + '-' * 53
    print c.y + '[+] Which of these games you want to download?'

    gameNum = int(raw_input(c.w + 'Enter the game number: '))
    gameName = gamesList[gameNum][0]
    href = gamesList[gameNum][1]
    gameMainUrl = 'https://www.emuparadise.me' + href

    # get the game download page html
    gamePageHtml = getGameDownloadPage(gameMainUrl)
    if not gamePageHtml:
        exit(c.r + '[!] Server Error! Try again later!' + c.res)

    # gather more game information
    gameDownloadLink, gameSize = parseGameLink(gamePageHtml)
    print c.y + '[*] Your game {} is {} big'.format(gameName, gameSize)

    prompt = raw_input(c.w + 'Do you really want o download it? [y/n] ')
    if prompt.lower()[0] != 'y':
        print c.w + '[*] Heres the download link, you can use another program'
        exit(gameDownloadLink + c.res)

    # user pressed yes, download the game
    print c.y + '[+] OK! Please wait while your game is downloading!' + c.res
    saveGame(gameDownloadLink)
    print c.y + '[+] Game Downloaded! Have Fun!' + c.res


if __name__ == '__main__':
    colorama.init()
    try:
        main()
    except KeyboardInterrupt, EOFError:
        print c.r + '\n[!] Exiting...'
    finally:
        colorama.deinit()
