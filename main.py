import curses
import cv2
import argparse
import os.path
import subprocess
import requests
import base64
import dotenv
import time
import threading
import sys
from bs4 import BeautifulSoup as bs

verbose = False
silent = False
fps = 8
headers = False


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('video', help='the video to use')
    ap.add_argument('-f', '--fps', type=int, default=8, help='framerate of output')
    ap.add_argument('-c', '--convert', action='store_true', help='Convert video to frames but do not scale')
    ap.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    ap.add_argument('-s', '--silent', action='store_true', help='Output nothing but the image')
    ap.add_argument('-r', '--headers', action='store_true', help='Print response headers')
    return ap.parse_args()


def last_path(path):
    return os.path.split(path)[-1]


def filename_to_parts(name):
    if '.' not in name:
        return name, ''
    else:
        *names, ext = name.rsplit('.')
        return '.'.join(names), ext


def ensure_dir(videoname):
    if os.path.isdir(videoname):
        return
    if os.path.exists(videoname):
        raise ValueError("Path {} exists but is not a directory!".format(videoname))
    else:
        os.mkdir(videoname)


def convert_video_to_frames(videopath, fps):
    videoname, videoext = filename_to_parts(last_path(videopath))
    ensure_dir(videoname)
    command = 'ffmpeg -i {} -r {} {}/%03d.bmp'.format(videopath, fps, videoname)
    status, output = subprocess.getstatusoutput(command)
    if verbose:
        print(output)


def scale_image(impath):
    i = cv2.imread(impath)
    if i is None:
        return False
    height, width = i.shape[:2]
    nw = 640
    nh = int(nw // (width / height))
    print('Set terminal to {}x{}'.format(100, int(100 / (width/height))))
    result = cv2.resize(i, (nw, nh))
    cv2.imwrite(impath, result)
    return True


def scale_video_frames(videopath, n=3):
    name, ext = filename_to_parts(last_path(videopath))
    namesfmt = '{}/%0{}d.bmp'.format(name, n)
    for i in range(1, 1000):
        if verbose:
            print('Trying to scale: ' + namesfmt % i)
        if not scale_image(namesfmt % i):
            break
    input("press enter!")


def hex_to_ansi(hex):
    r, g, b = hex[1:3], hex[3:5], hex[5:]
    r, g, b = int(r, base=16), int(g, base=16), int(b, base=16)
    r, g, b = r // 127, g // 127, b // 127
    index = (r << 2) | (g << 1) | (b << 0)
    return ({
            0: '\u001b[40;1m',
            (1 << 2): '\u001b[41;1m',
            (1 << 1): '\u001b[42;1m',
            ((1 << 2) | (1 << 1)): '\u001b[43;1m',
            (1 << 0): '\u001b[44;1m',
            ((1 << 2) | (1 << 0)): '\u001b[45;1m',
            ((1 << 1) | (1 << 0)): '\u001b[46;1m',
            7: '\u001b[47;1m'
            })[index]


def color_from_style(style):
    r = style.split(':')[-1].strip(';')
    if verbose:
        print(r)
    return r


def ascify_image(impath):
    key = dotenv.get_key('./.env', 'X_TEXTART_API_SECRET')
    data = {'image': open(impath, 'rb'), 'format': ('format', 'mono')}
    r = requests.post('http://api.textart.io/img2txt.json', files=data, headers={'X-Textart-Api-Secret': key})
    if headers:
        print(r.headers)
    if verbose:
        print(r.text)
    json = r.json()
    if verbose:
        print(json)
    html = base64.decodebytes(json['contents']['textart'].encode('utf-8'))
    with open('dump110.html', 'w') as f:
        f.write(str(html, encoding='utf-8'))
    soup = bs(html, features="html.parser")
    s = ''
    ch = 0
    for i in soup.find_all('span'):
        clr = color_from_style(i['style'])
        s += (hex_to_ansi(clr) + " ")
    return s


def print_video_frames(videopath, n=3):
    name, ext = filename_to_parts(last_path(videopath))
    namesfmt = '{}/%0{}d.bmp'.format(name, n)
    t = threading.Thread(target=lambda: subprocess.run(['afplay', videopath]))
    started = False
    for i in range(1, 1000):
        try:
            s = ascify_image(namesfmt % i)
            if not started:
                t.start()
            print(s)
            time.sleep(1 / fps)
        except (IOError, OSError) as e:
            if verbose:
                print("Out of frames? " + str(e))


def main():
    global verbose, silent, fps, headers
    options = parse_args()
    verbose = options.verbose
    silent = options.silent
    fps = options.fps
    headers = options.headers
    convert_video_to_frames(options.video, options.fps)
    if not options.convert:
        scale_video_frames(options.video)
    print_video_frames(options.video)


if __name__ == '__main__':
    exit(main())
