#!/usr/bin/env python3
import re
import warnings
from os import path
from sys import exit
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import requests
    import colorama
    import threading
    from tqdm import tqdm, TqdmSynchronisationWarning
    from bs4 import BeautifulSoup, Tag
except ImportError as e:
    print(f"[!] Could not import {str(e).split()[-1]}!")
    exit('[!] Make sure you have this package installed!')


class Colors:
    '''class for all the colors we will use'''
    yellow = colorama.Style.BRIGHT + colorama.Fore.YELLOW
    green = colorama.Style.BRIGHT + colorama.Fore.GREEN
    purple = colorama.Style.BRIGHT + colorama.Fore.MAGENTA
    white = colorama.Style.BRIGHT + colorama.Fore.WHITE
    red = colorama.Style.BRIGHT + colorama.Fore.RED
    cyan = colorama.Style.BRIGHT + colorama.Fore.CYAN
    reset = colorama.Style.RESET_ALL


class Symbols:
    check = u'\u2714'
    cross = u'\u2718'


def red_exit(msg):
    exit(Colors.red + msg + Colors.reset)


@dataclass
class Game:
    '''Struct-like object to store a game's data'''
    title: str
    url: str
    size: str


class GameFile(Game):
    '''Used to store the many files a Game might have'''
    pass


class UserError(Exception):
    '''This exception is raised when the user did something abnormal'''
    pass


class ServerError(Exception):
    '''This exception is raised when the server failed'''
    pass


DOMAIN = 'https://www.emuparadise.me'

# all the available platforms, the number is the sysid
PLATFORM_LIST = [
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
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:59.0) \
     Gecko/20100101 Firefox/59.0',
    'DNT': '1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'emuparadise'
}


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def hide_warnings(func):
    '''Wrapper to supress tqdm warnings'''
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", TqdmSynchronisationWarning)
            return func(*args, **kwargs)
    return wrapper


class GameSearcher:
    def __init__(self, game, con_id=0):
        self.search_term = game
        self.console_id = con_id
        self._games_links = list()

    def get_games(self):
        '''Returns the list of Game objects found'''
        return self._games_links

    def search(self):
        """Makes a search for the game using the specified platform (sysid)"""
        url = DOMAIN + '/roms/search.php'
        search_params = dict(query=self.search_term,
                             section='roms', sysid=self.console_id)
        r = requests.get(url, headers=HEADERS, params=search_params)

        if r.status_code != 200:
            raise ServerError('Search query failed!')
        # parse the html page
        soup = BeautifulSoup(r.text, 'html.parser')
        roms_body = soup('div', attrs={"class": "roms"})
        # store the results in a list
        for tag in roms_body:
            game_title = tag.a.contents[0]
            game_url = DOMAIN + tag.a.get('href')
            tag_text = tag.get_text()
            size = re.search(r'Size: (.*) ', tag_text)
            if size is None:
                game_size = 'Unknown'
            else:
                game_size = size.group(1)
            game = Game(title=game_title, url=game_url, size=game_size)
            self._games_links.append(game)


class GameDownloader:
    def __init__(self, game_obj):
        if not isinstance(game_obj, Game):
            raise TypeError('This class needs a Game instance.')
        self.game = game_obj
        url_parts = game_obj.url.split('/')
        self.game_gid = url_parts[-1]
        self.game_folder = url_parts[4]
        self.console_name = url_parts[3]
        self.game_files = list()

    def __urlify(self, uri):
        if not uri.startswith('http'):
            return DOMAIN + uri
        return uri

    def __get_url_redirect(self, page='/roms/get-download.php'):
        url = DOMAIN + page
        payload = dict(gid=self.game_gid, test='true')
        r = requests.head(url, params=payload, headers=HEADERS,
                          allow_redirects=False)
        url = r.headers.get('Location')
        if r.status_code != 301:
            raise ServerError(f'Server returned {r.status_code} at redirect.')
        if url == '':
            return False
        return url

    def __get_url_dreamcast(self, title):
        title_regex = r"Download (.*) ISO"
        url = 'http://50.7.92.186/happyxhJ1ACmlTrxJQpol71nBc/Dreamcast/'
        try:
            url += re.match(title_regex, title).group(1)
        except Exception:
            return None
        return url

    def __get_url_fileinfo(self, file_url):
        '''This methods returns the type of the file and its size'''
        r = requests.head(file_url, headers=HEADERS, allow_redirects=True)
        ftype = r.headers.get('Content-Type')
        size = r.headers.get('Content-Length', 0)
        return ftype, sizeof_fmt(int(size))

    def __get_direct_url(self, anchor_tag):
        '''This method tries to get the direct url for a Game file, on failure returns None'''
        if not isinstance(anchor_tag, Tag):
            raise TypeError('This methods needs an anchor bs4 Tag object.')
        href = self.__urlify(anchor_tag.get('href'))
        title = anchor_tag.get('title')
        # try using the href link directly
        file_type, _ = self.__get_url_fileinfo(href)
        if not 'html' in file_type:
            return href
        # try the redirect method
        url = self.__get_url_redirect()
        if url:
            return url
        # maybe its a dreamcast game
        url = self.__get_url_dreamcast(title)
        if url:
            return url
        return None

    def find_game_files(self):
        '''This method parses the game html page and finds all the game files'''
        if '/roms/' in self.game.url:
            raise NotImplementedError('Code to handle old ROM games missing.')
        # fetch the html page and create a soup with it
        r = requests.get(self.game.url, headers=HEADERS)
        soup = BeautifulSoup(r.text, 'html.parser')
        # get the section containing the download links
        download_div = soup('div', attrs={"class": "download-link"})[0]
        # for each game link
        for anchor in download_div.find_all('a'):
            file_title = anchor.get_text()
            file_title = file_title.replace('Download ', '')
            file_url = self.__get_direct_url(anchor)
            _, file_size = self.__get_url_fileinfo(file_url)
            game_file = GameFile(
                title=file_title, url=file_url, size=file_size)
            self.game_files.append(game_file)
        return self.game_files

    @hide_warnings
    def __save_file(self, direct_url, folder):
        '''Saves the game using http as a download method and tqdm for the download bar'''
        # if not isinstance(game_file, GameFile):
        #     raise TypeError('This method needs a GameFile object.')
        # start a http byte stream
        set_http = {'epdprefs': 'ephttpdownload'}
        r = requests.get(direct_url, stream=True,
                         headers=HEADERS, cookies=set_http)
        # get game size and game name + extension
        total_size = int(r.headers.get('content-length', 0)) / (32 * 1024.0)
        file_name = r.url.split('/')[-1]
        file_name = path.join(folder, file_name)
        # save the file 4096 bytes at a time while updating the progress bar
        with open(file_name, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True,
                      unit_divisor=1024) as pbar:
                for chunk in r.iter_content(chunk_size=4096):
                    f.write(chunk)
                    pbar.update(len(chunk))

    def save_game_files(self, file_indexes, folder='Games'):
        '''Save the game files with the specified indexes'''
        files_folder = path.join(folder, self.console_name, self.game_folder)
        futures_to_files = dict()
        # the site only allows 2 concurrent downloads
        with ThreadPoolExecutor(max_workers=2) as executor:
            # for each game file
            for index in file_indexes:
                try:
                    game_file = self.game_files[index]
                except IndexError:
                    raise UserError('Selected file number does not exist.')
                if not game_file.url:
                    continue
                # save the game file
                fut = executor.submit(
                    self.__save_file, game_file.url, files_folder)
                futures_to_files.update({fut: game_file})
            for future in as_completed(futures_to_files):
                # to propagate exceptions
                future.result()
                file = futures_to_files[future]
                yield file


