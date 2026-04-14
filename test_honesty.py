import os, sys
sys.stdout = open(os.devnull, 'w')

import requests, json, base64
from src.utils.crypto import _qrc_cloud_decrypt
from src.lyrics.parsers import parse_qrc

url = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
p1 = {
    'comm': {'ct': 11, 'cv': '1003006', 'v': '1003006', 'os_ver': '15', 'phonetype': '24122RKC7C', 'tmeAppID': 'qqmusiclight', 'nettype': 'NETWORK_WIFI', 'udid': '0'},
    'request': {'method': 'GetSession', 'module': 'music.getSession.session', 'param': {'caller': 0, 'uid': '0', 'vkey': 0}}
}
r1 = requests.post(url, json=p1, headers={'User-Agent': 'okhttp/3.14.9', 'content-type': 'application/json', 'cookie': 'tmeLoginType=-1;', 'accept-encoding': 'gzip'}, timeout=10)
sd = r1.json()['request']['data']['session']
uid, sid, userip = sd.get('uid', 0), sd.get('sid', ''), sd.get('userip', '')

p2 = {
    'comm': {'ct': 11, 'cv': '1003006', 'v': '1003006', 'os_ver': '15', 'phonetype': '24122RKC7C', 'tmeAppID': 'qqmusiclight', 'nettype': 'NETWORK_WIFI', 'udid': '0', 'uid': uid, 'sid': sid, 'userip': userip},
    'request': {
        'method': 'GetPlayLyricInfo',
        'module': 'music.musichallSong.PlayLyricInfo',
        'param': {
            'songID': 1538251,
            'songName': base64.b64encode('Honesty'.encode()).decode(),
            'albumName': base64.b64encode('WHITE ALBUM2 Original Soundtrack'.encode()).decode(),
            'singerName': base64.b64encode('松岡純也'.encode()).decode(),
            'interval': 120, 'crypt': 1, 'qrc': 1, 'trans': 1, 'roma': 1,
            'lrc_t': 0, 'qrc_t': 0, 'trans_t': 0, 'roma_t': 0, 'type': 0, 'ct': 19, 'cv': 2111,
        }
    }
}
r2 = requests.post(url, json=p2, headers={'User-Agent': 'okhttp/3.14.9', 'content-type': 'application/json', 'cookie': 'tmeLoginType=-1;', 'accept-encoding': 'gzip'}, timeout=15)
lyric_enc = r2.json().get('request', {}).get('data', {}).get('lyric', '')

decrypted = _qrc_cloud_decrypt(lyric_enc)
lines = parse_qrc(decrypted)

result = 'DEC:\n' + decrypted + '\n\nPARSED:\n'
for t, txt, wt in lines:
    result += f'  [{t}ms] {txt}\n'

p = os.path.join(os.environ['TEMP'], 'honesty.txt')
with open(p, 'w', encoding='utf-8') as f:
    f.write(result)
