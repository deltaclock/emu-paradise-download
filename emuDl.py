#!/usr/bin/env python3
import re
import warnings
from sys import exit
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import requests
    import colorama
    import threading
    from tqdm import tqdm, TqdmSynchronisationWarning
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"[!] Could not import {e.split()[-1]}!")
    exit('[!] Make sure you have this package installed!')


class c:
    # class for all the colors we will use
    y = colorama.Style.BRIGHT + colorama.Fore.YELLOW
    g = colorama.Style.BRIGHT + colorama.Fore.GREEN
    m = colorama.Style.BRIGHT + colorama.Fore.MAGENTA
    w = colorama.Style.BRIGHT + colorama.Fore.WHITE
    r = colorama.Style.BRIGHT + colorama.Fore.RED
    res = colorama.Style.RESET_ALL


# all the available platforms, the number is the sysid
platform_list = [
    ('ALL', 0),
    ('PS2', 41),
    ('PSP', 44),
    ('Nintendo 64', 9),
    ('Nintendo DS', 32),
    ('NES', 13),
    ('Sony Playstation', 2),
    ('SNES', 5),
    ('Nintendo Game Boy', 12),
    ('Nintendo Game Boy Color', 11),
    ('Nintendo Gameboy Advance', 31),
    ('Nintendo Gamecube', 42),
    ('XBox', 43),
    ('Nintendo Wii U', 70),
    ('Sega Dreamcast', 1)
]

# bypass bot protections
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:59.0) \
     Gecko/20100101 Firefox/59.0',
    'DNT': '1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'emuparadise'
}


# wrapper to supress warnings
def hide_warnings(func):
    def wrapper(direct_url):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", TqdmSynchronisationWarning)
            return func(direct_url)
    return wrapper


# makes a search for the game using the specified platform (sysid)
def make_search_query(search_term, sect=0):
    url = 'https://www.emuparadise.me/roms/search.php'
    search_params = dict(query=search_term, section='roms', sysid=sect)
    r = requests.get(url, headers=headers, params=search_params)

    return r.text if r.status_code == 200 else False


# returns the section of the html containg the search results
def parse_search_html(html_doc):
    soup = BeautifulSoup(html_doc, 'html.parser')
    roms_body = soup('div', attrs={"class": "roms"})
    return roms_body


# returns a list of tuples found in the search body
def parse_links(linksSoup):
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


def isHappyHour():
    happy_hour_url = 'https://www.emuparadise.me/happy_hour.php'
    r = requests.get(happy_hour_url)
    return False if 'var is_high_load' in r.text else True


# saves the game using http as a download method and tqdm for the download bar
@hide_warnings
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


def get_dreamcast_filenames(game_page):
    regex = r"Download (.*) ISO"
    r = requests.get(game_page, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    download_div = soup('div', attrs={"class": "download-link"})
    for link in download_div[0].find_all('a'):
        filename = re.match(regex, link.get('title')).group(1)
        yield filename


def get_direct_download_links(game_path):
    main_domain = 'http://www.emuparadise.me'
    file_server_domain = "http://50.7.92.186/happyxhJ1ACmlTrxJQpol71nBc/"

    _, console_name, _, game_gid = game_path.split('/')

    if 'Dreamcast' in console_name:
        return [file_server_domain + "Dreamcast/" + file
                for file in get_dreamcast_filenames(main_domain + game_path)
                ]

    elif 'roms' in console_name:
        raise NotImplementedError
    else:
        return [main_domain + f'/roms/get-download.php?gid={game_gid}&test=true']


def menu():
    '''return user platform and game choice'''

    print(c.y + '[+] Here is the list of currently supported platforms' + c.res)
    print('-' * 53 + c.g)

    # print a list of the available platforms
    for index, name in enumerate(platform_list):
        print(f'[{index}] {name[0]}')
    print(c.res + '-' * 53)

    console = int(input(c.w + 'Enter a console number: '))
    consoleId = platform_list[console][1]

    print(c.y + '[+] OK! Now type the game you wanna search for')
    game = input(c.w + 'Enter the game name: ')
    return consoleId, game


def main():
    try:
        conId, game_name = menu()
        # to catch invalid console number
    except (ValueError, IndexError):
        exit(c.r + '[!] No such console!' + c.res)

    if len(game_name) < 2:
        exit(c.r + '[!] No such game!' + c.res)
    searchHtml = make_search_query(game_name, sect=conId)

    if not searchHtml:
        exit(c.r + '[!] Server Error! Try again later!' + c.res)

    searchResult = parse_search_html(searchHtml)
    if len(searchResult) == 0:
        exit(c.r + '[!] No Such game!' + c.res)

    gamesList = parse_links(searchResult)
    print(c.res + '-' * 53 + c.g)
    # print the games found with their size
    for idx, game in enumerate(gamesList):
        print('[{}] {} - Size: {}'.format(idx, game[0], game[2]))

    print(c.res + '-' * 53)
    print(c.y + '[+] Which of these games you want to download?')

    try:
        gameNum = int(input(c.w + 'Enter the game number: '))
        game_name, path, game_size = gamesList[gameNum]
        # to catch invalid game number
    except (ValueError, IndexError):
        exit(c.r + '[!] No such game!' + c.res)

    download_links = get_direct_download_links(path)

    # # get the game download page html
    # gamePageHtml = getGameDownloadPage(gameMainUrl)
    # if not gamePageHtml:
    #     exit(c.r + '[!] Server Error! Try again later!' + c.res)

    # # gather more game information
    # gameDownloadLink, gameSize = parseGameLink(gamePageHtml)
    # print(c.y + '[*] Your game {} is {} big'.format(game_name, gameSize))

    prompt = input(c.w + 'Do you really want to download it? [y/n] ')
    if prompt.lower()[0] != 'y':
        print(c.w + '[*] Heres the download link, you can use another program')
        exit(download_links + c.res)

    # user pressed yes, download the game
    print(c.y + '[+] OK! Please wait while your game is downloading!' + c.res)
    return download_links


if __name__ == '__main__':
    colorama.init()
    try:
        print(c.y + '[+] Welcome to EmuParadise Downloader!' + c.res)
        links = main()
        futures = list()
        with ThreadPoolExecutor(max_workers=2) as executor:
            for l in links:
                fut = executor.submit(saveGame, l)
                futures.append(fut)
        for fut in as_completed(futures):
            print(c.m + 'Done!')
        # if isHappyHour():
        #     gameDlUrl = main()
        #     threading.Thread(target=saveGame, args=(gameDlUrl,)).start()
        #     print(c.m + '[+] Its Happy Hour! You can download a second game!')
        #     gameDlUrl = main()
        #     threading.Thread(target=saveGame, args=(gameDlUrl,)).start()
        # else:
        #     gameDlUrl = main()
        #     saveGame(gameDlUrl)
            print(c.y + '[+] Game Downloaded! Have Fun!' + c.res)
    except (KeyboardInterrupt, EOFError):
        print(c.r + '\n[!] Exiting...')
    finally:
        colorama.deinit()