def menu():
    '''Return user platform and game choice'''
    print(Colors.yellow +
          '[+] Here is the list of currently supported platforms' + Colors.reset)
    print('-' * 53 + Colors.green)
    for index, name in enumerate(PLATFORM_LIST):
        print(f'[{index}] {name[0]}')
    print(Colors.reset + '-' * 53)
    try:
        console = int(input(Colors.white + 'Enter a console number: '))
        console_id = PLATFORM_LIST[console][1]
    except IndexError:
        raise UserError('Selected number is wrong')
    except ValueError:
        raise UserError('Not a valid number')

    print(Colors.yellow + '[+] OK! Now type the game you wanna search for')
    game = input(Colors.white + 'Enter the game name: ')
    return console_id, game


def main():
    try:
        con_id, game_name = menu()
    except UserError as e:
        red_exit(f'[!] {str(e)}!')

    if len(game_name) < 2:
        red_exit('[!] No such game!')

    searcher = GameSearcher(game_name, con_id=con_id)

    try:
        searcher.search()
    except ServerError as e:
        print(e)
        red_exit('[!] Server Error! Try again later!')

    search_results = searcher.get_games()
    if len(search_results) == 0:
        red_exit('[!] No Such game!')

    print(Colors.reset + '-' * 53 + Colors.green)
    # print the games found with their size
    for idx, game in enumerate(search_results):
        print(f'[{idx}] {game.title} - Size: {game.size}')
    print(Colors.reset + '-' * 53)

    print(Colors.yellow + '[+] Which of these games you want to download?')
    try:
        game_num = int(input(Colors.white + 'Enter the game number: '))
        download_game = search_results[game_num]
    except (ValueError, IndexError):
        red_exit('[!] No such game!')
    print('[*] Please wait..')
    downloader = GameDownloader(download_game)
    game_files = downloader.find_game_files()
    # print the game files and let the user select
    for idx, file in enumerate(game_files):
        if not file.url:
            print(
                Colors.purple + f'[{idx}] {file.title} - Size: {file.size} - Available: {Colors.red}{Symbols.cross}' + Colors.reset)
            continue
        print(Colors.cyan +
              f'[{idx}] {file.title} - Size: {file.size} - Available: {Colors.green}{Symbols.check}' + Colors.reset)
    print(Colors.green + f'[{idx+1}] ALL')

    print(Colors.yellow +
          '[+] Which of these game files you want to download?')
    try:
        nums = input(
            Colors.white + 'Enter the game file number/s (Comma separated): ').split(',')
        file_nums = list()
        for num in set(nums):
            n = int(num)
            if n >= len(game_files):
                raise IndexError
            file_nums.append(n)
    except ValueError:
        red_exit('[!] Not a number!')
    except IndexError:
        file_nums = list(range(len(game_files)))
    print(file_nums)
    prompt = input(
        Colors.white + 'Do you really want to download them? [y/n] ')
    if prompt.lower()[0] != 'y':
        red_exit('[!] Bye..')

    # user pressed yes, download the game
    print(Colors.yellow +
          '[+] OK! Please wait while your game is downloading!' + Colors.reset)
    for downloaded_file in downloader.save_game_files(file_nums):
        print(downloaded_file.title + Colors.green + Symbols.check)


if __name__ == '__main__':
    colorama.init()
    try:
        print(Colors.yellow +
              '[+] Welcome to EmuParadise Downloader!' + Colors.reset)
        main()
        print(Colors.yellow + '[+] Game Downloaded! Have Fun!' + Colors.reset)
    except (KeyboardInterrupt, EOFError):
        red_exit('\n[!] Exiting...')
    finally:
        colorama.deinit()
